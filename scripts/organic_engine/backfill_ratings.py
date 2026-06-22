"""Backfill : remplit median_rating / max_reviews / n_with_rating dans amazon_snapshots
depuis les pages déjà en cache (.amazon_cache), sans refaire de réseau.

On reparse le HTML caché de chaque mot-clé connu et on met à jour SA ligne de snapshot
la plus récente. Idempotent. À lancer une fois après l'ajout des colonnes qualité.
"""
from __future__ import annotations
import sqlite3
from pathlib import Path
from collectors.amazon_demand import _parse, _cache_path
import demand_queue as dq


def main() -> None:
    c = dq.connect()
    dq.init_schema(c)
    keywords = [r[0] for r in c.execute(
        "SELECT DISTINCT keyword FROM amazon_snapshots").fetchall()]
    updated = miss = norating = 0
    for kw in keywords:
        p: Path = _cache_path(kw)
        if not p.exists():
            miss += 1
            continue
        body = p.read_text(encoding="utf-8", errors="ignore")
        d = _parse(kw, body)
        if d.median_rating is None:
            norating += 1
            continue
        # met à jour la ligne de snapshot la plus récente de ce mot-clé
        c.execute(
            """UPDATE amazon_snapshots
                 SET median_rating=?, max_reviews=?, n_with_rating=?, pct_low_rating=?
               WHERE keyword=? AND observed_at=(
                   SELECT MAX(observed_at) FROM amazon_snapshots WHERE keyword=?)""",
            (d.median_rating, d.max_reviews, d.n_with_rating, d.pct_low_rating, kw, kw),
        )
        updated += 1
    c.commit()
    print(f"keywords: {len(keywords)} | mis à jour: {updated} | "
          f"cache absent: {miss} | sans note: {norating}")


if __name__ == "__main__":
    main()
