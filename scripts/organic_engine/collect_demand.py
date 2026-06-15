"""Collecte de la DEMANDE marché par mot-clé (AliExpress) -> SQLite.

CJ mesure l'OFFRE (combien de vendeurs listent un produit). Ici on mesure la
DEMANDE réelle côté marketplace, par mot-clé :

  • AliExpress (best-effort) → ground-truth des unités VENDUES (tradeDesc).

Comme les snapshots CJ, AliExpress renvoie une PHOTO ponctuelle : on l'empile dans
le temps (1×/jour via cron) pour que le moteur calcule la vélocité de la demande.
Tout vit dans la MÊME base ``cj.db`` que CJ.

  sales_snapshots(keyword, observed_at, max_sold, median_sold, listings)
    (AliExpress « blocked » = donnée indisponible → AUCUNE ligne, jamais un zéro
     qui serait lu comme « zéro demande ».)

NB eBay : le collecteur ``ebay_browse.py`` et la table ``ebay_snapshots`` sont gardés
DORMANTS (compte eBay banni). ``snapshot_ebay`` existe encore mais n'est plus appelé.
Pour réactiver eBay : remettre ``ebay_listings`` dans ``signals.features.SIGNALS``,
rappeler ``snapshot_ebay`` dans ``run_collect`` et relire ``ebay_snapshots`` ici.

Usage :
    python3 collect_demand.py --from-buys --top 20   # mots-clés des meilleurs BUY
    python3 collect_demand.py --keyword "ceiling fan"
    python3 collect_demand.py --score                # aperçu vélocité demande
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from collectors import ebay_browse, aliexpress_orders
from signals.features import RawSignal

DB_PATH = Path(__file__).resolve().parent / "data" / "cj.db"


# ---------------------------------------------------------------------------
# Stockage (mêmes pragmas que collect_cj : WAL + busy_timeout pour la concurrence)
# ---------------------------------------------------------------------------

def init_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS ebay_snapshots (
            keyword         TEXT,
            observed_at     TEXT,
            active_listings INTEGER,
            price_median    REAL,
            currency        TEXT,
            PRIMARY KEY (keyword, observed_at)
        );
        CREATE INDEX IF NOT EXISTS idx_ebay_kw ON ebay_snapshots(keyword, observed_at);
        CREATE TABLE IF NOT EXISTS sales_snapshots (
            keyword      TEXT,
            observed_at  TEXT,
            max_sold     INTEGER,
            median_sold  INTEGER,
            listings     INTEGER,
            PRIMARY KEY (keyword, observed_at)
        );
        CREATE INDEX IF NOT EXISTS idx_sales_kw ON sales_snapshots(keyword, observed_at);
    """)
    conn.commit()
    return conn


def snapshot_ebay(conn: sqlite3.Connection, keyword: str, now: str) -> bool:
    """DORMANT (compte eBay banni) — plus appelé. Conservé pour réactivation future.

    Photographie eBay pour un mot-clé. Renvoie True si une ligne a été écrite.

    L'API dégrade en ``active_listings=0`` sur erreur ; on n'enregistre alors RIEN
    (0 annonce sur erreur réseau ≠ vraie absence d'annonces) pour ne pas polluer la
    vélocité avec un faux creux.
    """
    d = ebay_browse.fetch_demand(keyword)
    if d.active_listings <= 0 and d.sample == 0:
        return False
    conn.execute(
        """INSERT OR IGNORE INTO ebay_snapshots
               (keyword, observed_at, active_listings, price_median, currency)
           VALUES (?,?,?,?,?)""",
        (keyword, now, d.active_listings, d.price_median, d.currency),
    )
    return True


def snapshot_aliexpress(conn: sqlite3.Connection, keyword: str, now: str) -> bool:
    """Photographie AliExpress (best-effort). Aucune ligne si bloqué/indisponible."""
    d = aliexpress_orders.fetch_demand(keyword)
    if d.blocked or d.max_sold is None:
        return False
    conn.execute(
        """INSERT OR IGNORE INTO sales_snapshots
               (keyword, observed_at, max_sold, median_sold, listings)
           VALUES (?,?,?,?,?)""",
        (keyword, now, d.max_sold, d.median_sold, d.listings_with_sales),
    )
    return True


# ---------------------------------------------------------------------------
# Relecture historique -> RawSignal (consommé par enrich.py / le scoring)
# ---------------------------------------------------------------------------

def _series(rows: list[tuple]) -> tuple[list[float], list[float]]:
    """(observed_at, valeur) triés -> (jours depuis t0, valeurs)."""
    t0 = datetime.fromisoformat(rows[0][0])
    days = [(datetime.fromisoformat(r[0]) - t0).total_seconds() / 86400.0 for r in rows]
    vals = [float(r[1]) for r in rows]
    return days, vals


