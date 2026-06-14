"""Moteur de score organique composite (transversal à une population).

Le score répond à : « probabilité qu'un produit connaisse une forte croissance
organique dans les prochaines semaines ? » — c'est-à-dire qu'il privilégie
l'ACCÉLÉRATION à BAS NIVEAU (croissance précoce), pas la popularité actuelle.

Pipeline mathématique (détaillé dans DESIGN.md) :

1. Normalisation robuste (médiane/MAD) de chaque feature (vélocité, accélération,
   niveau) TRANSVERSALEMENT à la population -> z-scores comparables.
2. MOMENTUM = agrégat pondéré des z(vélocité) et z(accélération) sur les sources
   disponibles, avec boost des sources organiques précoces, pondéré par la
   fiabilité de chaque série (R², volatilité).
3. CORROBORATION = nb de sources indépendantes en hausse -> multiplicateur
   (un mouvement confirmé par plusieurs sources est peu probable sous le bruit).
4. MATURITÉ = z(niveau de ventes, âge, nb vendeurs, saturation des avis).
5. SCORE BRUT = momentum·corroboration − λ·max(0, maturité).
6. SCORE FINAL 0-100 = rang-percentile du score brut dans la population
   (interprétable : « top X % du potentiel organique actuel »).
7. CONFIANCE [0,1] = couverture des sources × adéquation d'historique ×
   (1 − volatilité) × corroboration. Rapportée SÉPARÉMENT du score.

Chaque score est entièrement décomposable : la contribution de chaque source est
exposée pour l'explicabilité.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from signals.features import EARLY_SOURCES, SIGNALS, ProductFeatures
from signals.timeseries import TrendFeatures, percentile_rank, robust_zscores

from .config import DEFAULT_WEIGHTS, DEFAULT_THRESHOLDS, PhaseThresholds, WeightSet
from .phases import Phase, classify_phase

_EPS = 1e-9
# Seuil de croissance mensuelle au-delà duquel une source compte comme « en hausse »
# pour la corroboration (5 %/mois).
_CORRO_MIN_GROWTH = 0.05


@dataclass(slots=True)
class SignalContribution:
    """Contribution explicable d'une source au momentum d'un produit."""

    source: str
    z_velocity: float
    z_acceleration: float
    weight: float
    contribution: float

    def explain(self) -> str:
        """Phrase lisible pour l'utilisateur final."""
        direction = "↑" if self.contribution >= 0 else "↓"
        return (
            f"{direction} {self.source} : vélocité {self.z_velocity:+.1f}σ, "
            f"accélération {self.z_acceleration:+.1f}σ "
            f"(contribution {self.contribution:+.2f})"
        )


@dataclass(slots=True)
class ScoreResult:
    """Résultat complet et explicable du scoring d'un produit."""

    product_id: str
    organic_score: float          # 0-100, rang-percentile dans la population
    confidence: float             # 0-1, fiabilité du score
    phase: Phase
    momentum: float               # composante momentum (z)
    maturity: float               # composante maturité (z)
    corroboration: int            # nb de sources indépendantes en hausse
    monthly_growth: float         # croissance mensuelle représentative
    contributions: list[SignalContribution] = field(default_factory=list)

    def top_reasons(self, k: int = 3) -> list[str]:
        """Les k principales raisons (positives) du score."""
        ranked = sorted(self.contributions, key=lambda c: c.contribution, reverse=True)
        return [c.explain() for c in ranked[:k] if c.contribution > 0]


def _reliability(tf: TrendFeatures) -> float:
    """Poids de fiabilité d'une série : récompense R² élevé et faible volatilité."""
    vol_factor = 1.0 / (1.0 + tf.volatility)
    points_factor = min(1.0, tf.n_points / 6.0)
    return max(0.05, tf.r2 * vol_factor * points_factor)


