#!/usr/bin/env python3
"""Worker Reddit — collecte récurrente, reprenable et à débit borné des mentions.

Reddit n'était jusqu'ici scrapé que sur quelques mots-clés (top-N manuel d'enrich.py).
Ce worker couvre PROGRESSIVEMENT tout l'univers Amazon (~8 000 mots-clés) en empilant
un snapshot daté par mot-clé dans ``reddit_snapshots`` (lu par le scoring via
``signals.db_signals``). Même esprit que ``sales_worker.py`` : file persistée en base
(resumable), budget borné par run, cadence polie, filtrage par shard multi-nœuds.

Source retenue : ``collectors.reddit_mentions`` (flux RSS public) — et NON
``social_signals`` (endpoint ``.json`` bloqué en 403, donc fragile à grande échelle).
Le RSS répond 200, ne coûte qu'1 requête multi-subreddit par mot-clé, possède déjà
cache disque (TTL 6 h) + backoff + intervalle mini : sûr et soutenable en masse.

Pas de score d'upvote dans le RSS : mentions = nb de posts pertinents (fenêtre 365 j) ;
score = nb total d'entrées du flux (proxy d'activité grossier). Un snapshot à 0 mention
est conservé (observation valide : absence de buzz, base pour une future vélocité).

File ``reddit_queue`` : CREATE TABLE IF NOT EXISTS (même modèle que ebay_queue/dhgate_queue),
seedée depuis amazon_queue. Priorité : jamais scrapé d'abord, puis re-confirmation due
(âge >= min_age_h), du plus ancien au plus récent.

Usage :
    python3 reddit_worker.py --budget 200
    python3 reddit_worker.py --budget 50 --min-age-h 168
"""
from __future__ import annotations

import argparse
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
from collectors import reddit_mentions as rm
from shard import in_shard, describe as shard_describe

# Cadence entre deux mots-clés. reddit_mentions impose déjà _MIN_REQUEST_INTERVAL=3 s
# entre appels RÉSEAU (et sert le cache sans réseau) ; on ajoute une petite marge.
PACE_SECONDS = (1.0, 3.0)
# Re-confirmation : Reddit bouge lentement → 1×/semaine suffit (et le cache TTL est 6 h).
DEFAULT_MIN_AGE_H = 168


_RUN = True


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _stop(*_):
    global _RUN
    _RUN = False
    print(f"[{_ts()}] arrêt demandé — fin de l'itération en cours…", flush=True)


def ensure_queue(c) -> int:
    """Crée reddit_queue (IF NOT EXISTS) et la (re)seed depuis amazon_queue.

    Idempotent : conserve last_scraped/scrape_count des entrées existantes, n'insère
    que les nouveaux mots-clés. Renvoie le total d'entrées de la file."""
    c.execute(
        """CREATE TABLE IF NOT EXISTS reddit_queue (
               keyword TEXT PRIMARY KEY,
               enqueued_at TEXT,
               last_scraped TEXT,
               scrape_count INTEGER DEFAULT 0,
               blocked_count INTEGER DEFAULT 0
           )"""
    )
    rows = c.execute("SELECT keyword FROM amazon_queue WHERE keyword IS NOT NULL").fetchall()
    for (kw,) in rows:
        c.execute(
            "INSERT OR IGNORE INTO reddit_queue(keyword, enqueued_at) VALUES(?,?)",
            (kw, _now()),
        )
    c.commit()
    return c.execute("SELECT COUNT(*) FROM reddit_queue").fetchone()[0]


