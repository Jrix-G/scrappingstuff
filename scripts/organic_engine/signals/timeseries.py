"""Extraction de features temporelles à partir d'une série de mesures.

Hypothèse fondatrice : la croissance organique précoce est *multiplicative*
(exponentielle), pas additive. Un produit qui passe de 100 → 200 → 400 ventes
a un taux de croissance CONSTANT ; 100 → 200 → 500 ACCÉLÈRE. Pour capturer ça,
tout le calcul se fait sur ``log(1 + valeur)`` :

* la **vélocité** = pente de la régression linéaire de log(v) sur le temps
  = taux de croissance exponentiel instantané (par jour), invariant d'échelle ;
* l'**accélération** = terme quadratique d'un ajustement de degré 2 sur log(v)
  = dérivée seconde, le signal qui distingue « croît » de « EXPLOSE » ;
* la **volatilité** = écart-type des résidus du trend (sur l'échelle log)
  = bruit du signal, sert à pondérer la confiance (bas = fiable).

Aucune de ces quantités n'est pondérée arbitrairement : ce sont des dérivées
mathématiques bien définies de la série observée.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import exp

import numpy as np

# Constante MAD -> écart-type pour une loi normale (cohérence des z-scores).
_MAD_SCALE = 1.4826
_EPS = 1e-9


@dataclass(slots=True)
class TrendFeatures:
    """Résumé dérivé d'une série temporelle d'un signal pour un produit."""

    level: float          # dernière valeur lissée (échelle d'origine)
    log_level: float      # log(1+level), pour comparaisons inter-produits
    velocity: float       # pente log/jour = taux de croissance exponentiel
    acceleration: float   # dérivée seconde (log/jour²)
    volatility: float     # écart-type des résidus log du trend
    r2: float             # qualité d'ajustement du trend [0,1]
    n_points: int         # nombre de mesures utilisées
    span_days: float      # durée couverte par la série

    @property
    def monthly_growth(self) -> float:
        """Croissance mensuelle implicite (ex. 0.5 = +50 %/mois)."""
        return exp(self.velocity * 30.0) - 1.0

    def is_reliable(self, min_points: int = 3, max_volatility: float = 1.0) -> bool:
        """Vrai si la série est assez riche et peu bruitée pour être exploitée."""
        return self.n_points >= min_points and self.volatility <= max_volatility


def _ema(values: np.ndarray, alpha: float = 0.5) -> np.ndarray:
    """Lissage exponentiel simple pour atténuer le bruit ponctuel."""
    out = np.empty_like(values, dtype=float)
    out[0] = values[0]
    for i in range(1, len(values)):
        out[i] = alpha * values[i] + (1 - alpha) * out[i - 1]
    return out


def extract_trend(
    timestamps_days: list[float] | np.ndarray,
    values: list[float] | np.ndarray,
    smooth: bool = True,
) -> TrendFeatures:
    """Calcule les features de tendance d'une série (temps en jours, valeurs).

    Args:
        timestamps_days: instants des mesures en jours (croissants).
        values: valeurs du signal (>= 0). Travaillées en log(1+v).
        smooth: applique un lissage EMA avant l'ajustement.

    Returns:
        Un :class:`TrendFeatures`. Robuste aux séries courtes : vélocité dès
        2 points, accélération dès 3, sinon 0 (et confiance basse en aval).
    """
    t = np.asarray(timestamps_days, dtype=float)
    v = np.asarray(values, dtype=float)
    if t.size != v.size or t.size == 0:
        return TrendFeatures(0, 0, 0, 0, 0, 0, 0, 0)

    # Tri chronologique défensif.
    order = np.argsort(t)
    t, v = t[order], v[order]

    log_v = np.log1p(np.clip(v, 0, None))
    if smooth and log_v.size >= 3:
        log_v = _ema(log_v)

    level = float(v[-1])
    log_level = float(log_v[-1])
    n = int(t.size)
    span = float(t[-1] - t[0])

    if n == 1:
        return TrendFeatures(level, log_level, 0, 0, 0, 0, 1, 0)

    # Recentrage du temps pour la stabilité numérique.
    tc = t - t.mean()

    # Vélocité : pente OLS de log_v ~ tc.
    slope, intercept = np.polyfit(tc, log_v, 1)
    velocity = float(slope)
    fitted_lin = intercept + slope * tc
    residuals = log_v - fitted_lin
    volatility = float(np.std(residuals)) if n > 2 else 0.0
    ss_tot = float(np.sum((log_v - log_v.mean()) ** 2))
    r2 = 1.0 - float(np.sum(residuals**2)) / (ss_tot + _EPS) if ss_tot > _EPS else 1.0

    # Accélération : terme quadratique d'un ajustement degré 2 (si >= 3 points).
    acceleration = 0.0
    if n >= 3:
        c2, c1, _c0 = np.polyfit(tc, log_v, 2)
        acceleration = float(2.0 * c2)  # d²/dt² d'un polynôme a t² => 2a

    return TrendFeatures(
        level=level,
        log_level=log_level,
        velocity=velocity,
        acceleration=acceleration,
        volatility=volatility,
        r2=max(0.0, min(1.0, r2)),
        n_points=n,
        span_days=span,
    )


def robust_zscores(x: np.ndarray) -> np.ndarray:
    """Z-scores robustes (médiane / MAD), insensibles aux valeurs extrêmes.

    Le e-commerce a une distribution très asymétrique (quelques best-sellers
    écrasent tout) : médiane et MAD sont bien plus stables que moyenne/écart-type.
    """
    x = np.asarray(x, dtype=float)
    med = np.median(x)
    mad = np.median(np.abs(x - med))
    scale = _MAD_SCALE * mad
    if scale < _EPS:  # série quasi-constante : pas de dispersion -> z = 0
        return np.zeros_like(x)
    return (x - med) / scale


def percentile_rank(x: np.ndarray) -> np.ndarray:
    """Rang-percentile empirique dans [0,1] (interprétable directement)."""
    x = np.asarray(x, dtype=float)
    if x.size == 0:
        return x
    order = x.argsort()
    ranks = np.empty_like(order, dtype=float)
    ranks[order] = np.arange(x.size)
    return ranks / max(1, x.size - 1)


def detect_anomaly(features: TrendFeatures, z_velocity: float, threshold: float = 3.5) -> bool:
    """Signale un mouvement anormal (z de vélocité au-delà du seuil).

    Un pic isolé peut être un bug de données OU une vraie viralité. On le marque
    ici ; la distinction se fait en aval par *corroboration inter-sources*
    (cf. scoring) : un pic réel apparaît sur plusieurs sources indépendantes.
    """
    return abs(z_velocity) > threshold
