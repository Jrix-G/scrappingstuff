"""Collecteur TikTok — signal viral précoce des produits.

Scrape les pages hashtag TikTok pour extraire le nombre de vues/vidéos d'un
mot-clé produit. Un hashtag qui explose (#ceilingfan, #robotvacuum) est le
signe le plus précoce du phénomène « TikTok made me buy it ».

Technique : GET de https://www.tiktok.com/tag/<keyword> — TikTok injecte un
JSON de réhydratation dans le HTML (balise <script id="__UNIVERSAL_DATA_FOR_REHYDRATION__">)
qui contient les stats du challenge (viewCount, videoCount). Pas d'API officielle,
pas de cookies, pas de navigateur. Dégradation gracieuse si TikTok bloque.

Cache : 24 h (un signal viral ne change pas à l'heure).
Rate-limit : ≥ 15 s entre requêtes réseau (TikTok détecte les rafales).
"""

from __future__ import annotations

import gzip
import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

_UA_DESKTOP = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)
_UA_MOBILE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.4 Mobile/15E148 Safari/604.1"
)

_CACHE_DIR       = Path(__file__).resolve().parent.parent / ".tiktok_cache"
_CACHE_TTL       = 24 * 3600     # 24 h : la viralité ne se mesure pas à l'heure
_MIN_INTERVAL    = 15.0          # secondes entre deux requêtes réseau
_last_req_ts     = 0.0

# Regex de secours si le JSON n'est pas trouvé dans <script>
_VIEW_RE  = re.compile(r'"viewCount"\s*:\s*(\d+)')
_VIDEO_RE = re.compile(r'"videoCount"\s*:\s*(\d+)')

# Marqueurs de blocage TikTok
_BLOCK_MARKERS = ("tiktok.com/login", "verify.tiktok.com", "captcha", "/robot")


class TikTokBlocked(Exception):
    """TikTok a retourné une page de challenge/captcha."""


class TikTokNoData(Exception):
    """Page accessible mais aucune donnée hashtag trouvée."""


@dataclass(slots=True)
class TikTokHashtagStats:
    keyword: str
    hashtag: str           # tel que normalisé (ex. "ceiling fan" → "ceilingfan")
    view_count: int | None = None
    video_count: int | None = None
    blocked: bool = False  # True = donnée indisponible (≠ hashtag inexistant)

    def as_dict(self) -> dict:
        return {
            "keyword": self.keyword,
            "hashtag": self.hashtag,
            "viewCount": self.view_count,
            "videoCount": self.video_count,
            "blocked": self.blocked,
        }

    @property
    def viral_score(self) -> float | None:
        """Score simple 0-100 basé sur le nombre de vues (log-normalisé sur 10 B)."""
        if self.view_count is None:
            return None
        import math
        return min(100.0, math.log10(max(1, self.view_count)) / math.log10(1e10) * 100)


# ── Cache disque ─────────────────────────────────────────────────────────────

def _cache_path(hashtag: str) -> Path:
    return _CACHE_DIR / f"{hashlib.sha256(hashtag.encode()).hexdigest()[:20]}.json"


def _cache_get(hashtag: str) -> dict | None:
    p = _cache_path(hashtag)
    if not p.exists():
        return None
    try:
        if time.time() - p.stat().st_mtime > _CACHE_TTL:
            return None
        return json.loads(p.read_text())
    except Exception:
        return None


def _cache_put(hashtag: str, data: dict) -> None:
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _cache_path(hashtag).write_text(json.dumps(data))
    except Exception:
        pass


# ── Normalisation ─────────────────────────────────────────────────────────────

def _to_hashtag(keyword: str) -> str:
    """'ceiling fan' → 'ceilingfan'  (TikTok hashtags : pas d'espace)."""
    return re.sub(r"[^a-z0-9]", "", keyword.lower())


# ── Requête HTTP (polie, avec User-Agent rotatif) ────────────────────────────