def next_keyword(c, min_age_h: int) -> str | None:
    """Prochain mot-clé : jamais scrapé d'abord, puis re-confirmation due (plus ancien
    d'abord). Filtré sur le shard de ce nœud (Pi et VPS se partagent l'univers).

    Pour le cold start on traite les mots-clés les plus DEMANDÉS d'abord (jointure sur
    amazon_queue.last_max_bought) : le signal Reddit est ainsi disponible en priorité
    sur les produits qui comptent pour le scoring (même philosophie « intéressant
    d'abord » que la file Amazon)."""
    for (kw,) in c.execute(
        "SELECT r.keyword FROM reddit_queue r "
        "LEFT JOIN amazon_queue a ON a.keyword = r.keyword "
        "WHERE r.scrape_count=0 ORDER BY a.last_max_bought DESC NULLS LAST, r.keyword"
    ).fetchall():
        if in_shard(kw):
            return kw
    now = datetime.now(timezone.utc)
    for kw, last in c.execute(
        "SELECT keyword, last_scraped FROM reddit_queue "
        "WHERE last_scraped IS NOT NULL ORDER BY last_scraped ASC"
    ).fetchall():
        if not in_shard(kw):
            continue
        try:
            age_h = (now - datetime.fromisoformat(last)).total_seconds() / 3600
        except Exception:
            age_h = 1e9
        if age_h >= min_age_h:
            return kw
    return None


def record(c, keyword: str, mentions: int, score: float) -> None:
    """Persiste le snapshot Reddit + marque le mot-clé scrapé dans la file."""
    c.execute(
        "INSERT OR IGNORE INTO reddit_snapshots(keyword, observed_at, mentions, score) "
        "VALUES(?,?,?,?)",
        (keyword, _now(), int(mentions), float(score)),
    )
    c.execute(
        "UPDATE reddit_queue SET last_scraped=?, scrape_count=scrape_count+1 WHERE keyword=?",
        (_now(), keyword),
    )
    c.commit()


def _sleep(seconds: float) -> None:
    """Sleep interruptible (réagit à SIGTERM en <1 s)."""
    end = time.time() + seconds
    while _RUN and time.time() < end:
        time.sleep(min(1.0, end - time.time()))


def main() -> int:
    ap = argparse.ArgumentParser(description="Worker Reddit (mentions RSS, débit borné)")
    ap.add_argument("--budget", type=int, default=200,
                    help="Nb max de mots-clés traités avant de rendre la main")
    ap.add_argument("--min-age-h", type=int, default=DEFAULT_MIN_AGE_H,
                    help="Âge mini avant re-confirmation d'un mot-clé déjà scrapé")
    args = ap.parse_args()

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    c = q.connect()
    q.init_schema(c)            # garantit reddit_snapshots (idempotent, IF NOT EXISTS)
    total = ensure_queue(c)
    print(f"[{_ts()}] Worker Reddit démarré — {shard_describe()} · file {total} "
          f"(budget {args.budget}, min-age {args.min_age_h}h)", flush=True)
    notify.send(f"👽 **Worker Reddit démarré** — budget {args.budget} mot(s)-clé(s)")

    done = hot = 0
    while _RUN and done < args.budget:
        kw = next_keyword(c, args.min_age_h)
        if kw is None:
            print(f"[{_ts()}] File Reddit à jour, rien de dû — fin.", flush=True)
            break
        try:
            _ts_days, vals, meta = rm.fetch_mentions(kw)
            mentions = int(meta.get("posts_kept", 0))
            score = float(meta.get("posts_seen", 0))
        except rm.RedditError as exc:
            # RSS indisponible (429/timeout après backoff) : on rend la main, le cron
            # relancera. On NE marque PAS le mot-clé (il restera prioritaire).
            print(f"[{_ts()}] ⚠ RSS indisponible sur « {kw} » : {exc} — on rend la main.",
                  flush=True)
            notify.blocked(kw, source="Reddit")
            break
        except Exception as exc:                  # garde-fou : ne jamais crasher le worker
            print(f"[{_ts()}] ✗ « {kw} » erreur inattendue : {exc}", flush=True)
            _sleep(random.uniform(*PACE_SECONDS))
            continue

        record(c, kw, mentions, score)
        done += 1
        flag = " 🟢" if mentions > 0 else ""
        print(f"[{_ts()}] [{done}/{args.budget}] « {kw} » mentions={mentions} "
              f"seen={int(score)}{flag}", flush=True)
        if mentions > 0:
            hot += 1
        _sleep(random.uniform(*PACE_SECONDS))

    print(f"[{_ts()}] Worker Reddit terminé — {done} mot(s)-clé(s), {hot} avec mention(s).",
          flush=True)
    notify.send(f"✅ **Worker Reddit terminé** — {done} traité(s) · {hot} avec mention(s)")
    c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
