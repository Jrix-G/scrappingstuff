"""
Module de logging Discord pour le pipeline Tandor.

Usage minimal :
    from utils.discord_logger import discord, DiscordHandler
    discord.daily_report(collected=5000, new=312, errors=4)
    discord.alert("Amazon", "IP captcha détecté")
    discord.info("demand_runner redémarré")

Le module est silencieux si DISCORD_WEBHOOK_URL n'est pas défini
(ne plante jamais le scraper).
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone

import requests

WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
_RATE_LIMIT_DELAY = 2.0  # secondes entre deux envois (bien en dessous du limit 30/60s)


# ── Envoi HTTP ────────────────────────────────────────────────────────────────

def _send(payload: dict, retries: int = 3) -> None:
    if not WEBHOOK_URL:
        return
    for attempt in range(retries):
        try:
            r = requests.post(WEBHOOK_URL, json=payload, timeout=10)
            if r.status_code == 429:
                wait = float(r.json().get("retry_after", 5))
                time.sleep(wait)
                continue
            r.raise_for_status()
            time.sleep(_RATE_LIMIT_DELAY)
            return
        except Exception:
            time.sleep(2 ** attempt)


def _embed(title: str, description: str = "", color: int = 0x3498DB,
           fields: list[dict] | None = None) -> None:
    e: dict = {
        "title": title,
        "color": color,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "footer": {"text": "Tandor Pi"},
    }
    if description:
        e["description"] = description
    if fields:
        e["fields"] = fields
    _send({"embeds": [e]})


# ── API publique ──────────────────────────────────────────────────────────────

class _Discord:
    """Interface de haut niveau pour les logs Discord."""

    # vert — rapport quotidien
    def daily_report(self, collected: int, new: int, errors: int,
                     amazon_done: int = 0, trends_cached: int = 0) -> None:
        _embed(
            title="Rapport Quotidien",
            color=0x2ECC71,
            fields=[
                {"name": "Produits CJ collectés", "value": str(collected),    "inline": True},
                {"name": "Nouveaux",               "value": str(new),          "inline": True},
                {"name": "Erreurs",                "value": str(errors),       "inline": True},
                {"name": "Amazon scanned",         "value": str(amazon_done),  "inline": True},
                {"name": "Trends en cache",        "value": str(trends_cached),"inline": True},
            ],
        )

    # rouge — alerte critique
    def alert(self, source: str, message: str, ping: bool = False) -> None:
        prefix = "@here\n" if ping else ""
        _embed(
            title=f"ALERTE — {source}",
            description=f"{prefix}```{message[:1800]}```",
            color=0xE74C3C,
        )

    # bleu — info routinière
    def info(self, message: str) -> None:
        _embed(title="Info", description=message, color=0x3498DB)

    # orange — avertissement
    def warning(self, message: str) -> None:
        _embed(title="Avertissement", description=message, color=0xF39C12)

    # jaune — démarrage serveur
    def startup(self, components: list[str]) -> None:
        status = "\n".join(f"• {c}" for c in components)
        _embed(
            title="Tandor Pi — Démarrage",
            description=f"Composants actifs :\n{status}",
            color=0xF1C40F,
        )


discord = _Discord()


# ── Handler logging standard ──────────────────────────────────────────────────

class DiscordHandler(logging.Handler):
    """Branche les logs Python WARNING+ sur Discord sans jamais planter."""

    _COLORS = {
        logging.DEBUG:    0x95A5A6,
        logging.INFO:     0x3498DB,
        logging.WARNING:  0xF39C12,
        logging.ERROR:    0xE74C3C,
        logging.CRITICAL: 0x8E44AD,
    }

    def __init__(self, min_level: int = logging.WARNING):
        super().__init__(min_level)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            _embed(
                title=record.levelname,
                description=self.format(record)[:2000],
                color=self._COLORS.get(record.levelno, 0xFFFFFF),
            )
        except Exception:
            pass  # logging ne doit jamais propager vers le scraper