def _stack(population: list[ProductFeatures], source: str, attr: str) -> np.ndarray:
    """Vecteur (longueur=population) d'un attribut de feature, NaN si absent."""
    out = np.full(len(population), np.nan)
    for i, pf in enumerate(population):
        tf = pf.signals.get(source)
        if tf is not None and tf.n_points >= 2:
            out[i] = getattr(tf, attr)
    return out


def _zscore_with_nan(values: np.ndarray) -> np.ndarray:
    """Z-scores robustes calculés sur le sous-ensemble disponible (NaN -> 0)."""
    mask = ~np.isnan(values)
    out = np.zeros_like(values)
    if mask.sum() >= 2:
        out[mask] = robust_zscores(values[mask])
    return out


def score_population(
    population: list[ProductFeatures],
    weights: WeightSet = DEFAULT_WEIGHTS,
    thresholds: PhaseThresholds = DEFAULT_THRESHOLDS,
) -> list[ScoreResult]:
    """Score une population entière de produits (calculs transversaux).

    Le score est RELATIF à la population fournie : passer tout l'univers produit
    en une fois donne des percentiles cohérents.
    """
    n = len(population)
    if n == 0:
        return []

    # 1) z-scores transversaux par source (vélocité & accélération, ajustés du sens).
    z_vel: dict[str, np.ndarray] = {}
    z_acc: dict[str, np.ndarray] = {}
    for source, direction in SIGNALS.items():
        vel = _stack(population, source, "velocity") * direction
        acc = _stack(population, source, "acceleration") * direction
        z_vel[source] = _zscore_with_nan(vel)
        z_acc[source] = _zscore_with_nan(acc)

    # 2) Momentum par produit + contributions explicables.
    momentum = np.zeros(n)
    corroboration = np.zeros(n, dtype=int)
    contributions: list[list[SignalContribution]] = [[] for _ in range(n)]

    for i, pf in enumerate(population):
        total_w = 0.0
        acc_momentum = 0.0
        for source in pf.available_sources:
            tf = pf.signals[source]
            direction = SIGNALS[source]
            zv, za = z_vel[source][i], z_acc[source][i]
            boost = weights.early_source_boost if source in EARLY_SOURCES else 1.0
            rel = _reliability(tf)
            w = rel * boost
            signal_momentum = weights.w_velocity * zv + weights.w_acceleration * za
            contrib = w * signal_momentum
            acc_momentum += contrib
            total_w += w
            # Corroboration = propriété INTRA-produit : cette source monte-t-elle
            # réellement (croissance mensuelle nette, sens ajusté) ? Indépendant
            # de la population, donc stable quelle que soit sa taille.
            adj_monthly_growth = np.exp(direction * tf.velocity * 30.0) - 1.0
            if adj_monthly_growth > _CORRO_MIN_GROWTH:
                corroboration[i] += 1
            contributions[i].append(
                SignalContribution(source, float(zv), float(za), float(w), float(contrib))
            )
        momentum[i] = acc_momentum / (total_w + _EPS)

    # 3) Multiplicateur de corroboration (n'amplifie que le momentum positif).
    corro_factor = 1.0 + weights.corroboration_bonus * np.maximum(0, corroboration - 1)
    momentum_adj = np.where(momentum > 0, momentum * corro_factor, momentum)

    # 4) Maturité : niveau de ventes + âge + vendeurs + saturation avis.
    maturity = _maturity_scores(population)

    # 5) Score brut : momentum pénalisé par l'excès de maturité.
    organic_raw = momentum_adj - weights.lambda_maturity * np.maximum(0.0, maturity)

    # 6) Score final 0-100 = rang-percentile dans la population.
    final = 100.0 * percentile_rank(organic_raw)

    # 7) Confiance + phase, par produit.
    sales_level = _stack(population, "sales", "log_level")
    level_pct_pop = _level_percentile(population)
    confidence = _confidence_scores(population, corroboration)

    results: list[ScoreResult] = []
    for i, pf in enumerate(population):
        growth, accel, hist = _representative_dynamics(pf)
        phase = classify_phase(growth, accel, level_pct_pop[i], hist, thresholds)
        results.append(
            ScoreResult(
                product_id=pf.product_id,
                organic_score=float(final[i]),
                confidence=float(confidence[i]),
                phase=phase,
                momentum=float(momentum_adj[i]),
                maturity=float(maturity[i]),
                corroboration=int(corroboration[i]),
                monthly_growth=float(growth),
                contributions=contributions[i],
            )
        )
    return results


