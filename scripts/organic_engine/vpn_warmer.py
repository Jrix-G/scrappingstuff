"""
VPN cache-warmer — exécuté dans le namespace réseau 'tandor-vpn' par vpn_warmer.sh.

Warm le cache AliExpress (.aliexpress_cache) et Google Trends (.trends_cache)
via l'IP WireGuard active du namespace. Toutes les requêtes HTTP partent
automatiquement par le VPN — aucune config proxy nécessaire.

Codes de sortie (interprétés par vpn_warmer.sh) :
  0  — tous les mots-clés du scope sont en cache : travail terminé
  1  — batch traité, des mots-clés restent (la shell relancera un autre batch)
  2  — IP bloquée (AliExpress punish ou Trends 429 persistant) : rotation demandée
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
import time
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ENGINE_DIR))

# ─── Extraction de mots-clés (même logique qu'enrich.py) ────────────────────

_STOP = {
    "for", "with", "the", "and", "use", "set", "pcs", "pc", "1pc", "mini", "new",
    "of", "to", "in", "a", "an", "portable", "multifunctional", "versatile",
    "professional", "high", "quick", "soft", "outdoor", "indoor", "home", "kids",
    "men", "women", "womens", "mens", "small", "large", "quiet", "rechargeable",
    "plus", "size", "style", "fashion", "fashionable", "casual", "premium",
    "best", "good", "top", "super", "ultra", "hot", "sale", "free", "gift",
}
_SPLIT_TOKENS = {"with", "for"}
_UNIT_RE = re.compile(r"^\d+(\.\d+)?(mah|mm|cm|ml|kg|g|w|v|in|inch|ft|m|l|oz|pcs|pc|x)?$")

EXIT_ALL_DONE  = 0
EXIT_MORE_WORK = 1
EXIT_BLOCKED   = 2


def _keyword(name: str, n_words: int = 2) -> str:
    raw = (name or "").strip()
    if not raw:
        return ""
    head = raw.split(",")[0]
    tokens: list[str] = []
    for tok in head.lower().split():
        t = tok.strip(",.;:()/-")
        if t in _SPLIT_TOKENS:
            break
        tokens.append(t)
    kept = [t for t in tokens
            if t and t not in _STOP and not t.isdigit() and not _UNIT_RE.match(t)]
    return " ".join(kept[-n_words:]) if kept else raw[:30].lower()


def _universe_keywords(db_path: Path, limit: int) -> list[str]:
    """Lit les produits CJ et en extrait les mots-clés uniques (ordonnés par fréquence)."""
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        rows = conn.execute(
            "SELECT name FROM cj_products WHERE name IS NOT NULL ORDER BY rowid"
        ).fetchall()
        conn.close()
    except Exception as exc:
        print(f"[warmer] cj.db inaccessible : {exc}", flush=True)
        return []

    seen: set[str] = set()
    keywords: list[str] = []
    freq: dict[str, int] = {}
    for (name,) in rows:
        kw = _keyword(name)
        if not kw or len(kw) < 4:
            continue
        freq[kw] = freq.get(kw, 0) + 1
        if kw not in seen:
            seen.add(kw)
            keywords.append(kw)

    # Trier par fréquence décroissante : les mots-clés les plus communs sont
    # les plus susceptibles de couvrir un maximum de produits en peu de requêtes.
    keywords.sort(key=lambda k: freq[k], reverse=True)
    return keywords[:limit]


# ─── Vérification de cache (lecture seule, sans import lourd) ────────────────

def _ali_fresh(keyword: str) -> bool:
    from collectors.aliexpress_orders import _cache_get
    return _cache_get(keyword) is not None


def _trends_fresh(keyword: str) -> bool:
    from collectors.google_trends import _cache_get
    return _cache_get(f"{keyword}|today 3-m|") is not None


# ─── Fonctions de collecte ───────────────────────────────────────────────────

def _warm_ali(keyword: str) -> str:
    """'hit' | 'fetched' | 'blocked' | 'error'"""
    if _ali_fresh(keyword):
        return "hit"
    from collectors.aliexpress_orders import fetch_demand, AliExpressBlocked
    try:
        result = fetch_demand(keyword)
        if result.blocked:
            return "blocked"
        return "fetched"
    except AliExpressBlocked:
        return "blocked"
    except Exception as exc:
        print(f"[warmer]   aliexpress erreur : {exc}", flush=True)
        return "error"


def _warm_trends(keyword: str) -> str:
    """'hit' | 'fetched' | 'blocked' | 'error'"""
    if _trends_fresh(keyword):
        return "hit"
    from collectors.google_trends import fetch_interest, TrendsError
    try:
        fetch_interest(keyword)
        return "fetched"
    except TrendsError:
        return "blocked"
    except Exception as exc:
        print(f"[warmer]   trends erreur : {exc}", flush=True)
        return "error"


# ─── Main ────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Tandor VPN cache-warmer")
    parser.add_argument("--target", choices=["aliexpress", "trends", "all"], default="all")
    parser.add_argument("--max-keywords", type=int, default=1000,
                        help="Taille max de l'univers de mots-clés à considérer")
    parser.add_argument("--batch", type=int, default=30,
                        help="Mots-clés à traiter par run avant de rendre la main")
    parser.add_argument("--db", type=str,
                        default=str(ENGINE_DIR / "data" / "cj.db"))
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"[warmer] cj.db introuvable : {db_path}", flush=True)
        return EXIT_ALL_DONE

    do_ali    = args.target in ("aliexpress", "all")
    do_trends = args.target in ("trends", "all")

    print(f"[warmer] Lecture des mots-clés ({db_path.name}) ...", flush=True)
    keywords = _universe_keywords(db_path, args.max_keywords)
    print(f"[warmer] Univers : {len(keywords)} mots-clés uniques", flush=True)

    # Filtrer les mots-clés qui ont encore au moins une source non cachée
    uncached = [
        kw for kw in keywords
        if (do_ali and not _ali_fresh(kw)) or (do_trends and not _trends_fresh(kw))
    ]
    print(f"[warmer] Non cachés : {len(uncached)}", flush=True)

    if not uncached:
        print("[warmer] Tout est en cache — terminé.", flush=True)
        return EXIT_ALL_DONE

    batch = uncached[: args.batch]
    print(f"[warmer] Batch : {len(batch)} mots-clés", flush=True)

    blocked_streak = 0  # blocages consécutifs → rotation

    for i, kw in enumerate(batch, 1):
        print(f"[warmer] [{i}/{len(batch)}] '{kw}'", flush=True)

        if do_ali:
            status = _warm_ali(kw)
            print(f"[warmer]   aliexpress → {status}", flush=True)
            if status == "blocked":
                blocked_streak += 1
                if blocked_streak >= 2:
                    print("[warmer] AliExpress bloqué — rotation VPN demandée", flush=True)
                    return EXIT_BLOCKED
            elif status in ("fetched", "hit"):
                blocked_streak = 0

        if do_trends:
            status = _warm_trends(kw)
            print(f"[warmer]   trends     → {status}", flush=True)
            if status == "blocked":
                blocked_streak += 1
                if blocked_streak >= 2:
                    print("[warmer] Trends bloqué — rotation VPN demandée", flush=True)
                    return EXIT_BLOCKED
            elif status in ("fetched", "hit"):
                blocked_streak = 0

    remaining = len(uncached) - len(batch)
    if remaining > 0:
        print(f"[warmer] Batch terminé — {remaining} mots-clés restants", flush=True)
        return EXIT_MORE_WORK

    print("[warmer] Tout est traité.", flush=True)
    return EXIT_ALL_DONE


if __name__ == "__main__":
    sys.exit(main())
