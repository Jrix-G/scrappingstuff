"""Collecteur TikTok — signal viral précoce des produits.

Scrape les pages hashtag TikTok pour extraire le nombre de vues/vidéos d'un
mot-clé produit. Un hashtag qui explose (#ceilingfan, #robotvacuum) est le
signe le plus précoce du phénomène « TikTok made me buy it ».

Technique : GET de l'endpoint web-mobile
https://m.tiktok.com/api/challenge/detail/?challengeName=<tag>&aid=1988 qui
renvoie directement un JSON {challengeInfo:{statsV2:{viewCount,videoCount}}}.
Pas d'API officielle, pas de cookies, pas de signature (msToken/X-Bogus), pas de
navigateur. L'ancienne page /tag/ HTML ne porte plus les stats (SSR déprécié par
TikTok) — d'où l'abandon. Dégradation gracieuse si TikTok bloque.

Cache : 24 h (un signal viral ne change pas à l'heure).
Rate-limit : ≥ 2 s entre requêtes réseau (endpoint testé à 100 req/min sans blocage).
"""

from __future__ import annotations

import hashlib
import json
import random
import re
import time
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

from utils import http  # transport partagé curl_cffi chrome131 (→ urllib de repli)

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
_MIN_INTERVAL    = 2.0           # secondes entre deux requêtes réseau
_last_req_ts     = 0.0

_API_URL = "https://m.tiktok.com/api/challenge/detail/?challengeName={tag}&aid=1988"

# Regex de secours si le JSON ne parse pas
_VIEW_RE  = re.compile(r'"viewCount"\s*:\s*"?(\d+)')
_VIDEO_RE = re.compile(r'"videoCount"\s*:\s*"?(\d+)')


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
    # Cadence polie + jitter : drainer ~4000 mots-clés/nuit est plus de volume que
    # l'ancien batch unique de 400, donc on désynchronise les requêtes pour ne pas
    # présenter un métronome parfait à l'anti-bot (le pacing reste ≥ _MIN_INTERVAL).
    wait = _MIN_INTERVAL + random.uniform(0.3, 1.2) - (time.time() - _last_req_ts)
    if wait > 0:
        time.sleep(wait)

    url = _API_URL.format(tag=urllib.parse.quote(hashtag))
    try:
        res = http.get_text(url, headers={
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://www.tiktok.com/",
        }, timeout=20)
    finally:
        _last_req_ts = time.time()

    if res.status == 404:
        raise TikTokNoData(f"Hashtag #{hashtag} introuvable (HTTP 404)")
    if res.status == 0 or res.status in (403, 429) or res.status >= 500:
        # échec transport / 4xx-5xx = l'IP/endpoint est rejeté → vrai blocage
        raise TikTokBlocked(f"HTTP {res.status} sur l'API challenge (#{hashtag})")

    body = res.text
    # SOFT-BLOCK : TikTok renvoie de plus en plus un HTTP 200 avec un corps vide ou
    # altéré (challengeInfo absent, statusCode ≠ 0, HTML de challenge) au lieu d'un
    # 4xx franc. Avant, ce cas était parsé en (None, None) puis MIS EN CACHE 24 h
    # comme « no data » → faux négatif persistant sur un mot-clé peut-être viral.
    # On le traite désormais comme un blocage : pas de cache, réessai ultérieur.
    # Un hashtag réellement inconnu, lui, renvoie un JSON valide (challengeInfo
    # présent + statusCode 0) avec des stats vides → reste un « no data » légitime.
    try:
        data = json.loads(body)
        valid = (isinstance(data, dict) and "challengeInfo" in data
                 and data.get("statusCode", -1) == 0)
    except Exception:
        valid = False
    if not valid:
        raise TikTokBlocked(
            f"Soft-block TikTok (HTTP 200 sans réponse API valide, #{hashtag})")

    return body


# ── Parsing ───────────────────────────────────────────────────────────────────

def _parse_stats(body: str) -> tuple[int | None, int | None]:
    """Extrait (viewCount, videoCount) depuis le JSON de l'API challenge.

    Réponse type : {"challengeInfo":{"stats":{...},"statsV2":{"viewCount":"...",
    "videoCount":"..."}},"statusCode":0}. Hashtag inconnu → challengeInfo vide.
    """
    # 1) Parse JSON direct (statsV2 = chaînes, stats = entiers selon les cas)
    try:
        data = json.loads(body)
        ci = data.get("challengeInfo") or {}
        stats = ci.get("statsV2") or ci.get("stats") or {}
        if stats:
            return (
                _to_int(stats.get("viewCount") or stats.get("videoViewCount")),
                _to_int(stats.get("videoCount")),
            )
    except (json.JSONDecodeError, AttributeError):
        pass

    # 2) Fallback regex si la forme du JSON change
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
        # le cache est sérialisé via as_dict() (camelCase) → remappe en champs dataclass
        return TikTokHashtagStats(
            keyword=cached.get("keyword", keyword),
            hashtag=cached.get("hashtag", hashtag),
            view_count=cached.get("viewCount"),
            video_count=cached.get("videoCount"),
            blocked=cached.get("blocked", False),
        )

    try:
        body = _fetch_page(hashtag)
    except TikTokBlocked:
        result = TikTokHashtagStats(keyword=keyword, hashtag=hashtag, blocked=True)
        return result
    except TikTokNoData:
        result = TikTokHashtagStats(keyword=keyword, hashtag=hashtag)
        _cache_put(hashtag, result.as_dict())
        return result
    except Exception:
        # Le transport (utils.http) ne lève pas ; tout imprévu = blocage (non caché).
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
