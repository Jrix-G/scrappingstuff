"""Collecteur YouTube — signal de demande via l'API YouTube Data v3 (clé requise).

Contrairement à TikTok/Reddit (scrapés sans clé), YouTube n'expose plus de page
publique exploitable : on passe par l'**API officielle YouTube Data v3**, qui exige
une clé. Pour un mot-clé produit on mesure deux choses :

* **video_count** — ``pageInfo.totalResults`` de ``search.list`` : volume estimé de
  vidéos correspondant au mot-clé (intérêt créateur/contenu autour du produit) ;
* **view_count** — somme des ``statistics.viewCount`` des vidéos retournées
  (``videos.list``) : magnitude réelle d'audience (demande agrégée).

QUOTA (critique). Le quota gratuit par défaut est **10 000 unités/jour**. Coûts :

* ``search.list``  = **100 unités** par appel ;
* ``videos.list``  = **1 unité**  par appel (jusqu'à 50 IDs d'un coup).

Donc un mot-clé = 100 (+1) ≈ 101 unités → **~99 mots-clés/jour MAXIMUM**. Le budget
par run du worker DOIT rester sous ce plafond (cf. youtube_worker.py / youtube_loop.sh).
Couvrir un shard (~4000 mots-clés) prend donc **~6 semaines** à ~95/jour : c'est lent
PAR CONCEPTION, comme prévu pour une source à quota.

CLÉ. Lue depuis la variable d'environnement ``YOUTUBE_API_KEY`` (m+ repli sur le
fichier ``~/discord/.env`` — même mécanisme que ``notify_discord``). Format attendu
dans le .env : ``YOUTUBE_API_KEY=AIza...``. Si la clé est absente, le collecteur lève
``YouTubeError`` AVANT tout appel réseau : il échoue PROPREMENT, ne plante pas le
pipeline nightly (le worker / le step shell traitent ce cas par un skip loggé).

Cache disque 24 h (comme tiktok_trending) : ne jamais regrener le quota pour un même
mot-clé dans la journée.

Aucune dépendance externe : urllib + json (stdlib) uniquement.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

logger = logging.getLogger("tandor.youtube")

_API_BASE = "https://www.googleapis.com/youtube/v3"
_CACHE_DIR = Path(__file__).resolve().parent.parent / ".youtube_cache"
_CACHE_TTL = 24 * 3600          # 24 h : le signal de demande ne se mesure pas à l'heure
_MIN_INTERVAL = 0.5             # politesse réseau (le quota, pas le rate-limit, est la contrainte)
_SEARCH_MAX_RESULTS = 50        # max autorisé par l'API en un appel
_last_req_ts = 0.0

# Coûts en unités de quota (documentés par Google) — exposés pour le budget du worker.
COST_SEARCH = 100
COST_VIDEOS = 1


class YouTubeError(Exception):
    """Erreur d'accès à l'API YouTube Data v3 (clé absente, quota, HTTP, parsing)."""


class YouTubeQuotaError(YouTubeError):
    """Quota journalier dépassé (HTTP 403 quotaExceeded) — arrêter le run."""


# ── Clé API ───────────────────────────────────────────────────────────────────
# Même patron que notify_discord : env d'abord, repli sur ~/discord/.env.
_BOT_ENV = Path(os.getenv("TANDOR_DISCORD_ENV") or (Path.home() / "discord" / ".env"))


def _load_env_file(path: Path) -> dict[str, str]:
    """Parse minimal d'un .env (KEY=VALUE), sans dépendance externe."""
    out: dict[str, str] = {}
    try:
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    except Exception:
        pass
    return out


def get_api_key() -> str | None:
    """Retourne la clé YouTube (env ``YOUTUBE_API_KEY`` ou ligne du ~/discord/.env), ou None."""
    return os.getenv("YOUTUBE_API_KEY") or _load_env_file(_BOT_ENV).get("YOUTUBE_API_KEY")


def has_api_key() -> bool:
    return bool(get_api_key())


# ── Cache disque ────────────────────────────────────────────────────────────────

def _cache_path(keyword: str) -> Path:
    return _CACHE_DIR / f"{hashlib.sha256(keyword.encode()).hexdigest()[:20]}.json"


def _cache_get(keyword: str) -> dict | None:
    p = _cache_path(keyword)
    if not p.exists():
        return None
    try:
        if time.time() - p.stat().st_mtime > _CACHE_TTL:
            return None
        return json.loads(p.read_text())
    except Exception:
        return None


def _cache_put(keyword: str, data: dict) -> None:
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _cache_path(keyword).write_text(json.dumps(data))
    except Exception:
        pass  # cache best-effort


# ── HTTP ─────────────────────────────────────────────────────────────────────────

