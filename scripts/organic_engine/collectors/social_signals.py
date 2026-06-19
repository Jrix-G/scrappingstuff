"""Signaux sociaux enrichis — Reddit JSON + Google Autocomplete.

Complément à reddit_mentions.py (RSS, fréquence) et tiktok_trending.py (hashtag views).
Ce module apporte :
  - Reddit JSON non-authentifié : nb_posts_30j, nb_posts_90j, avg_score, velocity_ratio
  - Google Autocomplete : position du keyword dans les suggestions (popularité relative)

Reddit JSON (reddit.com/search.json) fonctionne sans OAuth en 2025 avec le bon
User-Agent. Rate limit réel : ~10-15 req/min. On garde ≥5s entre requêtes.
Les upvotes sont fiables pour les posts de +24h (fuzzing négligeable).

Fallback automatique vers le RSS si le JSON retourne 403/429.
Cache disque TTL 6h (même politique que reddit_mentions.py).

Usage standalone :
    python3 -m collectors.social_signals "robot vacuum"
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

# ── Constantes ────────────────────────────────────────────────────────────────

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
_CACHE_DIR      = Path(__file__).resolve().parent.parent / ".social_cache"
_CACHE_TTL      = 6 * 3600      # 6h : frais sans marteler Reddit
_MIN_INTERVAL   = 5.0           # secondes entre requêtes Reddit JSON
_last_req_ts    = 0.0

_DEFAULT_SUBS = [
    "shutupandtakemymoney", "BuyItForLife", "gadgets",
    "DidntKnowIWantedThat", "INEEEEDIT", "ProductPorn",
]


# ── Cache disque ──────────────────────────────────────────────────────────────

def _cache_path(key: str) -> Path:
    h = hashlib.sha256(key.encode()).hexdigest()[:20]
    return _CACHE_DIR / f"{h}.json"


def _cache_get(key: str) -> dict | None:
    p = _cache_path(key)
    if not p.exists():
        return None
    try:
        if time.time() - p.stat().st_mtime > _CACHE_TTL:
            return None
        return json.loads(p.read_text())
    except Exception:
        return None


def _cache_put(key: str, data: dict) -> None:
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _cache_path(key).write_text(json.dumps(data))
    except Exception:
        pass  # best-effort


# ── Résultat ──────────────────────────────────────────────────────────────────

@dataclass(slots=True)
class RedditSignal:
    keyword: str
    nb_posts_30j: int
    nb_posts_90j: int
    avg_score: float        # upvotes nets moyens (posts 30j)
    avg_comments: float     # commentaires moyens (posts 30j)
    velocity_ratio: float   # nb_posts_30j / max(nb_posts_90j, 1)
    source: str             # "json" | "rss_fallback" | "empty"

    @property
    def velocity_score(self) -> float:
        """Score 0-100 : ratio de croissance normalisé (ratio 5x = 100)."""
        return min(100.0, self.velocity_ratio * 20.0)


# ── HTTP poli ─────────────────────────────────────────────────────────────────

def _get_json(url: str, retries: int = 3) -> dict:
    """GET JSON Reddit avec backoff. Lève urllib.error.HTTPError si échec persistant."""
    global _last_req_ts
    last_exc: Exception | None = None
    for attempt in range(retries):
        wait = _MIN_INTERVAL - (time.time() - _last_req_ts)
        if wait > 0:
            time.sleep(wait)
        req = urllib.request.Request(url, headers={
            "User-Agent": _UA,
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
        })
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                _last_req_ts = time.time()
                return json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            _last_req_ts = time.time()
            last_exc = exc
            if exc.code in (429, 500, 502, 503):
                time.sleep(2 ** attempt * 5.0)   # backoff 5s → 10s → 20s
                continue
            raise  # 403 → on re-raise pour fallback RSS
        except (urllib.error.URLError, TimeoutError) as exc:
            last_exc = exc
            time.sleep(2 ** attempt * 3.0)
    raise urllib.error.URLError(f"Reddit JSON indisponible : {last_exc}")


# ── Fallback RSS → fréquence uniquement ──────────────────────────────────────

def _reddit_via_rss(keyword: str, subreddits: list[str]) -> tuple[int, int]:
    """Fallback RSS : compte les posts 30j et 90j (sans score ni commentaires).

    Réutilise le flux RSS déjà scrappé par reddit_mentions.py si disponible.
    """
    try:
        from .reddit_mentions import fetch_mentions
        ts, vals, meta = fetch_mentions(keyword, subreddits=subreddits, days=90)
    except Exception:
        return 0, 0
    # ts = jours depuis t0 (il y a 90j), vals = mentions/semaine
    # Sépare 30j (ts >= 60) vs 90j (ts < 60)
    posts_30 = int(sum(v for t, v in zip(ts, vals) if t >= 60))
    posts_90 = int(sum(v for t, v in zip(ts, vals) if t < 60))
    return posts_30, posts_90


# ── Reddit JSON principal ─────────────────────────────────────────────────────

def _reddit_via_json(keyword: str, subreddits: list[str]) -> tuple[list[dict], str]:
    """Récupère les posts Reddit via l'endpoint .json (sans OAuth).

    Pagine une seule fois (max 100 posts) — suffisant pour la vélocité.
    Renvoie (posts_bruts, source="json").
    """
    multi = "+".join(subreddits)
    params = urllib.parse.urlencode({
        "q": keyword,
        "restrict_sr": "on",
        "sort": "new",
        "limit": "100",
        "t": "all",
    })
    url = f"https://www.reddit.com/r/{multi}/search.json?{params}"
    data = _get_json(url)
    children = data.get("data", {}).get("children", [])
    return [c["data"] for c in children if c.get("kind") == "t3"], "json"


# ── API publique : SocialSignalScraper ────────────────────────────────────────

class SocialSignalScraper:
    """Signaux sociaux multi-sources pour un keyword produit dropshipping.

    Instancier une fois, appeler fetch_reddit() pour chaque produit.
    Le cache disque (TTL 6h) évite de retaper Reddit entre les runs.

    Exemple :
        scraper = SocialSignalScraper()
        sig = scraper.fetch_reddit("robot vacuum")
        print(sig.velocity_ratio, sig.avg_score, sig.velocity_score)
    """

    def __init__(self, subreddits: list[str] | None = None):
        self.subreddits = subreddits or _DEFAULT_SUBS

    # ── Reddit ────────────────────────────────────────────────────────────────

    def fetch_reddit(self, keyword: str) -> RedditSignal:
        """Retourne nb_posts_30j, nb_posts_90j, avg_score, velocity_ratio.

        Essaie le JSON Reddit. Fallback sur RSS si 403. Cache 6h dans les deux cas.
        """
        cache_key = f"reddit|{keyword}|{'|'.join(self.subreddits)}"
        cached = _cache_get(cache_key)
        if cached is not None:
            return RedditSignal(**cached)

        result = self._fetch_reddit_uncached(keyword)
        _cache_put(cache_key, {
            "keyword": result.keyword,
            "nb_posts_30j": result.nb_posts_30j,
            "nb_posts_90j": result.nb_posts_90j,
            "avg_score": result.avg_score,
            "avg_comments": result.avg_comments,
            "velocity_ratio": result.velocity_ratio,
            "source": result.source,
        })
        return result

    def _fetch_reddit_uncached(self, keyword: str) -> RedditSignal:
        now = time.time()
        w30 = 30 * 86400
        w90 = 90 * 86400
        source = "json"

        try:
            posts, source = _reddit_via_json(keyword, self.subreddits)
        except urllib.error.HTTPError as exc:
            # 403 = JSON bloqué → fallback RSS (fréquence seulement, pas de score)
            if exc.code == 403:
                p30, p90 = _reddit_via_rss(keyword, self.subreddits)
                ratio = p30 / max(p90, 1)
                return RedditSignal(
                    keyword=keyword, nb_posts_30j=p30, nb_posts_90j=p90,
                    avg_score=0.0, avg_comments=0.0,
                    velocity_ratio=ratio, source="rss_fallback",
                )
            posts, source = [], "empty"
        except Exception:
            posts, source = [], "empty"

        if not posts:
            return RedditSignal(
                keyword=keyword, nb_posts_30j=0, nb_posts_90j=0,
                avg_score=0.0, avg_comments=0.0,
                velocity_ratio=0.0, source=source,
            )

        # Fenêtres temporelles
        recent  = [p for p in posts if now - p.get("created_utc", 0) < w30]
        older   = [p for p in posts if w30 <= now - p.get("created_utc", 0) < w90]

        avg_score    = sum(p.get("score", 0) for p in recent) / max(len(recent), 1)
        avg_comments = sum(p.get("num_comments", 0) for p in recent) / max(len(recent), 1)
        ratio        = len(recent) / max(len(older), 1)

        return RedditSignal(
            keyword=keyword,
            nb_posts_30j=len(recent),
            nb_posts_90j=len(older),
            avg_score=round(avg_score, 1),
            avg_comments=round(avg_comments, 1),
            velocity_ratio=round(ratio, 3),
            source=source,
        )

    # ── Google Autocomplete ───────────────────────────────────────────────────

    def google_autocomplete_position(self, keyword: str) -> int:
        """Position 0-9 du keyword dans les suggestions Google du premier mot.

        -1 = absent des 10 suggestions (peu populaire ou trop niche).
         0 = première suggestion (très populaire).

        Signal binaire utile : position <= 4 → keyword dans la demande courante.
        Cache 6h.
        """
        cache_key = f"gac|{keyword}"
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached.get("position", -1)

        position = -1
        try:
            prefix = keyword.split()[0] if keyword.strip() else keyword
            url = (
                "https://suggestqueries.google.com/complete/search?"
                + urllib.parse.urlencode({"q": prefix, "client": "firefox"})
            )
            req = urllib.request.Request(url, headers={"User-Agent": _UA})
            with urllib.request.urlopen(req, timeout=10) as resp:
                suggestions: list[str] = json.loads(resp.read())[1]
            kw_lower = keyword.lower()
            position = next(
                (i for i, s in enumerate(suggestions) if kw_lower in s.lower()),
                -1,
            )
        except Exception:
            pass  # network error → -1 conservative

        _cache_put(cache_key, {"keyword": keyword, "position": position})
        return position

    # ── Score combiné ─────────────────────────────────────────────────────────

    def organic_velocity_score(self, keyword: str) -> dict:
        """Score combiné 0-100 : Reddit (vélocité + engagement) + Autocomplete.

        Retourne un dict avec le score global et les composantes pour traçabilité.
        """
        reddit = self.fetch_reddit(keyword)
        gac_pos = self.google_autocomplete_position(keyword)

        # Composante Reddit : 70% du score
        # velocity_score = ratio normalisé (0-100)
        # engagement_score : avg_score normalisé (seuil 50 upvotes = 100)
        velocity_c   = reddit.velocity_score * 0.50
        engagement_c = min(100.0, reddit.avg_score / 50.0 * 100.0) * 0.20

        # Composante Google Autocomplete : 30%
        # Position 0 = score 100, position 9 = score 10, absent = score 0
        gac_score = max(0.0, (9 - gac_pos) / 9.0 * 100.0) if gac_pos >= 0 else 0.0
        gac_c = gac_score * 0.30

        total = velocity_c + engagement_c + gac_c

        return {
            "keyword": keyword,
            "organic_velocity": round(total, 1),
            "components": {
                "reddit_velocity":   round(velocity_c, 1),
                "reddit_engagement": round(engagement_c, 1),
                "gac_score":         round(gac_c, 1),
            },
            "raw": {
                "nb_posts_30j":    reddit.nb_posts_30j,
                "nb_posts_90j":    reddit.nb_posts_90j,
                "avg_score":       reddit.avg_score,
                "velocity_ratio":  reddit.velocity_ratio,
                "gac_position":    gac_pos,
                "reddit_source":   reddit.source,
            },
        }


# ── Point d'entrée manuel ─────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    kw = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "robot vacuum"
    scraper = SocialSignalScraper()

    print(f"\nKeyword : {kw!r}")
    print("-" * 50)

    reddit = scraper.fetch_reddit(kw)
    print(f"Reddit source    : {reddit.source}")
    print(f"Posts 30j        : {reddit.nb_posts_30j}")
    print(f"Posts 90j        : {reddit.nb_posts_90j}")
    print(f"Velocity ratio   : {reddit.velocity_ratio:.2f}x")
    print(f"Avg score        : {reddit.avg_score:.0f} upvotes")
    print(f"Avg comments     : {reddit.avg_comments:.0f}")
    print(f"Velocity score   : {reddit.velocity_score:.1f}/100")

    gac = scraper.google_autocomplete_position(kw)
    print(f"\nGoogle Autocomplete position : {gac} ({'absent' if gac < 0 else f'#{gac+1}/10'})")

    result = scraper.organic_velocity_score(kw)
    print(f"\nOrganic velocity score : {result['organic_velocity']:.1f}/100")
    for k, v in result["components"].items():
        print(f"  {k:<25} {v:.1f}")
