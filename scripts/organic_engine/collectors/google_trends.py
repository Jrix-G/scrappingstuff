"""Collecteur Google Trends — scraping HTTP direct, sans pytrends, sans API payante.

Stratégie :
  1. Obtenir un cookie NID valide en visitant google.com avec curl_cffi (TLS Chrome).
  2. Appeler l'endpoint explore pour récupérer le token TIMESERIES.
  3. Appeler widgetdata/multiline pour la série temporelle 0-100.

Pourquoi pas pytrends : archivé en avril 2025, 429 après ~20 requêtes.
Pourquoi curl_cffi : impersonne le TLS de Chrome (JA3/H2 frame order) — Google
ne voit pas Python/requests. Taux de succès attendu >85% depuis une IP résidentielle.

Cache disque TTL 3 jours. Dégradation gracieuse : série vide si les deux backends échouent.
"""

from __future__ import annotations

import hashlib
import json
import random
import time
from pathlib import Path
from urllib.parse import quote

try:
    from curl_cffi import requests as cffi_requests
    _HAS_CURL_CFFI = True
except ImportError:
    _HAS_CURL_CFFI = False

_CACHE_DIR       = Path(__file__).resolve().parent.parent / ".trends_cache"
_CACHE_TTL       = 3 * 24 * 3600   # 3 j — renouvelle plus souvent que 7j (produits viraux)
_COOKIE_REFRESH  = 48 * 3600       # 48 h entre renouvellements du cookie NID
_BASE            = "https://trends.google.com/trends/api"
_HEADERS         = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-US,en;q=0.9",
    "referer": "https://trends.google.com/",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}


class TrendsError(Exception):
    pass


# ── Cache ──────────────────────────────────────────────────────────────────────

def _cache_path(key: str) -> Path:
    return _CACHE_DIR / f"{hashlib.sha256(key.encode()).hexdigest()[:20]}.json"


def _cache_get(key: str):
    p = _cache_path(key)
    if not p.exists():
        return None
    try:
        if time.time() - p.stat().st_mtime > _CACHE_TTL:
            return None
        d = json.loads(p.read_text())
        return d["ts"], d["vals"], d["meta"]
    except Exception:
        return None


def _cache_put(key: str, ts: list, vals: list, meta: dict) -> None:
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _cache_path(key).write_text(json.dumps({"ts": ts, "vals": vals, "meta": meta}))
    except Exception:
        pass


# ── Scraper principal ─────────────────────────────────────────────────────────

class _GoogleTrendsScraper:
    """Session curl_cffi persistante pour Google Trends."""

    def __init__(self):
        self._session = None
        self._cookie_ts: float = 0.0

    def _get_session(self) -> "cffi_requests.Session":
        if self._session is None:
            self._session = cffi_requests.Session(impersonate="chrome131")
            self._session.headers.update(_HEADERS)
        return self._session

    def _refresh_cookies(self) -> None:
        """Visite google.com pour obtenir un cookie NID valide (sans login)."""
        if time.time() - self._cookie_ts < _COOKIE_REFRESH:
            return
        try:
            s = self._get_session()
            s.get("https://www.google.com", timeout=15)
            self._cookie_ts = time.time()
            time.sleep(random.uniform(1.5, 3.0))
        except Exception:
            pass  # best-effort — on tente quand même l'appel Trends

    def _get(self, url: str, retries: int = 5) -> dict:
        s = self._get_session()
        last_exc: Exception | None = None
        for attempt in range(retries):
            try:
                resp = s.get(url, timeout=25)
                if resp.status_code == 429:
                    wait = (2 ** attempt) * 10 + random.uniform(0, 5)
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                text = resp.text
                if text.startswith(")]}'"):
                    text = text[5:]   # strip anti-hijacking prefix
                return json.loads(text)
            except Exception as exc:
                last_exc = exc
                time.sleep((2 ** attempt) * 5 + random.uniform(0, 2))
        raise TrendsError(f"Google Trends HTTP échoué : {last_exc}")

    def _get_token(self, keyword: str, timeframe: str, geo: str) -> tuple[str, dict]:
        req_obj = {
            "comparisonItem": [{"keyword": keyword, "geo": geo, "time": timeframe}],
            "category": 0,
            "property": "",
        }
        url = f"{_BASE}/explore?hl=en-US&tz=0&req={quote(json.dumps(req_obj, separators=(',', ':')))}"
        data = self._get(url)
        for w in data.get("widgets", []):
            if w.get("id") == "TIMESERIES":
                return w["token"], w["request"]
        raise TrendsError("Widget TIMESERIES introuvable dans la réponse explore")

    def _get_series(self, token: str, req: dict) -> list[float]:
        url = (
            f"{_BASE}/widgetdata/multiline"
            f"?hl=en-US&tz=0"
            f"&req={quote(json.dumps(req, separators=(',', ':')))}"
            f"&token={token}"
        )
        data = self._get(url)
        rows = data.get("default", {}).get("timelineData", [])
        return [float(r["value"][0]) for r in rows if r.get("value")]

    def fetch(self, keyword: str, timeframe: str = "today 3-m", geo: str = "") -> tuple[list[float], list[float], dict]:
        """Retourne (timestamps_days, values_0_100, meta)."""
        self._refresh_cookies()
        time.sleep(random.uniform(3.0, 7.0))   # délai humain avant chaque appel

        token, req = self._get_token(keyword, timeframe, geo)
        time.sleep(random.uniform(2.0, 4.0))
        values = self._get_series(token, req)

        if not values:
            return [], [], {"keyword": keyword, "points": 0, "backend": "direct"}

        timestamps = [float(i * 7) for i in range(len(values))]  # points hebdo (~7j chacun)
        meta = {
            "keyword": keyword, "points": len(values),
            "timeframe": timeframe, "geo": geo or "WW", "backend": "direct",
        }
        return timestamps, values, meta


