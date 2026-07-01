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
from datetime import datetime, timedelta, timezone
from pathlib import Path

ENGINE = Path(__file__).resolve().parent
sys.path.insert(0, str(ENGINE))
from vpn_warmer import _keyword  # même extraction de mots-clés que le reste du pipeline
from shard import in_shard       # partition multi-nœuds : ne tirer que SON shard de mots-clés

DB = ENGINE / "data" / "cj.db"

# Seuils de rafraîchissement selon la vélocité Amazon (heures avant de re-scraper).
REFRESH_HOT_H = 24            # produit chaud (>=5000 bought/mois) → tous les jours
REFRESH_WARM_H = 72          # tiède (>=500) → tous les 3 jours
REFRESH_COLD_H = 168         # froid (<500 ou rien) → 1×/semaine
HOT_THRESHOLD = 5000
WARM_THRESHOLD = 500
ALI_THRESHOLD = 2000         # vélocité Amazon min pour mériter une confirmation AliExpress
SALES_THRESHOLD = 500        # vélocité Amazon min pour empiler une confirmation eBay/DHgate
SALES_QUEUES = ("ebay_queue", "dhgate_queue")   # files des sources de ventes secondaires


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

        -- Snapshots de signaux organiques précoces (alimentent le scoring via
        -- signals/db_signals.py). Mêmes conventions que amazon_snapshots :
        -- 1 ligne = 1 photo datée d'un mot-clé ; la vélocité se calcule sur ≥2 lignes.
        -- TikTok : view_count/video_count du hashtag (cf. tiktok_trending.py).
        CREATE TABLE IF NOT EXISTS tiktok_snapshots (
            keyword TEXT, observed_at TEXT,
            view_count INTEGER, video_count INTEGER,
            PRIMARY KEY (keyword, observed_at)
        );
        CREATE INDEX IF NOT EXISTS idx_tiktoksnap_kw ON tiktok_snapshots(keyword);

        -- Google Suggest (autocomplete) : score 0..100, saturation 0..1.
        -- direction = dérivée série-niveau (non per-snapshot) -> NULL au flush.
        CREATE TABLE IF NOT EXISTS suggest_snapshots (
            keyword TEXT, observed_at TEXT,
            score REAL, saturation REAL, direction REAL,
            PRIMARY KEY (keyword, observed_at)
        );
        CREATE INDEX IF NOT EXISTS idx_suggestsnap_kw ON suggest_snapshots(keyword);

        -- VAGUE 2 (tables créées maintenant, NON alimentées pour l'instant) :
        -- Reddit : nb de mentions + score agrégé par mot-clé.
        CREATE TABLE IF NOT EXISTS reddit_snapshots (
            keyword TEXT, observed_at TEXT,
            mentions INTEGER, score REAL,
            PRIMARY KEY (keyword, observed_at)
        );
        CREATE INDEX IF NOT EXISTS idx_redditsnap_kw ON reddit_snapshots(keyword);

        -- YouTube : nb de vidéos + total de vues par mot-clé.
        CREATE TABLE IF NOT EXISTS youtube_snapshots (
            keyword TEXT, observed_at TEXT,
            video_count INTEGER, view_count INTEGER,
            PRIMARY KEY (keyword, observed_at)
        );
        CREATE INDEX IF NOT EXISTS idx_youtubesnap_kw ON youtube_snapshots(keyword);

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

        CREATE TABLE IF NOT EXISTS ebay_queue (
            keyword TEXT PRIMARY KEY,
            enqueued_at TEXT,
            priority REAL DEFAULT 0,
            last_scraped TEXT,
            scrape_count INTEGER DEFAULT 0,
            blocked_count INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS dhgate_queue (
            keyword TEXT PRIMARY KEY,
            enqueued_at TEXT,
            priority REAL DEFAULT 0,
            last_scraped TEXT,
            scrape_count INTEGER DEFAULT 0,
            blocked_count INTEGER DEFAULT 0
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
    (vélocité décroissante). Filtré sur le shard du nœud (partition multi-machines)."""
    # 1. Cold start : jamais scrapé, le plus de produits couverts d'abord.
    #    On parcourt par couverture décroissante et on s'arrête au 1er du shard.
    pend = c.execute(
        "SELECT keyword FROM amazon_queue WHERE scrape_count=0 "
        "ORDER BY n_products DESC"
    ).fetchall()
    for (kw,) in pend:
        if in_shard(kw):
            return kw
    # 2. Refresh : dû selon la vélocité, les plus chauds d'abord.
    now = datetime.now(timezone.utc)
    cand = c.execute(
        "SELECT keyword, last_scraped, last_max_bought FROM amazon_queue "
        "WHERE last_scraped IS NOT NULL ORDER BY last_max_bought DESC NULLS LAST"
    ).fetchall()
    for kw, last, mx in cand:
        if not in_shard(kw):
            continue
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
    # Passerelle eBay/DHgate : seuil plus bas (volume de confirmation multi-marketplace).
    if (demand.max_bought or 0) >= SALES_THRESHOLD:
        for table in SALES_QUEUES:
            c.execute(
                f"INSERT INTO {table}(keyword, enqueued_at, priority) VALUES(?,?,?) "
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
        if not in_shard(kw):
            continue
        if last is None:
            return kw
        try:
            age_h = (now - datetime.fromisoformat(last)).total_seconds() / 3600
        except Exception:
            age_h = 1e9
        if age_h >= min_age_h:
            return kw
    return None


def record_aliexpress(c: sqlite3.Connection, keyword: str, demand=None) -> None:
    """Met à jour la file Ali ET persiste un snapshot ventes dans sales_snapshots
    (table canonique partagée avec collect_demand → lue par le scoring/loss_risk).
    Sans cela le signal AliExpress du runner 24/7 était totalement jeté."""
    if demand is not None and not getattr(demand, "blocked", False) and (getattr(demand, "max_sold", 0) or 0) > 0:
        c.execute(
            """CREATE TABLE IF NOT EXISTS sales_snapshots (
                   keyword TEXT, observed_at TEXT, max_sold INTEGER,
                   median_sold INTEGER, listings INTEGER,
                   PRIMARY KEY (keyword, observed_at))"""
        )
        c.execute(
            "INSERT OR IGNORE INTO sales_snapshots(keyword, observed_at, max_sold, median_sold, listings) "
            "VALUES(?,?,?,?,?)",
            (keyword, _now(), demand.max_sold or 0, demand.median_sold or 0,
             getattr(demand, "n_results", 0) or 0),
        )
    c.execute(
        "UPDATE aliexpress_queue SET last_scraped=?, scrape_count=scrape_count+1 WHERE keyword=?",
        (_now(), keyword),
    )
    c.commit()


# ── Sources de ventes secondaires : eBay sold + DHgate sold ──────────────────
# Même mur de rate-limit par IP qu'AliExpress → workers single-IP disciplinés,
# alimentant la table canonique sales_snapshots. Files calquées sur aliexpress_queue.

def rebuild_sales_queues(c: sqlite3.Connection) -> dict:
    """(Re)seed ebay_queue & dhgate_queue depuis les mots-clés Amazon à vélocité.

    Idempotent : conserve l'état (last_scraped, scrape_count) des entrées existantes,
    n'ajoute/maj que la priorité = dernière vélocité Amazon connue."""
    rows = c.execute(
        "SELECT keyword, last_max_bought FROM amazon_queue "
        "WHERE last_max_bought >= ? ORDER BY last_max_bought DESC",
        (SALES_THRESHOLD,),
    ).fetchall()
    for table in SALES_QUEUES:
        for kw, mx in rows:
            c.execute(
                f"INSERT INTO {table}(keyword, enqueued_at, priority) VALUES(?,?,?) "
                "ON CONFLICT(keyword) DO UPDATE SET priority=excluded.priority",
                (kw, _now(), float(mx or 0)),
            )
    c.commit()
    return {t: c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in SALES_QUEUES}


def next_sales_keyword(c: sqlite3.Connection, queue_table: str, min_age_h: int = 48) -> str | None:
    """Prochain mot-clé d'une file de ventes : jamais scrapé (priorité haute) d'abord,
    puis re-confirmation due (âge >= min_age_h), par priorité décroissante."""
    if queue_table not in SALES_QUEUES:
        raise ValueError(f"file inconnue : {queue_table}")
    now = datetime.now(timezone.utc)
    cand = c.execute(
        f"SELECT keyword, last_scraped FROM {queue_table} ORDER BY priority DESC"
    ).fetchall()
    for kw, last in cand:
        if not in_shard(kw):
            continue
        if last is None:
            return kw
        try:
            age_h = (now - datetime.fromisoformat(last)).total_seconds() / 3600
        except Exception:
            age_h = 1e9
        if age_h >= min_age_h:
            return kw
    return None


def record_sales(c: sqlite3.Connection, queue_table: str, keyword: str, demand) -> None:
    """Persiste un snapshot ventes (eBay/DHgate) dans sales_snapshots + maj la file.

    demand expose max_sold / median_sold / listings_with_sales / blocked
    (interface commune EbaySoldDemand & DHgateDemand)."""
    if queue_table not in SALES_QUEUES:
        raise ValueError(f"file inconnue : {queue_table}")
    blocked = getattr(demand, "blocked", False)
    if not blocked and (getattr(demand, "max_sold", 0) or 0) > 0:
        c.execute(
            """CREATE TABLE IF NOT EXISTS sales_snapshots (
                   keyword TEXT, observed_at TEXT, max_sold INTEGER,
                   median_sold INTEGER, listings INTEGER,
                   PRIMARY KEY (keyword, observed_at))"""
        )
        c.execute(
            "INSERT OR IGNORE INTO sales_snapshots(keyword, observed_at, max_sold, median_sold, listings) "
            "VALUES(?,?,?,?,?)",
            (keyword, _now(), demand.max_sold or 0, demand.median_sold or 0,
             getattr(demand, "listings_with_sales", 0) or 0),
        )
    if blocked:
        c.execute(f"UPDATE {queue_table} SET blocked_count=blocked_count+1 WHERE keyword=?", (keyword,))
    else:
        c.execute(
            f"UPDATE {queue_table} SET last_scraped=?, scrape_count=scrape_count+1 WHERE keyword=?",
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
    sales = {}
    for t in SALES_QUEUES:
        try:
            tot = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            scr = c.execute(f"SELECT COUNT(*) FROM {t} WHERE scrape_count>0").fetchone()[0]
            sales[t] = f"{scr}/{tot}"
        except sqlite3.OperationalError:
            sales[t] = "n/a"
    return {"total_keywords": total, "scraped": done, "pending": pending,
            "aliexpress_queued": ali, "hot_products": hot, **sales}


BREAKOUT_THRESHOLD = 100000  # palier « demande massive » (cap badge Amazon = 100k+)


def amazon_breakout(c: sqlite3.Connection, keyword: str, new_max) -> bool:
    """True si `new_max` est un NOUVEAU record historique pour ce mot-clé ET atteint
    le palier de demande massive.

    Sert à n'envoyer une notif produit que sur un vrai événement (~3/jour mesuré)
    plutôt qu'à chaque produit HOT (~1300/jour → spam, couvert par le digest).
    À appeler AVANT record_amazon (le snapshot courant ne doit pas encore être inséré)."""
    if (new_max or 0) < BREAKOUT_THRESHOLD:
        return False
    prev = c.execute(
        "SELECT MAX(max_bought) FROM amazon_snapshots WHERE keyword=?", (keyword,)
    ).fetchone()[0]
    return (new_max or 0) > (prev or 0)


def hourly_digest(c: sqlite3.Connection, hours: int = 1, top_n: int = 5) -> dict:
    """Synthèse des snapshots Amazon de la dernière `hours` heure(s) pour Discord.

    Remplace le heartbeat brut : combien de produits scrapés + le top demande réel,
    sans une notif par produit (la donnée est dense en gros vendeurs → spammy)."""
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    scraped = c.execute(
        "SELECT COUNT(*) FROM amazon_snapshots WHERE observed_at>=?", (since,)
    ).fetchone()[0]
    top = c.execute(
        "SELECT keyword, MAX(max_bought) AS mb FROM amazon_snapshots "
        "WHERE observed_at>=? AND max_bought IS NOT NULL "
        "GROUP BY keyword ORDER BY mb DESC LIMIT ?", (since, top_n)
    ).fetchall()
    queue_total = c.execute("SELECT COUNT(*) FROM amazon_queue").fetchone()[0]
    return {"scraped_last_h": scraped,
            "top": [(kw, mb) for kw, mb in top],
            "queue_total": queue_total}


if __name__ == "__main__":  # python3 demand_queue.py  → init + stats
    c = connect()
    init_schema(c)
    n = rebuild_from_cj(c)
    print(f"File Amazon (re)construite : {n} mots-clés uniques depuis cj_products")
    print("Stats:", stats(c))
