"""File d'attente de priorité du scraping demande (Amazon primaire + AliExpress confirmation).

Logique « pile » demandée :
1. On part de TOUS les produits CJ (cj_products) → mots-clés dédoublonnés.
2. **Cold start** : on scrape Amazon pour chaque mot-clé jamais vu, en commençant par
   ceux qui couvrent le PLUS de produits CJ (couverture maximale d'abord).
3. **Régime permanent** : on rafraîchit en priorité les mots-clés à FORTE vélocité
   (produits intéressants), rarement les mauvais (vélocité faible/nulle).
4. **Passerelle AliExpress** : dès qu'un mot-clé dépasse un seuil de vélocité Amazon,
   on l'empile pour confirmation AliExpress (budget rare ~250/jour, dépensé sur les tops).

Tout est persisté dans cj.db → le runner 24/7 est resumable (reprend où il s'est arrêté).
"""
from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ENGINE = Path(__file__).resolve().parent
sys.path.insert(0, str(ENGINE))
from vpn_warmer import _keyword  # même extraction de mots-clés que le reste du pipeline

DB = ENGINE / "data" / "cj.db"

# Seuils de rafraîchissement selon la vélocité Amazon (heures avant de re-scraper).
REFRESH_HOT_H = 24            # produit chaud (>=5000 bought/mois) → tous les jours
REFRESH_WARM_H = 72          # tiède (>=500) → tous les 3 jours
REFRESH_COLD_H = 168         # froid (<500 ou rien) → 1×/semaine
HOT_THRESHOLD = 5000
WARM_THRESHOLD = 500
ALI_THRESHOLD = 2000         # vélocité Amazon min pour mériter une confirmation AliExpress


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect() -> sqlite3.Connection:
    c = sqlite3.connect(DB, timeout=30)
    c.execute("PRAGMA journal_mode=WAL")
    return c


def init_schema(c: sqlite3.Connection) -> None:
    c.executescript(
        """
        CREATE TABLE IF NOT EXISTS amazon_snapshots (
            keyword TEXT, observed_at TEXT, max_bought INTEGER,
            median_bought INTEGER, n_with_velocity INTEGER, n_results INTEGER
        );
        CREATE INDEX IF NOT EXISTS idx_amzsnap_kw ON amazon_snapshots(keyword);

        CREATE TABLE IF NOT EXISTS amazon_queue (
            keyword TEXT PRIMARY KEY,
            n_products INTEGER DEFAULT 1,
            last_scraped TEXT,
            scrape_count INTEGER DEFAULT 0,
            last_max_bought INTEGER,
            last_median_bought INTEGER,
            blocked_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending'
        );

        CREATE TABLE IF NOT EXISTS aliexpress_queue (
            keyword TEXT PRIMARY KEY,
            enqueued_at TEXT,
            priority REAL DEFAULT 0,
            last_scraped TEXT,
            scrape_count INTEGER DEFAULT 0
        );
        """
    )
    c.commit()


def rebuild_from_cj(c: sqlite3.Connection) -> int:
    """(Re)construit la file Amazon depuis cj_products. Idempotent : conserve l'état
    des mots-clés déjà scrapés, n'insère que les nouveaux en 'pending'."""
    rows = c.execute("SELECT name FROM cj_products WHERE name IS NOT NULL").fetchall()
    counts: dict[str, int] = {}
    for (name,) in rows:
        kw = _keyword(name)
        if kw and len(kw) >= 4:
            counts[kw] = counts.get(kw, 0) + 1
    added = 0
    for kw, n in counts.items():
        cur = c.execute(
            "INSERT INTO amazon_queue(keyword, n_products) VALUES(?,?) "
            "ON CONFLICT(keyword) DO UPDATE SET n_products=excluded.n_products",
            (kw, n),
        )
        if cur.rowcount and c.execute(
            "SELECT scrape_count FROM amazon_queue WHERE keyword=?", (kw,)
        ).fetchone()[0] == 0:
            added += 1
    c.commit()
    return len(counts)


def _refresh_interval_h(max_bought: int | None) -> int:
    if max_bought is None:
        return REFRESH_COLD_H
    if max_bought >= HOT_THRESHOLD:
        return REFRESH_HOT_H
    if max_bought >= WARM_THRESHOLD:
        return REFRESH_WARM_H
    return REFRESH_COLD_H


