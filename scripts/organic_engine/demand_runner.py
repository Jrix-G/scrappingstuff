#!/usr/bin/env python3
"""Runner 24/7 du signal demande Tandor.

Boucle principale : scrape Amazon (« bought in past month ») au rythme 3–6 s/produit,
en priorisant la pile (couverture max puis vélocité). AliExpress n'est PLUS scrapé ici
(délégué à un worker dédié single-IP) ; le runner se contente de remplir aliexpress_queue.

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
import notify_discord as notify
from collectors import amazon_demand as amz

# ── Pacing (demandé : 5–10 s aléatoire entre produits Amazon) ────────────────
PACE_MIN, PACE_MAX = 3.0, 6.0    # cadence accélérée (ban mesuré ~0,2 %, backoff couvre la dérive)
BREAK_EVERY = (35, 60)           # break humain toutes les N req (moins fréquent)
BREAK_SECONDS = (90, 180)        # durée du break : 1,5–3 min
PERSONA_EVERY = (150, 400)       # rotation d'identité toutes les N req
COOLDOWNS = [120, 300, 900, 1800, 3600]   # backoff blocage : 2,5,15,30,60 min
QUIET_HOURS = (2, 6)             # heures creuses locales (léger ralenti ×1.5)

# ── AliExpress : PLUS scrapé ici ─────────────────────────────────────────────
# L'ancienne boucle tapait toutes les 5,5 min — PLUS COURT que le cooldown ~30 min
# d'AliExpress → elle re-déclenchait le ban en boucle et l'IP maison ne guérissait
# jamais. AliExpress est désormais collecté par un worker dédié (extraction-max +
# cadence calée sur le cooldown, single-IP). Le runner se contente de REMPLIR
# aliexpress_queue (via record_amazon → seuil ALI_THRESHOLD).

# ── Heartbeat Discord (preuve de vie même si tout est bloqué) ────────────────
HEARTBEAT_S = 3600               # un message de synthèse toutes les heures

_RUN = True


def _fmt_stats(s: dict) -> str:
    return (f"{s.get('scraped', 0)}/{s.get('total_keywords', 0)} scrapés · "
            f"{s.get('hot_products', 0)} hot · "
            f"{s.get('aliexpress_queued', 0)} ali en file")


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


def main() -> None:
    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    c = q.connect()
    q.init_schema(c)
    n = q.rebuild_from_cj(c)
    print(f"[{_ts()}] Démarrage runner demande — {n} mots-clés en file. Stats: {q.stats(c)}", flush=True)
    notify.send(f"🚀 **Runner demande démarré** — {n} mots-clés en file · {_fmt_stats(q.stats(c))}", ping=True)
    last_heartbeat = time.time()

    sess = amz.make_session()
    consec_blocks = 0
    req_since_break = 0
    req_since_persona = 0
    next_break_at = random.randint(*BREAK_EVERY)
    next_persona_at = random.randint(*PERSONA_EVERY)
    done = 0

    while _RUN:
        # ── Heartbeat Discord (preuve de vie) ────────────────────────────────
        if time.time() - last_heartbeat >= HEARTBEAT_S:
            notify.send(f"💓 **Runner OK** — {done} produits scrapés cette session · "
                        f"{_fmt_stats(q.stats(c))} · {consec_blocks} blocage(s) consécutif(s)")
            last_heartbeat = time.time()

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
            if consec_blocks == 1:               # 1er blocage de la série (évite le spam)
                notify.blocked(kw, source="Amazon")
            sess = amz.make_session()           # identité fraîche
            req_since_persona = 0
            next_persona_at = random.randint(*PERSONA_EVERY)
            if consec_blocks >= 8:               # IP en grande difficulté → longue pause
                print(f"[{_ts()}] ⚠⚠ blocages répétés — pause 6 h.", flush=True)
                notify.send("⛔ **Amazon — blocages répétés (×8)** : IP en grande difficulté, "
                            "pause 6 h du scraping Amazon.", ping=True)
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
        pace = random.uniform(PACE_MIN, PACE_MAX) * (1.5 if _in_quiet_hours() else 1.0)
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
