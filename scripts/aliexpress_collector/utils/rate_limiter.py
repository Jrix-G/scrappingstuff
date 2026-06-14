"""Limiteur de débit asynchrone simple (token-bucket minimal).

Garantit un intervalle minimal entre deux acquisitions, quel que soit l'endroit
d'où on appelle. ``run.py`` espace déjà les fiches via ``human_pause`` ; ce
limiteur est fourni pour les usages où plusieurs tâches partagent un même quota.
"""

from __future__ import annotations

import asyncio
import time


class RateLimiter:
    """Borne le débit à au plus une acquisition par ``min_interval`` secondes."""

    def __init__(self, min_interval: float) -> None:
        self._min_interval = max(0.0, min_interval)
        self._last = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Attend si nécessaire pour respecter l'intervalle minimal."""
        async with self._lock:
            wait = self._min_interval - (time.monotonic() - self._last)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last = time.monotonic()
