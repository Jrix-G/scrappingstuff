"""Job quotidien du Raspberry Pi : collecte CJ + rebuild du cache produit.

Enchaîne, dans l'ordre :
  1. collecte CJ  → ajoute 1 snapshot dans cj.db (démarre/alimente la vélocité réelle)
  2. export       → recalcule vendabilité + enrichit Trends/Reddit (top N) → cache API

À brancher sur cron (voir DEPLOY_PI.md). Chaque étape est isolée : si la collecte
échoue (réseau/CJ down), l'export tourne quand même sur les données déjà en base.

Usage :
    export CJ_EMAIL="..."; export CJ_API_KEY="..."
    python3 run_daily.py                       # 20 pages, top 40 enrichi
    python3 run_daily.py --pages 40 --limit 60
    python3 run_daily.py --no-collect          # rebuild cache seulement
    python3 run_daily.py --no-enrich           # rapide, sans Trends/Reddit
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def _log(msg: str) -> None:
    print(f"[{datetime.now(timezone.utc).isoformat(timespec='seconds')}] {msg}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="Job quotidien Tandor (collecte + cache)")
    ap.add_argument("--pages", type=int, default=20, help="Pages CJ à collecter (50/page)")
    ap.add_argument("--page-size", type=int, default=50)
    ap.add_argument("--keyword", type=str, default=None, help="Filtre mot-clé CJ")
    ap.add_argument("--limit", type=int, default=40, help="Top N enrichi Trends/Reddit")
    ap.add_argument("--geo", type=str, default="", help="Code pays Trends (ex. FR)")
    ap.add_argument("--no-collect", action="store_true", help="Sauter la collecte CJ")
    ap.add_argument("--no-enrich", action="store_true", help="Export sans Trends/Reddit")
    args = ap.parse_args()

    _log("=== Job quotidien Tandor : démarrage ===")

    # --- Étape 1 : collecte CJ (tolérante aux pannes) -----------------------
    if not args.no_collect:
        try:
            from collect_cj import run_collect
            _log(f"Collecte CJ : {args.pages} pages …")
            run_collect(args.pages, args.page_size, args.keyword)
        except SystemExit:
            _log("⚠ Collecte interrompue (creds/CJ). On continue sur la base existante.")
        except Exception as exc:  # noqa: BLE001 - le job ne doit pas mourir ici
            _log(f"⚠ Collecte en erreur : {exc}. On continue sur la base existante.")
    else:
        _log("Collecte sautée (--no-collect).")

    # --- Étape 2 : rebuild du cache produit ---------------------------------
    from export_dashboard import build_records, OUT, CACHE

    _log(f"Export : top {args.limit} (enrich={not args.no_enrich}) …")
    out, total_in_db = build_records(args.limit, args.geo, args.no_enrich)
    if not out:
        _log("✗ Aucune donnée à exporter (cj.db vide ?). Échec.")
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    cache = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "count": len(out),
            "total_in_db": total_in_db,
            "enriched": not args.no_enrich,
            "geo": args.geo or "WW",
        },
        "products": out,
    }
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=2))

    _log(f"✓ Cache régénéré : {len(out)} produits servis / {total_in_db} en base → {CACHE}")
    _log("=== Job quotidien Tandor : terminé ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
