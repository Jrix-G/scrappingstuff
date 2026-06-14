"""Accès aux données pour l'API (interface + implémentation mémoire).

L'API ne dépend que de l'interface :class:`Repository`. La prod fournira une
implémentation SQLite/Postgres lisant ``signal_history`` et reconstruisant les
``ProductFeatures`` ; l'implémentation mémoire sert aux tests et démos.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from signals.features import ProductFeatures


@runtime_checkable
class Repository(Protocol):
    """Contrat de persistance consommé par l'API."""

    def load_population(self) -> list[ProductFeatures]:
        """Charge tous les produits avec leurs features (pour le scoring transversal)."""
        ...

    def load_history(self, product_id: str) -> dict[str, list[dict[str, Any]]]:
        """Historique brut des signaux d'un produit (pour les graphes)."""
        ...

    def load_alerts(self, undelivered_only: bool = True) -> list[dict[str, Any]]:
        """Alertes en attente."""
        ...


class InMemoryRepository:
    """Implémentation mémoire (tests/démo)."""

    def __init__(self) -> None:
        self._population: list[ProductFeatures] = []
        self._history: dict[str, dict[str, list[dict[str, Any]]]] = {}
        self._alerts: list[dict[str, Any]] = []

    def set_population(self, population: list[ProductFeatures]) -> None:
        self._population = population

    def load_population(self) -> list[ProductFeatures]:
        return self._population

    def load_history(self, product_id: str) -> dict[str, list[dict[str, Any]]]:
        return self._history.get(product_id, {})

    def load_alerts(self, undelivered_only: bool = True) -> list[dict[str, Any]]:
        if undelivered_only:
            return [a for a in self._alerts if not a.get("delivered")]
        return self._alerts