def _fetch_page(hashtag: str) -> str:
    global _last_req_ts
    wait = _MIN_INTERVAL - (time.time() - _last_req_ts)
    if wait > 0:
        time.sleep(wait)

    url = f"https://www.tiktok.com/tag/{urllib.parse.quote(hashtag)}"

    # TikTok sert du HTML différent selon le UA — on essaie mobile d'abord
    # (pages plus légères, moins de JS anti-bot)
    for ua in (_UA_MOBILE, _UA_DESKTOP):
        req = urllib.request.Request(url, headers={
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Referer": "https://www.tiktok.com/",
            "Connection": "keep-alive",
        })
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                raw = resp.read()
                if "gzip" in (resp.headers.get("Content-Encoding") or ""):
                    raw = gzip.decompress(raw)
                body = raw.decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            if exc.code in (404,):
                raise TikTokNoData(f"Hashtag #{hashtag} introuvable (HTTP 404)")
            raise
        finally:
            _last_req_ts = time.time()

        if any(m in body for m in _BLOCK_MARKERS) or len(body) < 2000:
            raise TikTokBlocked(f"Page de blocage/captcha TikTok (hashtag=#{hashtag})")

        if "__UNIVERSAL_DATA_FOR_REHYDRATION__" in body or "viewCount" in body:
            return body

    raise TikTokNoData(f"Aucune donnée JSON dans la page de #{hashtag}")


# ── Parsing ───────────────────────────────────────────────────────────────────

def _parse_stats(body: str) -> tuple[int | None, int | None]:
    """Extrait (viewCount, videoCount) depuis le JSON embarqué TikTok."""
    # 1) Cherche la balise de réhydratation SSR
    m = re.search(
        r'<script[^>]+id=["\']__UNIVERSAL_DATA_FOR_REHYDRATION__["\'][^>]*>(.*?)</script>',
        body, re.DOTALL
    )
    if m:
        try:
            data = json.loads(m.group(1))
            # Navigue dans la structure TikTok (plusieurs niveaux possibles)
            challenge = (
                data.get("__DEFAULT_SCOPE__", {})
                    .get("webapp.challenge-detail", {})
                    .get("challengeInfo", {})
                    .get("statsV2") or
                data.get("__DEFAULT_SCOPE__", {})
                    .get("webapp.challenge-detail", {})
                    .get("challengeInfo", {})
                    .get("stats")
            )
            if challenge:
                return (
                    _to_int(challenge.get("viewCount") or challenge.get("videoViewCount")),
                    _to_int(challenge.get("videoCount")),
                )
        except (json.JSONDecodeError, AttributeError):
            pass

    # 2) Fallback regex sur le HTML brut
    vm = _VIEW_RE.search(body)
    vim = _VIDEO_RE.search(body)
    return (
        int(vm.group(1)) if vm else None,
        int(vim.group(1)) if vim else None,
    )


def _to_int(val) -> int | None:
    try:
        return int(str(val).replace(",", "").replace(" ", ""))
    except (ValueError, TypeError):
        return None


# ── API publique ──────────────────────────────────────────────────────────────

def fetch_hashtag(keyword: str) -> TikTokHashtagStats:
    """Récupère les stats du hashtag TikTok correspondant au mot-clé produit.

    Sert le cache 24 h si disponible. Dégradation gracieuse sur blocage.
    """
    hashtag = _to_hashtag(keyword)
    cached = _cache_get(hashtag)
    if cached is not None:
        return TikTokHashtagStats(**cached)

    try:
        body = _fetch_page(hashtag)
    except TikTokBlocked:
        result = TikTokHashtagStats(keyword=keyword, hashtag=hashtag, blocked=True)
        return result
    except TikTokNoData:
        result = TikTokHashtagStats(keyword=keyword, hashtag=hashtag)
        _cache_put(hashtag, result.as_dict())
        return result
    except (urllib.error.URLError, TimeoutError):
        result = TikTokHashtagStats(keyword=keyword, hashtag=hashtag, blocked=True)
        return result

    views, videos = _parse_stats(body)
    result = TikTokHashtagStats(
        keyword=keyword, hashtag=hashtag,
        view_count=views, video_count=videos,
    )
    _cache_put(hashtag, result.as_dict())
    return result


def tiktok_raw_signal(keyword: str):
    """Construit un ``RawSignal('tiktok', ...)`` — valeur unique (score viral)."""
    from signals.features import RawSignal
    stats = fetch_hashtag(keyword)
    if stats.blocked or stats.view_count is None:
        return RawSignal("tiktok", [], [])
    score = stats.viral_score or 0.0
    return RawSignal("tiktok", [0.0], [score])


# ── Point d'entrée manuel ─────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    kw = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "ceiling fan"
    stats = fetch_hashtag(kw)
    if stats.blocked:
        print(f"⚠ #{stats.hashtag} : IP bloquée ou captcha")
    elif stats.view_count is None:
        print(f"#{stats.hashtag} : aucune donnée (hashtag inconnu ou page vide)")
    else:
        print(f"#{stats.hashtag}")
        print(f"  Vues  : {stats.view_count:,}")
        print(f"  Vidéos: {stats.video_count or '?':,}")
        print(f"  Score viral : {stats.viral_score:.1f}/100")
