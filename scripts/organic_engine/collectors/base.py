"""Interface commune des collecteurs de signaux.

Chaque source (AliExpress, CJ, Reddit, TikTok...) implémente ce contrat. Le
moteur reste découplé des collecteurs : ajouter/retirer une source ne touche
ni au scoring ni à l'API. La résilience « fonctionne même si une source est
indisponible » est garantie par ``collect`` qui renvoie une liste vide (jamais
d'exception propagée) en cas d'échec.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable


@dataclass(slots=True)
class SignalPoint:
    """Une observation : (produit, source, instant, valeur)."""

    external_id: str
    source: str
    observed_at: datetime
    value: float


@runtime_checkable
class Collector(Protocol):
    """Contrat d'un collecteur de signal."""

    name: str               # nom de la source (clé dans signals.features.SIGNALS)

    def is_available(self) -> bool:
        """Vrai si la source est joignable (sinon le moteur la saute)."""
        ...

    def collect(self, keywords: list[str]) -> list[SignalPoint]:
        """Collecte les points de signal ; renvoie [] en cas d'échec (jamais d'exception)."""
        ...
