#!/usr/bin/env python3
"""Flush des caches fichier (TikTok / Google Suggest) vers cj.db.

Les collecteurs ``tiktok_trending`` et ``suggest_trends`` n'écrivent QUE des caches
disque (``.tiktok_cache/``, ``.trends_cache/suggest_*.json``). Ce script déverse ces
caches dans les tables ``tiktok_snapshots`` / ``suggest_snapshots`` pour qu'ils
deviennent lisibles par le scoring (via ``signals.db_signals``).

Idempotent : dédupe sur la clé primaire (keyword, observed_at) via INSERT OR IGNORE.
Sert pour le flush one-shot initial ET la persistance récurrente nightly (appelé
depuis tandor_scrape.sh après chaque collecte).

Usage :
    python3 flush_signals.py --target tiktok
    python3 flush_signals.py --target suggest
    python3 flush_signals.py --target all
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ENGINE = Path(__file__).resolve().parent
sys.path.insert(0, str(ENGINE))

import demand_queue as q
from collectors import reddit_mentions as rm

TIKTOK_CACHE = ENGINE / ".tiktok_cache"
TRENDS_CACHE = ENGINE / ".trends_cache"
REDDIT_CACHE = ENGINE / ".reddit_cache"
_ATOM = {"a": "http://www.w3.org/2005/Atom"}


def _mtime_iso(p: Path) -> str:
    """mtime du fichier en ISO UTC — sert d'observed_at faute de date interne."""
    return datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc).isoformat()


def flush_tiktok(conn: sqlite3.Connection) -> int:
    """Déverse .tiktok_cache/ -> tiktok_snapshots. Renvoie le nb de lignes insérées.

    Ignore les entrées bloquées (donnée indisponible) et celles sans viewCount
    (un 0/None lu comme « zéro vue » fausserait la vélocité). observed_at = mtime.
    """
    if not TIKTOK_CACHE.exists():
        return 0
    inserted = 0
    for f in TIKTOK_CACHE.glob("*.json"):
        try:
            d = json.loads(f.read_text())
        except Exception:
            continue
        if d.get("blocked") or d.get("viewCount") is None:
            continue
        kw = d.get("keyword")
        if not kw:
            continue
        cur = conn.execute(
            "INSERT OR IGNORE INTO tiktok_snapshots(keyword, observed_at, view_count, video_count) "
            "VALUES(?,?,?,?)",
            (kw, _mtime_iso(f), d.get("viewCount"), d.get("videoCount")),
        )
        inserted += cur.rowcount
    conn.commit()
    return inserted


def flush_suggest(conn: sqlite3.Connection) -> int:
    """Déverse .trends_cache/suggest_*.json -> suggest_snapshots. Nb de lignes insérées.

    Chaque fichier porte une LISTE de snapshots journaliers {t, score, saturation,...}.
    observed_at = snap['t'] (date du snapshot). direction = NULL : c'est une dérivée
    série-niveau (cf. suggest_trends._direction), pas une grandeur per-snapshot.
    keyword reconstruit depuis le nom de fichier (``suggest_<safe>.json`` -> '_'→' ').
    """
    if not TRENDS_CACHE.exists():
        return 0
    inserted = 0
    for f in TRENDS_CACHE.glob("suggest_*.json"):
        try:
            snaps = json.loads(f.read_text())
        except Exception:
            continue
        if not isinstance(snaps, list):
            continue
        # 'suggest_beach_sandals.json' -> 'beach sandals' (round-trip du safe-name :
        # lossless pour les mots-clés alnum+espaces, cas dominant du pipeline).
        keyword = f.stem[len("suggest_"):].replace("_", " ").strip()
        if not keyword:
            continue
        for snap in snaps:
            t = snap.get("t")
            score = snap.get("score")
            if not t or score is None:
                continue
            cur = conn.execute(
                "INSERT OR IGNORE INTO suggest_snapshots(keyword, observed_at, score, saturation, direction) "
                "VALUES(?,?,?,?,?)",
                (keyword, t, float(score), snap.get("saturation"), None),
            )
            inserted += cur.rowcount
    conn.commit()
    return inserted


def _reddit_keyword(root: ET.Element) -> str | None:
    """Reconstruit le mot-clé recherché depuis le ``<id>`` du flux Atom mis en cache.

    L'id porte l'URL de recherche, p.ex. ``/r/a+b/search.rss?q=huggie+earrings&...``.
    On en extrait le paramètre ``q`` (parse_qs décode le ``+`` en espace) — exactement
    le mot-clé passé à ``reddit_mentions.fetch_mentions`` au moment du fetch."""
    el = root.find("a:id", _ATOM)
    if el is None or not el.text or "?" not in el.text:
        return None
    qs = urllib.parse.parse_qs(el.text.split("?", 1)[1])
    kw = (qs.get("q") or [None])[0]
    return kw.strip() if kw else None


def flush_reddit(conn: sqlite3.Connection) -> int:
    """Déverse .reddit_cache/ (flux RSS Atom) -> reddit_snapshots. Nb de lignes insérées.

    Chaque fichier est UN flux de recherche multi-subreddit pour un mot-clé. On
    réutilise les helpers de ``reddit_mentions`` (parse + filtre de pertinence + même
    fenêtre 365 j) pour compter les mentions PERTINENTES dans le temps — le même signal
    que celui calculé en live. observed_at = mtime du cache (date du fetch, comme
    flush_tiktok). mentions = nb de posts pertinents dans la fenêtre ; score = nb total
    d'entrées du flux (proxy d'activité grossier ; le RSS n'expose AUCUN upvote/score).
    Les mots-clés à 0 mention sont conservés : un point de base à 0 est une observation
    valide (absence de buzz) qui permettra à la vélocité de naître au prochain run."""
    if not REDDIT_CACHE.exists():
        return 0
    horizon = time.time() - 365 * 86400
    inserted = 0
    for f in REDDIT_CACHE.glob("*.xml"):
        try:
            text = f.read_text()
            root = ET.fromstring(text)
        except Exception:
            continue
        kw = _reddit_keyword(root)
        if not kw:
            continue
        entries = rm._parse_entries(text)
        kept = sum(1 for title, created in entries
                   if created >= horizon and rm._is_relevant(kw, title))
        cur = conn.execute(
            "INSERT OR IGNORE INTO reddit_snapshots(keyword, observed_at, mentions, score) "
            "VALUES(?,?,?,?)",
            (kw, _mtime_iso(f), int(kept), float(len(entries))),
        )
        inserted += cur.rowcount
    conn.commit()
    return inserted


def main() -> int:
    parser = argparse.ArgumentParser(description="Flush caches fichier -> snapshots cj.db")
    parser.add_argument("--target", choices=["tiktok", "suggest", "reddit", "all"], default="all")
    args = parser.parse_args()

    c = q.connect()
    q.init_schema(c)  # garantit l'existence des tables (idempotent, IF NOT EXISTS)

    total = 0
    if args.target in ("tiktok", "all"):
        n = flush_tiktok(c)
        print(f"[flush] tiktok_snapshots  : +{n} lignes")
        total += n
    if args.target in ("suggest", "all"):
        n = flush_suggest(c)
        print(f"[flush] suggest_snapshots : +{n} lignes")
        total += n
    if args.target in ("reddit", "all"):
        n = flush_reddit(c)
        print(f"[flush] reddit_snapshots  : +{n} lignes")
        total += n
    c.close()
    print(f"[flush] total inséré : {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
