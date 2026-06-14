"""Contrat commun à toutes les implémentations de stockage.

Le reste du pipeline ne connaît que cette interface : on peut donc basculer
SQLite/JSON sans toucher au collecteur (principe d'inversion de dépendance).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from core.models import Product


@runtime_checkable
class Storage(Protocol):
    """Interface de persistance des produits."""

    def known_ids(self) -> set[str]:
        """Renvoie les identifiants déjà stockés (pour dédup et reprise)."""
        ...

    def upsert(self, product: Product) -> bool:
        """Insère ou met à jour un produit.

        Returns:
            ``True`` si le produit était nouveau, ``False`` si déjà connu.
        """
        ...

    def count(self) -> int:
        """Nombre total de produits stockés."""
        ...

    def close(self) -> None:
        """Libère les ressources sous-jacentes."""
        ...
