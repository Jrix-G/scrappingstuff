"""Comportement temporel d'apparence humaine.

Les bots se trahissent par des délais trop réguliers. On utilise une loi Beta
pour produire des pauses asymétriques (souvent courtes, parfois longues), plus
proches d'un humain qu'un ``uniform``.
"""

from __future__ import annotations

import asyncio
import random


def human_delay(min_seconds: float, max_seconds: float) -> float:
    """Tire un délai non uniforme dans ``[min_seconds, max_seconds]``."""
    span = max(0.0, max_seconds - min_seconds)
    # Beta(2,5) : densité concentrée vers le bas, longue traîne vers le haut.
    return min_seconds + random.betavariate(2, 5) * span


async def human_pause(min_seconds: float, max_seconds: float) -> None:
    """Attend un délai d'apparence humaine (asynchrone)."""
    await asyncio.sleep(human_delay(min_seconds, max_seconds))
