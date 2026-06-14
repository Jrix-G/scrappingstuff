"""Job quotidien du Raspberry Pi : collecte CJ + rebuild du cache produit.

Enchaîne, dans l'ordre :
  1. découverte CJ → capte les nouveaux produits (pages les plus récentes)
  2. refresh CJ    → re-snapshote l'univers déjà connu (suivi/vélocité réelle)
  3. export        → recalcule vendabilité + enrichit Trends/Reddit (top N) → cache API

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
    ap.add_argument("--pages", type=int, default=100, help="Pages CJ de découverte (50/page)")
    ap.add_argument("--page-size", type=int, default=50)
    ap.add_argument("--keyword", type=str, default=None, help="Filtre mot-clé CJ")
    ap.add_argument("--limit", type=int, default=40, help="Top N enrichi Trends/Reddit")
    ap.add_argument("--geo", type=str, default="", help="Code pays Trends (ex. FR)")
    ap.add_argument("--no-collect", action="store_true", help="Sauter la découverte CJ")
    ap.add_argument("--no-refresh", action="store_true", help="Sauter le re-snapshot de l'univers")
    ap.add_argument("--max-refresh", type=int, default=8000,
                    help="Plafond de produits re-snapshotés (suivi/vélocité)")
    ap.add_argument("--refresh-min-age-hours", type=float, default=20.0,
                    help="Ne pas re-snapshoter un produit vu depuis moins de N heures")
    ap.add_argument("--no-enrich", action="store_true", help="Export sans Trends/Reddit")
    args = ap.parse_args()

    _log("=== Job quotidien Tandor : démarrage ===")

    # --- Étape 1 : découverte CJ (nouveaux produits, tolérante aux pannes) ---
    if not args.no_collect:
        try:
            from collect_cj import run_collect
            _log(f"Découverte CJ : {args.pages} pages (≈{args.pages * args.page_size} produits) …")
            run_collect(args.pages, args.page_size, args.keyword)
        except SystemExit:
            _log("⚠ Découverte interrompue (creds/CJ). On continue sur la base existante.")
        except Exception as exc:  # noqa: BLE001 - le job ne doit pas mourir ici
            _log(f"⚠ Découverte en erreur : {exc}. On continue sur la base existante.")
    else:
        _log("Découverte sautée (--no-collect).")

    # --- Étape 2 : refresh de l'univers connu (suivi/vélocité) --------------
    if not args.no_refresh:
        try:
            from collect_cj import run_refresh
            _log(f"Refresh univers : plafond {args.max_refresh} (âge mini {args.refresh_min_age_hours}h) …")
            run_refresh(args.max_refresh, args.refresh_min_age_hours)
        except SystemExit:
            _log("⚠ Refresh interrompu (creds/CJ). On continue.")
        except Exception as exc:  # noqa: BLE001 - le job ne doit pas mourir ici
            _log(f"⚠ Refresh en erreur : {exc}. On continue.")
    else:
        _log("Refresh sauté (--no-refresh).")

    # --- Étape 3 : rebuild du cache produit ---------------------------------
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