def next_amazon_keyword(c: sqlite3.Connection) -> str | None:
    """Prochain mot-clé Amazon à scraper : pending (couverture max) puis refresh dû
    (vélocité décroissante)."""
    # 1. Cold start : jamais scrapé, le plus de produits couverts d'abord.
    row = c.execute(
        "SELECT keyword FROM amazon_queue WHERE scrape_count=0 "
        "ORDER BY n_products DESC LIMIT 1"
    ).fetchone()
    if row:
        return row[0]
    # 2. Refresh : dû selon la vélocité, les plus chauds d'abord.
    now = datetime.now(timezone.utc)
    cand = c.execute(
        "SELECT keyword, last_scraped, last_max_bought FROM amazon_queue "
        "WHERE last_scraped IS NOT NULL ORDER BY last_max_bought DESC NULLS LAST"
    ).fetchall()
    for kw, last, mx in cand:
        try:
            age_h = (now - datetime.fromisoformat(last)).total_seconds() / 3600
        except Exception:
            age_h = 1e9
        if age_h >= _refresh_interval_h(mx):
            return kw
    return None


def record_amazon(c: sqlite3.Connection, demand) -> None:
    """Enregistre un snapshot Amazon + met à jour la file ; empile sur AliExpress si top."""
    kw = demand.keyword
    if demand.blocked:
        c.execute("UPDATE amazon_queue SET blocked_count=blocked_count+1 WHERE keyword=?", (kw,))
        c.commit()
        return
    c.execute(
        "INSERT INTO amazon_snapshots(keyword, observed_at, max_bought, median_bought, "
        "n_with_velocity, n_results) VALUES(?,?,?,?,?,?)",
        (kw, _now(), demand.max_bought, demand.median_bought,
         demand.n_with_velocity, demand.n_results),
    )
    c.execute(
        "UPDATE amazon_queue SET last_scraped=?, scrape_count=scrape_count+1, "
        "last_max_bought=?, last_median_bought=?, status='done' WHERE keyword=?",
        (_now(), demand.max_bought, demand.median_bought, kw),
    )
    # Passerelle AliExpress : top vélocité → confirmation.
    if (demand.max_bought or 0) >= ALI_THRESHOLD:
        c.execute(
            "INSERT INTO aliexpress_queue(keyword, enqueued_at, priority) VALUES(?,?,?) "
            "ON CONFLICT(keyword) DO UPDATE SET priority=excluded.priority",
            (kw, _now(), float(demand.max_bought or 0)),
        )
    c.commit()


def next_aliexpress_keyword(c: sqlite3.Connection, min_age_h: int = 24) -> str | None:
    """Prochain mot-clé AliExpress : top vélocité jamais confirmé, ou re-confirmation due."""
    now = datetime.now(timezone.utc)
    cand = c.execute(
        "SELECT keyword, last_scraped FROM aliexpress_queue ORDER BY priority DESC"
    ).fetchall()
    for kw, last in cand:
        if last is None:
            return kw
        try:
            age_h = (now - datetime.fromisoformat(last)).total_seconds() / 3600
        except Exception:
            age_h = 1e9
        if age_h >= min_age_h:
            return kw
    return None


def record_aliexpress(c: sqlite3.Connection, keyword: str) -> None:
    c.execute(
        "UPDATE aliexpress_queue SET last_scraped=?, scrape_count=scrape_count+1 WHERE keyword=?",
        (_now(), keyword),
    )
    c.commit()


def stats(c: sqlite3.Connection) -> dict:
    total = c.execute("SELECT COUNT(*) FROM amazon_queue").fetchone()[0]
    done = c.execute("SELECT COUNT(*) FROM amazon_queue WHERE scrape_count>0").fetchone()[0]
    pending = total - done
    ali = c.execute("SELECT COUNT(*) FROM aliexpress_queue").fetchone()[0]
    hot = c.execute(
        "SELECT COUNT(*) FROM amazon_queue WHERE last_max_bought>=?", (HOT_THRESHOLD,)
    ).fetchone()[0]
    return {"total_keywords": total, "scraped": done, "pending": pending,
            "aliexpress_queued": ali, "hot_products": hot}


if __name__ == "__main__":  # python3 demand_queue.py  → init + stats
    c = connect()
    init_schema(c)
    n = rebuild_from_cj(c)
    print(f"File Amazon (re)construite : {n} mots-clés uniques depuis cj_products")
    print("Stats:", stats(c))