def _api_get(endpoint: str, params: dict) -> dict:
    """GET authentifié d'un endpoint de l'API YouTube Data v3 → dict JSON.

    Lève ``YouTubeQuotaError`` sur dépassement de quota (403), ``YouTubeError`` sinon.
    """
    global _last_req_ts
    wait = _MIN_INTERVAL - (time.time() - _last_req_ts)
    if wait > 0:
        time.sleep(wait)
    url = f"{_API_BASE}/{endpoint}?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8")
        _last_req_ts = time.time()
        return json.loads(body)
    except urllib.error.HTTPError as exc:
        _last_req_ts = time.time()
        detail = ""
        try:
            detail = exc.read().decode("utf-8")
        except Exception:
            pass
        if exc.code == 403 and "quota" in detail.lower():
            raise YouTubeQuotaError(f"Quota YouTube dépassé (HTTP 403)") from exc
        raise YouTubeError(f"HTTP {exc.code} sur {endpoint}: {detail[:200]}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise YouTubeError(f"Réseau indisponible sur {endpoint}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise YouTubeError(f"Réponse non-JSON sur {endpoint}: {exc}") from exc


# ── Parsing (testable hors réseau avec des réponses mockées) ──────────────────────

def parse_search(data: dict) -> tuple[int, list[str]]:
    """Extrait (video_count, [video_ids]) d'une réponse ``search.list``.

    ``video_count`` = ``pageInfo.totalResults`` (estimation du volume de vidéos pour
    le mot-clé). Les IDs sont ceux des items de type vidéo, pour un éventuel
    ``videos.list`` d'agrégation des vues.
    """
    page_info = data.get("pageInfo") or {}
    total = int(page_info.get("totalResults", 0) or 0)
    ids: list[str] = []
    for item in data.get("items", []) or []:
        vid = (item.get("id") or {}).get("videoId")
        if vid:
            ids.append(vid)
    return total, ids


def parse_videos_stats(data: dict) -> int:
    """Somme des ``statistics.viewCount`` d'une réponse ``videos.list`` → view_count total."""
    total = 0
    for item in data.get("items", []) or []:
        stats = item.get("statistics") or {}
        vc = stats.get("viewCount")
        if vc is not None:
            try:
                total += int(vc)
            except (TypeError, ValueError):
                continue
    return total


# ── Collecte ─────────────────────────────────────────────────────────────────────

def fetch_youtube(keyword: str, with_views: bool = True) -> dict:
    """Récupère le signal YouTube d'un mot-clé : ``{keyword, video_count, view_count}``.

    Args:
        keyword:    mot-clé produit (q de search.list).
        with_views: si True, fait l'appel ``videos.list`` (1 unité) pour agréger les vues.
                    Si False, n'utilise que ``search.list`` (économise 1 unité, ``view_count``=None).

    Returns:
        dict ``{"keyword", "video_count", "view_count"}``. ``view_count`` peut être None
        si ``with_views=False`` ou si aucune vidéo n'est retournée.

    Raises:
        YouTubeError / YouTubeQuotaError. La clé absente lève ``YouTubeError`` AVANT
        tout réseau (échec propre).
    """
    cached = _cache_get(keyword)
    if cached is not None:
        return cached

    key = get_api_key()
    if not key:
        raise YouTubeError(
            "YOUTUBE_API_KEY absente — définis-la dans l'environnement ou ~/discord/.env "
            "(format: YOUTUBE_API_KEY=AIza...). Aucun appel réseau effectué."
        )

    search = _api_get("search", {
        "key": key, "part": "snippet", "type": "video",
        "q": keyword, "maxResults": _SEARCH_MAX_RESULTS,
    })
    video_count, ids = parse_search(search)

    view_count: int | None = None
    if with_views and ids:
        videos = _api_get("videos", {
            "key": key, "part": "statistics", "id": ",".join(ids),
        })
        view_count = parse_videos_stats(videos)

    result = {"keyword": keyword, "video_count": video_count, "view_count": view_count}
    _cache_put(keyword, result)
    return result


def youtube_raw_signal(keyword: str, **kwargs):
    """Construit un ``RawSignal('youtube', ...)`` ponctuel (1 point) pour un mot-clé.

    Le scoring exige ≥2 points pour une vélocité : ce signal ponctuel devient utile
    une fois empilé dans ``youtube_snapshots`` par le worker (la série se reconstruit
    via ``signals.db_signals``). Série vide si la collecte échoue.
    """
    from signals.features import RawSignal
    try:
        data = fetch_youtube(keyword, **kwargs)
    except YouTubeError as exc:
        logger.warning("YouTube indisponible pour « %s » : %s", keyword, exc)
        return RawSignal("youtube", [], [])
    val = data.get("view_count")
    if val is None:
        val = data.get("video_count") or 0
    return RawSignal("youtube", [0.0], [float(val)])


if __name__ == "__main__":  # test : python3 -m collectors.youtube_trending "robot vacuum"
    import sys
    logging.basicConfig(level=logging.INFO)
    kw = " ".join(sys.argv[1:]) or "robot vacuum"
    if not has_api_key():
        print("✗ YOUTUBE_API_KEY absente (env ou ~/discord/.env). Collecteur inactif.")
        sys.exit(1)
    try:
        data = fetch_youtube(kw)
    except YouTubeError as exc:
        print(f"✗ {exc}")
        sys.exit(1)
    print(f"Mot-clé     : {kw}")
    print(f"video_count : {data['video_count']:,}")
    print(f"view_count  : {data['view_count']:,}" if data['view_count'] is not None else "view_count  : (non agrégé)")
