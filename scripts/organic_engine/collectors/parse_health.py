"""Détecteur de « collecte morte » (markup cassé) — santé des parseurs.

POURQUOI : tout le scraping repose sur des regex contre du HTML/JSON embarqué.
Quand une plateforme change son markup, le parseur ne lève PAS d'erreur : il
renvoie 0 résultat, qui est silencieusement enregistré comme « zéro demande ».
Le signal s'éteint sans bruit. Ce module sépare les deux cas qui se ressemblent :

  * page BLOQUÉE (rate-limit / captcha)  -> donnée indisponible, NORMAL et temporaire
  * page LISIBLE mais 0 EXTRAIT          -> signature d'un markup cassé, à ALERTER

On enregistre par source, pour chaque tentative, (readable, extracted). Si, sur
une fenêtre, le taux de pages lisibles portant ≥1 signal s'effondre sous un
plancher, on conclut que le parseur est mort. Best-effort : toute exception est
avalée pour ne JAMAIS interrompre le scraping.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

_DDL = """CREATE TABLE IF NOT EXISTS parse_health(
    source TEXT, observed_at TEXT, readable INTEGER, extracted INTEGER)"""

# Il faut un minimum de pages LISIBLES avant de conclure (sinon faux positif sur
# un petit échantillon), et on n'alerte que sous un plancher de rendement absolu.
MIN_READABLE = 30
DEAD_YIELD = 0.05  # <5 % des pages lisibles rendent un signal => parseur mort


def record(conn: sqlite3.Connection, source: str, readable: bool, extracted: int) -> None:
    """Enregistre une tentative de parse. Best-effort (jamais bloquant)."""
    try:
        conn.execute(_DDL)
        conn.execute(
            "INSERT INTO parse_health(source, observed_at, readable, extracted) "
            "VALUES(?,?,?,?)",
            (source, datetime.now(timezone.utc).isoformat(), int(bool(readable)), int(extracted or 0)),
        )
        conn.commit()
    except Exception:
        pass


def check(conn: sqlite3.Connection, hours: int = 24) -> list[dict]:
    """Sources dont le parseur semble mort sur la fenêtre. ``[]`` si tout va bien."""
    dead: list[dict] = []
    try:
        conn.execute(_DDL)
        since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        rows = conn.execute(
            "SELECT source, "
            "  SUM(readable) AS readable, "
            "  SUM(CASE WHEN readable=1 AND extracted>0 THEN 1 ELSE 0 END) AS with_signal "
            "FROM parse_health WHERE observed_at >= ? GROUP BY source",
            (since,),
        ).fetchall()
    except Exception:
        return dead
    for source, readable, with_signal in rows:
        readable = readable or 0
        with_signal = with_signal or 0
        if readable < MIN_READABLE:
            continue
        ratio = with_signal / readable
        if ratio <= DEAD_YIELD:
            dead.append({"source": source, "readable": readable,
                         "with_signal": with_signal, "yield": round(ratio, 3)})
    return dead