def demand_raw_signals(conn: sqlite3.Connection, keyword: str) -> list[RawSignal]:
    """Séries de demande disponibles pour un mot-clé.

    Renvoie les ``RawSignal`` ayant au moins 2 points — en dessous, pas de vélocité
    calculable, le moteur les ignore de toute façon. (eBay dormant : non relu.)
    """
    out: list[RawSignal] = []
    sales = conn.execute(
        "SELECT observed_at, max_sold FROM sales_snapshots "
        "WHERE keyword=? AND max_sold IS NOT NULL ORDER BY observed_at",
        (keyword,),
    ).fetchall()
    if len(sales) >= 2:
        days, vals = _series(sales)
        out.append(RawSignal("sales", days, vals))
    return out


def latest_sales_level(conn: sqlite3.Connection, keyword: str) -> dict | None:
    """Dernier NIVEAU absolu de ventes AliExpress pour un mot-clé.

    Validation de demande dès le 1er snapshot (≠ vélocité qui exige 2 points) :
    « ce type de produit s'est vendu X fois ». None si aucun snapshot.
    """
    row = conn.execute(
        "SELECT observed_at, max_sold, median_sold, listings FROM sales_snapshots "
        "WHERE keyword=? AND max_sold IS NOT NULL ORDER BY observed_at DESC LIMIT 1",
        (keyword,),
    ).fetchone()
    if not row:
        return None
    return {"observedAt": row[0], "maxSold": row[1],
            "medianSold": row[2], "listings": row[3]}


# ---------------------------------------------------------------------------
# Sélection des mots-clés
# ---------------------------------------------------------------------------

def keywords_from_buys(top: int) -> list[str]:
    """Mots-clés dérivés des meilleurs produits BUY (réutilise analyze + enrich)."""
    from analyze import analyze
    from enrich import keyword_from_name
    records = analyze(datetime.now().month)
    buys = [r for r in records if r["verdict"] == "BUY"][:top]
    seen, kws = set(), []
    for r in buys:
        kw = keyword_from_name(r["name"])
        if kw and kw not in seen:
            seen.add(kw)
            kws.append(kw)
    return kws


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------

def run_collect(keywords: list[str], delay: float) -> None:
    if not keywords:
        print("Aucun mot-clé à collecter.")
        return
    conn = init_db()
    now = datetime.now(timezone.utc).isoformat()
    sales_ok = sales_blocked = 0
    print(f"Collecte demande (ventes AliExpress) pour {len(keywords)} mots-clés ...\n")
    for i, kw in enumerate(keywords, 1):
        if snapshot_aliexpress(conn, kw, now):
            sales_ok += 1
            mark = "ventes✓"
        else:
            sales_blocked += 1
            mark = "ventes—"
        print(f"  [{i}/{len(keywords)}] « {kw} »  {mark}", flush=True)
        conn.commit()
        if i < len(keywords):
            time.sleep(delay)
    conn.close()
    print(f"\n{'='*60}")
    print(f"  Snapshots ventes (AE) : {sales_ok}/{len(keywords)}  "
          f"(indispo/bloqués : {sales_blocked})")
    print(f"  Base                  : {DB_PATH}")
    print(f"{'='*60}")


def run_score(top: int) -> None:
    """Aperçu : vélocité de la demande par mot-clé (≥2 snapshots requis)."""
    from signals.features import build_product_features
    from scoring.engine import score_population

    conn = init_db()
    keywords = [r[0] for r in conn.execute(
        "SELECT DISTINCT keyword FROM ebay_snapshots "
        "UNION SELECT DISTINCT keyword FROM sales_snapshots").fetchall()]
    population, names = [], {}
    for kw in keywords:
        raws = demand_raw_signals(conn, kw)
        if not raws:
            continue
        population.append(build_product_features(kw, raws))
        names[kw] = kw
    conn.close()
    if not population:
        print("Pas encore d'historique (≥2 collectes à des dates différentes requises).")
        print("→ Relance `python3 collect_demand.py --from-buys` demain.")
        return
    results = score_population(population)
    results.sort(key=lambda r: r.organic_score, reverse=True)
    print(f"\n  DEMANDE QUI DÉCOLLE — TOP {top} (sur {len(population)} mots-clés suivis)\n")
    for r in results[:top]:
        print(f"  {r.organic_score:5.1f}  [{r.phase.value:12}] "
              f"crois/m={r.monthly_growth*100:+6.1f}%  {names[r.product_id]}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Collecte demande marché (eBay + AliExpress)")
    parser.add_argument("--keyword", action="append", default=[],
                        help="Mot-clé à suivre (répétable)")
    parser.add_argument("--from-buys", action="store_true",
                        help="Dériver les mots-clés des meilleurs produits BUY")
    parser.add_argument("--top", type=int, default=20, help="Nb de BUY à reprendre")
    parser.add_argument("--delay", type=float, default=2.0, help="Délai entre mots-clés (s)")
    parser.add_argument("--score", action="store_true", help="Afficher la vélocité demande")
    args = parser.parse_args()

    if args.score:
        run_score(args.top)
        return
    keywords = list(args.keyword)
    if args.from_buys:
        keywords += keywords_from_buys(args.top)
    run_collect(keywords, args.delay)


if __name__ == "__main__":
    main()
