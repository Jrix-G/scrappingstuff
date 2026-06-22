#!/usr/bin/env python3
"""Worker single-IP des sources de ventes secondaires : eBay sold + DHgate sold.

Pourquoi un worker séparé du runner Amazon : ces deux sources scrapent des pages
web publiques (pas d'API) et se heurtent au MÊME mur de rate-limit par IP
qu'AliExpress (eBay « flappe » après ~80-120 req ; DHgate bloque aussi sous rafale).
On les exploite donc en **single-IP discipliné** : cadence longue, un essai propre par
mot-clé, backoff exponentiel sur blocage, budget borné par run. Resumable (état dans cj.db).

Alimente la table canonique ``sales_snapshots`` (lue par le scoring / loss_risk),
en plus d'AliExpress et d'Amazon → signal demande multi-source.

Usage :
    python3 sales_worker.py --source ebay   --budget 30
    python3 sales_worker.py --source dhgate --budget 60
"""
from __future__ import annotations

import argparse
import random
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

ENGINE = Path(__file__).resolve().parent
sys.path.insert(0, str(ENGINE))

import demand_queue as q
import notify_discord as notify
from collectors import ebay_sold, dhgate_sold

# source → (module collecteur, table de file, libellé Discord). Interface commune : fetch_demand(kw).
SOURCES = {
    "ebay":   (ebay_sold,   "ebay_queue",   "eBay"),
    "dhgate": (dhgate_sold, "dhgate_queue", "DHgate"),
}

# Seuil « chaud » propre aux ventes secondaires : l'échelle « sold » eBay/DHgate est
# sans rapport avec le « bought/mois » Amazon (q.HOT_THRESHOLD=5000). Calé modeste
# pour que le signal Discord se déclenche sans spammer.
SALES_HOT_THRESHOLD = 50

# Cadence single-IP (entre deux mots-clés réussis). Le collecteur impose déjà un
# _MIN_REQUEST_INTERVAL interne ; on ajoute une marge pour rester sous le seuil de l'IP.
PACE_SECONDS = (45.0, 90.0)
# Backoff sur blocage (IP en cooldown) : 10 / 30 / 60 min.
BLOCK_COOLDOWNS = [600, 1800, 3600]
# Au-delà, l'IP est en grande difficulté → on rend la main (le cron relancera plus tard).
MAX_CONSEC_BLOCKS = 4

_RUN = True


def _ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _stop(*_):
    global _RUN
    _RUN = False
    print(f"[{_ts()}] arrêt demandé — fin de l'itération en cours…", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="Worker ventes single-IP (eBay/DHgate)")
    ap.add_argument("--source", choices=list(SOURCES), required=True)
    ap.add_argument("--budget", type=int, default=30,
                    help="Nb max de mots-clés réussis avant de rendre la main")
    ap.add_argument("--min-age-h", type=int, default=48,
                    help="Âge mini avant re-confirmation d'un mot-clé déjà scrapé")
    args = ap.parse_args()

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    module, table, label = SOURCES[args.source]
    c = q.connect()
    q.init_schema(c)
    seeded = q.rebuild_sales_queues(c)
    print(f"[{_ts()}] Worker « {args.source} » démarré — files: {seeded} "
          f"(budget {args.budget}, min-age {args.min_age_h}h)", flush=True)
    notify.send(f"🛒 **Worker {label} démarré** — budget {args.budget} mot(s)-clé(s)")
    hot = 0

    done = 0
    consec_blocks = 0

    while _RUN and done < args.budget:
        kw = q.next_sales_keyword(c, table, min_age_h=args.min_age_h)
        if kw is None:
            print(f"[{_ts()}] File « {args.source} » à jour, rien de dû — fin.", flush=True)
            break

        try:
            d = module.fetch_demand(kw)
        except Exception as exc:                      # garde-fou : ne jamais crasher le worker
            print(f"[{_ts()}] ✗ « {kw} » erreur inattendue : {exc}", flush=True)
            d = None

        if d is None or getattr(d, "blocked", True):
            consec_blocks += 1
            q.record_sales(c, table, kw, d) if d is not None else None
            idx = min(consec_blocks - 1, len(BLOCK_COOLDOWNS) - 1)
            cooldown = BLOCK_COOLDOWNS[idx] + random.uniform(0, 120)
            print(f"[{_ts()}] ⚠ BLOQUÉ ×{consec_blocks} sur « {kw} » "
                  f"→ cooldown {cooldown/60:.1f} min", flush=True)
            if consec_blocks == 1:                    # 1er blocage de la série (évite le spam)
                notify.blocked(kw, source=label)
            if consec_blocks >= MAX_CONSEC_BLOCKS:
                print(f"[{_ts()}] ⚠⚠ IP « {args.source} » épuisée — on rend la main.", flush=True)
                break
            _sleep(cooldown)
            continue

        consec_blocks = 0
        q.record_sales(c, table, kw, d)
        done += 1
        flag = " 🟢" if (d.max_sold or 0) >= SALES_HOT_THRESHOLD else ""
        print(f"[{_ts()}] [{done}/{args.budget}] « {kw} » "
              f"max={d.max_sold} med={d.median_sold} n={d.listings_with_sales}{flag}", flush=True)
        if (d.max_sold or 0) >= SALES_HOT_THRESHOLD:
            hot += 1
            notify.sales_hot(kw, label, d.max_sold, d.median_sold, d.listings_with_sales)
        _sleep(random.uniform(*PACE_SECONDS))

    print(f"[{_ts()}] Worker « {args.source} » terminé — {done} mot(s)-clé(s) confirmé(s).", flush=True)
    notify.send(f"✅ **Worker {label} terminé** — {done} confirmé(s) · {hot} chaud(s) "
                f"(≥ {SALES_HOT_THRESHOLD})")
    c.close()
    return 0


def _sleep(seconds: float) -> None:
    """Sleep interruptible (réagit à SIGTERM en <1 s)."""
    end = time.time() + seconds
    while _RUN and time.time() < end:
        time.sleep(min(1.0, end - time.time()))


if __name__ == "__main__":
    raise SystemExit(main())
