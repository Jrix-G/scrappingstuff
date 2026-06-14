"""Hyperparamètres du scoring.

POINT MÉTHODOLOGIQUE CENTRAL — pourquoi ce ne sont PAS des poids arbitraires :

En l'absence de données d'issue (phase de démarrage à froid, aucun produit n'a
encore d'historique « a-t-il explosé ? »), on ne PEUT PAS apprendre les poids.
On utilise donc un **prior à maximum d'entropie** : à information nulle, le choix
le moins biaisé est l'équipondération des features normalisées. Ce prior est
explicitement temporaire.

Dès que des issues sont observées (cf. :mod:`analytics.learning`), une régression
logistique régularisée REMPLACE ces constantes par des coefficients appris et
validés. Les ``WeightSet`` ci-dessous portent un ``source`` qui trace l'origine
(« prior » vs « learned:v3 ») pour l'auditabilité.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class WeightSet:
    """Jeu de poids du score, avec traçabilité de son origine."""

    # Décomposition vélocité / accélération dans le momentum (somme = 1).
    w_velocity: float = 0.5
    w_acceleration: float = 0.5

    # Pénalité de maturité : à quel point un niveau/âge élevé déclasse le produit.
    # lambda contrôle l'arbitrage « croissance précoce » vs « déjà installé ».
    lambda_maturity: float = 0.6

    # Bonus de corroboration : un mouvement confirmé par plusieurs sources
    # indépendantes est statistiquement bien plus crédible (cf. DESIGN.md).
    corroboration_bonus: float = 0.15

    # Poids relatif des sources organiques précoces dans le momentum.
    early_source_boost: float = 1.3

    source: str = "prior:max-entropy"
    feature_weights: dict[str, float] = field(default_factory=dict)


# Seuils de classification de phase, exprimés en grandeurs interprétables.
@dataclass(slots=True)
class PhaseThresholds:
    """Seuils de la classification de phase (cf. scoring.phases)."""

    flat_monthly_growth: float = 0.05    # |g_m| < 5 %/mois => plat
    strong_monthly_growth: float = 0.30  # g_m > 30 %/mois => forte croissance
    low_level_pct: float = 0.35          # percentile de niveau « bas »
    high_level_pct: float = 0.85         # percentile de niveau « élevé »
    emergent_max_history_days: float = 45.0


DEFAULT_WEIGHTS = WeightSet()
DEFAULT_THRESHOLDS = PhaseThresholds()
