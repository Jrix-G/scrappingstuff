"""Collecte CJ Dropshipping -> SQLite, puis scoring organique.

Usage :
    export CJ_EMAIL="ton@email.com"
    export CJ_API_KEY="ta_cle_api"
    python3 collect_cj.py --pages 20            # collecte 20 pages (~1000 produits)
    python3 collect_cj.py --keyword "led light" # filtre par mot-clé
    python3 collect_cj.py --score               # score ce qui est en base

La VÉLOCITÉ a besoin d'historique : lance la collecte régulièrement (1×/jour).
Le 1er run pose la baseline ; dès le 2e, le moteur calcule l'accélération.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from collectors.cj_dropshipping import CJClient, CJError, CJProduct
from signals.features import RawSignal, build_product_features
from scoring.engine import score_population

DB_PATH = Path(__file__).resolve().parent / "data" / "cj.db"


# ---------------------------------------------------------------------------
# Stockage
# ---------------------------------------------------------------------------

def init_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS cj_products (
            pid          TEXT PRIMARY KEY,
            name         TEXT,
            category     TEXT,
            image        TEXT,
            create_time  TEXT,
            first_seen   TEXT,
            last_seen    TEXT
        );
        CREATE TABLE IF NOT EXISTS cj_snapshots (
            pid          TEXT,
            observed_at  TEXT,
            price        REAL,
            listed_num   INTEGER,
            PRIMARY KEY (pid, observed_at)
        );
        CREATE INDEX IF NOT EXISTS idx_snap_pid ON cj_snapshots(pid, observed_at);
    """)
    conn.commit()
    return conn


def store(conn: sqlite3.Connection, products: list[CJProduct]) -> tuple[int, int]:
    """Enregistre produits + snapshot. Renvoie (nouveaux_produits, snapshots)."""
    now = datetime.now(timezone.utc).isoformat()
    new_products = 0
    snaps = 0
    for p in products:
        if not p.pid:
            continue
        is_new = conn.execute("SELECT 1 FROM cj_products WHERE pid=?", (p.pid,)).fetchone() is None
        conn.execute(
            """INSERT INTO cj_products (pid, name, category, image, create_time, first_seen, last_seen)
               VALUES (?,?,?,?,?,?,?)
               ON CONFLICT(pid) DO UPDATE SET name=excluded.name, last_seen=excluded.last_seen""",
            (p.pid, p.name, p.category, p.image, p.create_time, now, now),
        )
        conn.execute(
            """INSERT OR IGNORE INTO cj_snapshots (pid, observed_at, price, listed_num)
               VALUES (?,?,?,?)""",
            (p.pid, p.observed_at, p.price, p.listed_num),
        )
        new_products += int(is_new)
        snaps += 1
    conn.commit()
    return new_products, snaps


# ---------------------------------------------------------------------------
# Collecte
# ---------------------------------------------------------------------------

def run_collect(pages: int, page_size: int, keyword: str | None) -> None:
    email = os.environ.get("CJ_EMAIL", "")
    api_key = os.environ.get("CJ_API_KEY", "")
    try:
        client = CJClient(email, api_key)
        print(f"Authentification CJ ({email}) ...")
        client.authenticate()
        print("✓ Token obtenu\n")
    except CJError as exc:
        print(f"✗ Échec CJ : {exc}")
        print("→ Vérifie CJ_EMAIL et CJ_API_KEY (Mon CJ → Authorization → API).")
        sys.exit(1)

    conn = init_db()
    total_new = total_snaps = 0
    catalog_total = 0
    try:
        for page, products, total in client.iter_catalog(pages, page_size, keyword):
            catalog_total = total
            new, snaps = store(conn, products)
            total_new += new
            total_snaps += snaps
            print(f"  page {page:>3} : {len(products):>3} produits  "
                  f"(+{new} nouveaux)  [catalogue total CJ : {total:,}]")
    except CJError as exc:
        print(f"\n⚠ Interruption API : {exc} (données déjà enregistrées)")
    finally:
        in_db = conn.execute("SELECT COUNT(*) FROM cj_products").fetchone()[0]
        conn.close()

    print(f"\n{'='*60}")
    print(f"  Snapshots pris      : {total_snaps}")
    print(f"  Nouveaux produits   : {total_new}")
    print(f"  Produits en base    : {in_db:,}")
    print(f"  Catalogue CJ total  : {catalog_total:,}")
    print(f"  Base                : {DB_PATH}")
    print(f"{'='*60}")
    if total_new == total_snaps:
        print("  ℹ 1er passage = baseline. Relance demain pour activer la vélocité.")


