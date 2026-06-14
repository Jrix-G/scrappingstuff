"""Classification du cycle de vie d'un produit.

La phase est une fonction *déterministe* du triplet (niveau, vélocité,
accélération), donc entièrement explicable. Logique :

                      vélocité (croissance mensuelle g_m)
                      décroît        plat           croît
    niveau bas    │  DECLINING   │  MATURE*    │ EMERGENT / EARLY_GROWTH
    niveau moyen  │  DECLINING   │  MATURE     │ GROWTH
    niveau haut   │  DECLINING   │  MATURE     │ PEAK (si accél. <= 0)

(*) bas + plat = produit qui n'a jamais décollé : traité comme MATURE/inerte.

EMERGENT vs EARLY_GROWTH : EMERGENT = très tôt (niveau bas, accélération
positive, historique court) ; EARLY_GROWTH = la croissance s'est confirmée.
"""

from __future__ import annotations

from enum import Enum

from .config import PhaseThresholds, DEFAULT_THRESHOLDS


class Phase(str, Enum):
    EMERGENT = "EMERGENT"
    EARLY_GROWTH = "EARLY_GROWTH"
    GROWTH = "GROWTH"
    PEAK = "PEAK"
    MATURE = "MATURE"
    DECLINING = "DECLINING"


def classify_phase(
    monthly_growth: float,
    acceleration: float,
    level_pct: float,
    history_days: float,
    thresholds: PhaseThresholds = DEFAULT_THRESHOLDS,
) -> Phase:
    """Attribue une phase à partir des dérivées et du niveau relatif.

    Args:
        monthly_growth: croissance mensuelle implicite (0.5 = +50 %).
        acceleration: dérivée seconde du log (signe surtout pertinent).
        level_pct: rang-percentile du niveau dans la population [0,1].
        history_days: durée d'historique disponible.
        thresholds: seuils configurables.
    """
    t = thresholds

    # Déclin : la vélocité est nettement négative.
    if monthly_growth < -t.flat_monthly_growth:
        return Phase.DECLINING

    # Plat : ni hausse ni baisse marquée -> produit installé ou inerte.
    if monthly_growth <= t.flat_monthly_growth:
        return Phase.MATURE

    # À partir d'ici : croissance positive.
    # Sommet : niveau très élevé et l'accélération retombe (décélère).
    if level_pct >= t.high_level_pct and acceleration <= 0:
        return Phase.PEAK

    # Émergent : encore bas, accélère, et historique court (signal le plus précoce).
    if (
        level_pct <= t.low_level_pct
        and acceleration > 0
        and history_days <= t.emergent_max_history_days
    ):
        return Phase.EMERGENT

    # Début de croissance : bas/moyen, croissance forte, n'accélère plus à la baisse.
    if level_pct <= 0.5 and monthly_growth >= t.strong_monthly_growth and acceleration >= 0:
        return Phase.EARLY_GROWTH

    # Sinon : croissance « classique » (niveau déjà significatif, progresse encore).
    return Phase.GROWTH


# Phases que l'outil met en avant (avant saturation commerciale).
TARGET_PHASES = frozenset({Phase.EMERGENT, Phase.EARLY_GROWTH})
