#!/usr/bin/env python3
"""Runner 24/7 du signal demande Tandor.

Boucle principale : scrape Amazon (« bought in past month ») au rythme 5–10 s/produit,
en priorisant la pile (couverture max puis vélocité). En cadence lente parallèle,
confirme les TOP produits sur AliExpress (~1 req/5,5 min ≈ 260/jour, sous le mur x5sec).

Durcissement anti-ban (recherche dédiée 2026) :
* détection de blocage par le CORPS (captcha Amazon = HTTP 200) + présence des cartes ;
* backoff exponentiel 2→5→15→30→60 min, nouvelle persona, jamais de fast-retry ;
* rotation d'identité (profil TLS + UA + cookies) toutes ~150–400 req et à chaque blocage ;
* breaks « humains » 2–5 min toutes les 20–40 req ; heures creuses ralenties.

Resumable : tout l'état est dans cj.db. Lancer : python3 demand_runner.py
Arrêt propre : SIGTERM/SIGINT.
"""
from __future__ import annotations

import random
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ENGINE = Path(__file__).resolve().parent
sys.path.insert(0, str(ENGINE))

import demand_queue as q
from collectors import amazon_demand as amz

# ── Pacing (demandé : 5–10 s aléatoire entre produits Amazon) ────────────────
PACE_MIN, PACE_MAX = 5.0, 10.0
BREAK_EVERY = (20, 40)            # break humain toutes les N req
BREAK_SECONDS = (120, 300)       # durée du break : 2–5 min
PERSONA_EVERY = (150, 400)       # rotation d'identité toutes les N req
COOLDOWNS = [120, 300, 900, 1800, 3600]   # backoff blocage : 2,5,15,30,60 min
QUIET_HOURS = (2, 6)             # heures creuses locales (ralenti ×3)

# ── Cadence AliExpress (budget rare, top produits) ───────────────────────────
ALI_INTERVAL_S = 330             # ~5,5 min → ~260/jour, sous le plafond x5sec

_RUN = True


def _stop(*_):
    global _RUN
    _RUN = False
    print(f"[{_ts()}] arrêt demandé — fin de l'itération en cours…", flush=True)


def _ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _in_quiet_hours() -> bool:
    h = datetime.now().hour
    lo, hi = QUIET_HOURS
    return lo <= h < hi


def _scrape_aliexpress(keyword: str) -> str:
    """Confirme un mot-clé sur AliExpress (best-effort). Retourne un libellé de résultat."""
    try:
        from collectors.aliexpress_orders import fetch_demand
        d = fetch_demand(keyword)
        if d.blocked:
            return "bloqué"
        return f"maxSold={d.max_sold} median={d.median_sold}"
    except Exception as e:
        return f"err {type(e).__name__}"


def main() -> None:
    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    c = q.connect()
    q.init_schema(c)
    n = q.rebuild_from_cj(c)
    print(f"[{_ts()}] Démarrage runner demande — {n} mots-clés en file. Stats: {q.stats(c)}", flush=True)

    sess = amz.make_session()
    consec_blocks = 0
    req_since_break = 0
    req_since_persona = 0
    next_break_at = random.randint(*BREAK_EVERY)
    next_persona_at = random.randint(*PERSONA_EVERY)
    last_ali = 0.0
    done = 0

    while _RUN:
        # ── Cadence AliExpress (top produits) ────────────────────────────────
        if time.time() - last_ali >= ALI_INTERVAL_S:
            ali_kw = q.next_aliexpress_keyword(c)
            if ali_kw:
                res = _scrape_aliexpress(ali_kw)
                q.record_aliexpress(c, ali_kw)
                print(f"[{_ts()}]   ▸ AliExpress « {ali_kw} » → {res}", flush=True)
            last_ali = time.time()

        # ── Amazon : prochain mot-clé de la pile ─────────────────────────────
        kw = q.next_amazon_keyword(c)
        if kw is None:
            print(f"[{_ts()}] File à jour, rien de dû — pause 5 min.", flush=True)
            time.sleep(300)
            continue

        d = amz.fetch_demand(kw, session=sess)

        if d.blocked:
            consec_blocks += 1
            q.record_amazon(c, d)
            idx = min(consec_blocks - 1, len(COOLDOWNS) - 1)
            base = COOLDOWNS[idx]
            sleep = base + random.uniform(0, base * 0.5)
            print(f"[{_ts()}] ⚠ BLOQUÉ ×{consec_blocks} sur « {kw} » → cooldown "
                  f"{sleep/60:.1f} min + nouvelle persona", flush=True)
            sess = amz.make_session()           # identité fraîche
            req_since_persona = 0
            next_persona_at = random.randint(*PERSONA_EVERY)
            if consec_blocks >= 8:               # IP en grande difficulté → longue pause
                print(f"[{_ts()}] ⚠⚠ blocages répétés — pause 6 h.", flush=True)
                time.sleep(6 * 3600)
                consec_blocks = 0
            else:
                time.sleep(sleep)
            continue

        consec_blocks = 0
        q.record_amazon(c, d)
        done += 1
        flag = " 🔥" if (d.max_bought or 0) >= q.HOT_THRESHOLD else ""
        if done % 20 == 0 or (d.max_bought or 0) >= q.HOT_THRESHOLD:
            print(f"[{_ts()}] [{done}] « {kw} » max={d.max_bought} med={d.median_bought} "
                  f"({d.n_with_velocity}/{d.n_results}){flag}", flush=True)

        # ── Pacing 5–10 s (×3 en heures creuses) ─────────────────────────────
        pace = random.uniform(PACE_MIN, PACE_MAX) * (3.0 if _in_quiet_hours() else 1.0)
        time.sleep(pace)

        # ── Break humain ─────────────────────────────────────────────────────
        req_since_break += 1
        if req_since_break >= next_break_at:
            br = random.uniform(*BREAK_SECONDS)
            print(f"[{_ts()}]   …break humain {br/60:.1f} min", flush=True)
            time.sleep(br)
            req_since_break = 0
            next_break_at = random.randint(*BREAK_EVERY)

        # ── Rotation d'identité ──────────────────────────────────────────────
        req_since_persona += 1
        if req_since_persona >= next_persona_at:
            sess = amz.make_session()
            req_since_persona = 0
            next_persona_at = random.randint(*PERSONA_EVERY)

    print(f"[{_ts()}] Runner arrêté. Stats finales: {q.stats(c)}", flush=True)
    c.close()


if __name__ == "__main__":
    main()