# ---------------------------------------------------------------------------
# Scoring depuis l'historique
# ---------------------------------------------------------------------------

def run_score(top: int) -> None:
    conn = init_db()
    rows = conn.execute("SELECT pid, name, create_time FROM cj_products").fetchall()
    population = []
    for pid, name, create_time in rows:
        snaps = conn.execute(
            "SELECT observed_at, listed_num, price FROM cj_snapshots WHERE pid=? ORDER BY observed_at",
            (pid,),
        ).fetchall()
        if len(snaps) < 2:
            continue  # pas d'historique => pas de vélocité
        t0 = datetime.fromisoformat(snaps[0][0])
        days = [(datetime.fromisoformat(s[0]) - t0).total_seconds() / 86400.0 for s in snaps]
        listed = [float(s[1]) if s[1] is not None else 0.0 for s in snaps]
        # 'cj_listings' = adoption côté offre (vendeurs qui listent) -> proxy momentum.
        raws = [RawSignal("cj_listings", days, listed)]
        age = _age_days(create_time)
        population.append(build_product_features(pid, raws, age_days=age,
                                                 seller_count=int(listed[-1])))
    conn.close()

    if not population:
        print("Pas encore d'historique suffisant (besoin de ≥2 collectes à des dates différentes).")
        print("→ Relance `python3 collect_cj.py --pages N` demain, puis `--score`.")
        return

    results = score_population(population)
    results.sort(key=lambda r: r.organic_score, reverse=True)
    names = {pid: name for pid, name, _ in rows}
    print(f"\n  TOP {top} POTENTIEL ORGANIQUE (sur {len(population)} produits avec historique)\n")
    for r in results[:top]:
        nm = (names.get(r.product_id) or r.product_id)[:50]
        print(f"  {r.organic_score:5.1f}  [{r.phase.value:12}] conf={r.confidence:.2f}  {nm}")


def _age_days(create_time: str | None) -> float | None:
    """Âge en jours. CJ renvoie un epoch en MILLISECONDES (ex. 1781263470000)."""
    if not create_time:
        return None
    now = datetime.now(timezone.utc)
    # Cas 1 : epoch numérique (millisecondes ou secondes).
    s = str(create_time).strip()
    if s.isdigit():
        ts = int(s)
        if ts > 10_000_000_000:  # > ~2286 en secondes => c'est des millisecondes
            ts /= 1000.0
        try:
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            return (now - dt).total_seconds() / 86400.0
        except (ValueError, OSError, OverflowError):
            return None
    # Cas 2 : date texte.
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s[:19], fmt).replace(tzinfo=timezone.utc)
            return (now - dt).total_seconds() / 86400.0
        except ValueError:
            continue
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Collecteur CJ Dropshipping + scoring")
    parser.add_argument("--pages", type=int, default=20, help="Pages à collecter (50 produits/page)")
    parser.add_argument("--page-size", type=int, default=50)
    parser.add_argument("--keyword", type=str, default=None, help="Filtre par mot-clé produit")
    parser.add_argument("--score", action="store_true", help="Scorer la base au lieu de collecter")
    parser.add_argument("--top", type=int, default=20, help="Nb de produits à afficher au scoring")
    args = parser.parse_args()

    if args.score:
        run_score(args.top)
    else:
        run_collect(args.pages, args.page_size, args.keyword)


if __name__ == "__main__":
    main()
