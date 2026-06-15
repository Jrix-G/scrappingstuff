"""Modèles de features et construction depuis les historiques bruts.

Une *source* fournit une série temporelle (ventes, recherches Google, mentions
Reddit...). On la transforme en :class:`TrendFeatures` (niveau, vélocité,
accélération, volatilité) via :mod:`signals.timeseries`, puis on regroupe toutes
les sources d'un produit dans :class:`ProductFeatures`. Le scoring travaille
ensuite sur une *population* de ``ProductFeatures`` (calculs transversaux).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .timeseries import TrendFeatures, extract_trend

# --- Catalogue des signaux ------------------------------------------------
# direction = +1 : une hausse est positive (ventes, mentions...).
# direction = -1 : une hausse est négative (Amazon BSR : rang bas = mieux).
SIGNALS: dict[str, int] = {
    "sales": +1,            # ventes réelles (AliExpress tradeDesc / CJ)
    "cj_listings": +1,      # nb de vendeurs CJ listant le produit (adoption offre)
    # NB: "ebay_listings" retiré (compte eBay banni) — collecteur ebay_browse.py
    # gardé dormant sur disque, à réactiver ici si un autre compte eBay apparaît.
    "google_trends": +1,    # volume de recherche
    "reddit": +1,           # mentions Reddit
    "tiktok": +1,           # vues / posts TikTok
    "youtube": +1,          # YouTube Shorts
    "pinterest": +1,        # épingles Pinterest
    "amazon_bsr": -1,       # Best Sellers Rank (inversé)
}

# Sources organiques « précoces » : leur mouvement précède la demande de masse.
EARLY_SOURCES = frozenset({"reddit", "tiktok", "youtube", "pinterest", "google_trends"})


@dataclass(slots=True)
class RawSignal:
    """Série brute d'une source pour un produit."""

    name: str
    timestamps_days: list[float]
    values: list[float]


@dataclass(slots=True)
class ProductFeatures:
    """Toutes les features d'un produit, prêtes pour le scoring transversal."""

    product_id: str
    signals: dict[str, TrendFeatures] = field(default_factory=dict)
    age_days: float | None = None        # âge estimé du produit
    seller_count: int | None = None      # nb de vendeurs (saturation offre)
    review_count: int | None = None      # nb d'avis (saturation demande)

    @property
    def available_sources(self) -> set[str]:
        """Sources réellement présentes et exploitables pour ce produit."""
        return {name for name, tf in self.signals.items() if tf.n_points >= 2}


def build_product_features(
    product_id: str,
    raw_signals: list[RawSignal],
    age_days: float | None = None,
    seller_count: int | None = None,
    review_count: int | None = None,
) -> ProductFeatures:
    """Construit un :class:`ProductFeatures` depuis les séries brutes.

    Les sources inconnues (hors :data:`SIGNALS`) sont ignorées silencieusement,
    ce qui rend le système tolérant à l'ajout/retrait de sources.
    """
    features: dict[str, TrendFeatures] = {}
    for raw in raw_signals:
        if raw.name not in SIGNALS:
            continue
        features[raw.name] = extract_trend(raw.timestamps_days, raw.values)
    return ProductFeatures(
        product_id=product_id,
        signals=features,
        age_days=age_days,
        seller_count=seller_count,
        review_count=review_count,
    )
