"""Modèle de données normalisé d'un produit.

Un seul schéma fait foi dans tout le pipeline : les extracteurs produisent des
:class:`Product`, le stockage les consomme. Le couplage faible passe par ce
contrat typé plutôt que par des dictionnaires anonymes.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class Product:
    """Représentation normalisée d'un produit AliExpress.

    ``product_id`` est la clé d'unicité (dédup et reprise). Les champs absents
    restent ``None`` plutôt que d'être inventés : l'absence est une information.
    """

    product_id: str
    title: str | None = None
    price: float | None = None
    currency: str | None = None
    original_price: float | None = None
    rating: float | None = None
    reviews_count: int | None = None
    orders_count: int | None = None
    seller: str | None = None
    url: str | None = None
    images: list[str] = field(default_factory=list)
    variants: list[str] = field(default_factory=list)
    category: str | None = None
    description: str | None = None
    available: bool | None = None
    source: str = "aliexpress"
    collected_at: str = field(default_factory=_utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        """Sérialise en dict prêt pour JSON/SQLite."""
        return asdict(self)

    def merge(self, other: "Product") -> "Product":
        """Fusionne deux vues d'un même produit (listing + fiche détaillée).

        ``self`` est prioritaire ; ``other`` ne comble que les trous. Utile
        pour enrichir une fiche listing avec les données de la page produit
        sans écraser ce qu'on avait déjà.
        """
        if other.product_id != self.product_id:
            raise ValueError("Fusion de deux produits d'identifiants différents.")
        merged = self.to_dict()
        for key, value in other.to_dict().items():
            current = merged.get(key)
            is_empty = current in (None, "", [], 0)
            if is_empty and value not in (None, "", []):
                merged[key] = value
        return Product(**merged)