def _maturity_scores(population: list[ProductFeatures]) -> np.ndarray:
    """z-score de maturité : haut = produit installé/saturé (à déclasser)."""
    n = len(population)
    sales_level = _stack(population, "sales", "log_level")
    age = np.array([pf.age_days if pf.age_days is not None else np.nan for pf in population])
    sellers = np.array(
        [pf.seller_count if pf.seller_count is not None else np.nan for pf in population]
    )
    reviews = np.array(
        [pf.review_count if pf.review_count is not None else np.nan for pf in population]
    )
    components = [
        _zscore_with_nan(sales_level),
        _zscore_with_nan(age),
        _zscore_with_nan(sellers),
        _zscore_with_nan(np.log1p(reviews)),
    ]
    # Moyenne des composantes disponibles (ici toutes ramenées à 0 si absentes).
    avail = np.zeros(n)
    total = np.zeros(n)
    for comp, src in zip(
        components, [sales_level, age, sellers, reviews]
    ):
        mask = ~np.isnan(src)
        avail += np.where(mask, comp, 0.0)
        total += mask.astype(float)
    return avail / np.maximum(1.0, total)


def _level_percentile(population: list[ProductFeatures]) -> np.ndarray:
    """Rang-percentile du niveau représentatif (ventes, sinon moyenne des sources)."""
    levels = np.zeros(len(population))
    for i, pf in enumerate(population):
        if "sales" in pf.signals and pf.signals["sales"].n_points >= 1:
            levels[i] = pf.signals["sales"].log_level
        elif pf.signals:
            levels[i] = float(np.mean([tf.log_level for tf in pf.signals.values()]))
    return percentile_rank(levels)


def _confidence_scores(population: list[ProductFeatures], corroboration: np.ndarray) -> np.ndarray:
    """Confiance [0,1] : couverture × historique × stabilité × corroboration."""
    total_sources = len(SIGNALS)
    conf = np.zeros(len(population))
    for i, pf in enumerate(population):
        avail = pf.available_sources
        if not avail:
            conf[i] = 0.0
            continue
        coverage = len(avail) / total_sources
        hist = np.mean([min(1.0, pf.signals[s].n_points / 6.0) for s in avail])
        stability = np.mean([1.0 / (1.0 + pf.signals[s].volatility) for s in avail])
        corro = min(1.0, 0.5 + 0.25 * corroboration[i])
        # Moyenne géométrique : une dimension faible plombe la confiance (prudence).
        conf[i] = float((coverage * hist * stability * corro) ** 0.25)
    return conf


def _representative_dynamics(pf: ProductFeatures) -> tuple[float, float, float]:
    """Croissance mensuelle, accélération et historique « représentatifs ».

    Priorité aux ventes (demande réelle) ; à défaut, moyenne des sources précoces.
    """
    if "sales" in pf.signals and pf.signals["sales"].n_points >= 2:
        tf = pf.signals["sales"]
        return tf.monthly_growth, tf.acceleration, tf.span_days
    early = [tf for s, tf in pf.signals.items() if s in EARLY_SOURCES and tf.n_points >= 2]
    if early:
        growth = float(np.mean([tf.monthly_growth for tf in early]))
        accel = float(np.mean([tf.acceleration for tf in early]))
        hist = float(np.max([tf.span_days for tf in early]))
        return growth, accel, hist
    return 0.0, 0.0, 0.0