# Singleton de session (réutilisée entre appels pour conserver les cookies)
_scraper = _GoogleTrendsScraper()


# ── API publique (identique à l'ancienne interface pytrends) ──────────────────

def fetch_interest(
    keyword: str,
    timeframe: str = "today 3-m",
    geo: str = "",
    retries: int = 3,
) -> tuple[list[float], list[float], dict]:
    """Récupère la série d'intérêt Google Trends.

    Retourne (timestamps_days, values, meta). Série vide si échec.
    Interface identique à l'ancienne version pytrends.
    """
    if not _HAS_CURL_CFFI:
        raise TrendsError("curl_cffi non installé. → pip install curl_cffi")

    cache_key = f"{keyword}|{timeframe}|{geo}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            result = _scraper.fetch(keyword, timeframe, geo)
            _cache_put(cache_key, *result)
            return result
        except TrendsError as exc:
            last_exc = exc
            time.sleep(2 ** attempt * 8.0)

    raise TrendsError(f"Google Trends indisponible après {retries} essais : {last_exc}")


def trends_raw_signal(keyword: str, **kwargs):
    """Construit un RawSignal('google_trends', ...) — série vide si indisponible."""
    from signals.features import RawSignal
    try:
        ts, vals, _meta = fetch_interest(keyword, **kwargs)
    except TrendsError:
        ts, vals = [], []
    return RawSignal("google_trends", ts, vals)


# ── 2026-06-21 : bascule no-VPN ──────────────────────────────────────────────
# L'endpoint widgetdata ci-dessus se fait rate-limiter depuis l'IP maison (VPN
# abandonné). Le signal est désormais délégué au collecteur autocomplete
# (suggest_trends : Google Suggest + repli Bing, snapshots quotidiens → features
# `direction` + `saturation`). Les noms publics (fetch_interest / trends_raw_signal)
# restent identiques → aucun call site à modifier. Le code widgetdata reste
# au-dessus comme repli manuel.
from collectors.suggest_trends import (  # noqa: E402
    fetch_interest as fetch_interest,
    trends_raw_signal as trends_raw_signal,
)


if __name__ == "__main__":
    import sys
    kw = sys.argv[1] if len(sys.argv) > 1 else "portable blender"
    try:
        ts, vals, meta = fetch_interest(kw)
        print(f"Mot-clé : {kw}  | {meta['points']} points | backend={meta.get('backend')}")
        if vals:
            print(f"Intérêt récent : {vals[-5:]}  (max {max(vals):.0f})")
    except TrendsError as exc:
        print(f"✗ {exc}")
