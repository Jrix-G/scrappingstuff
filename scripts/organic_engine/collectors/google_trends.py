"""Collecteur Google Trends — vélocité de la demande de recherche.

Google Trends renvoie une série temporelle (intérêt relatif 0–100) sur plusieurs mois
EN UN SEUL APPEL : la vélocité et l'accélération sont donc calculables immédiatement,
sans attendre l'historique de snapshots. Sortie : un :class:`RawSignal` ``"google_trends"``.

Dépendance : ``pytrends`` (``pip install pytrends``). L'API non officielle renvoie des
HTTP 429 dès qu'on tape trop vite depuis une même IP. Deux garde-fous ici :
  • **cache disque (TTL)** : un mot-clé déjà vu n'est jamais re-tiré (dédup automatique
    entre produits qui partagent le mot-clé, et réutilisation d'un run à l'autre) ;
  • **intervalle mini entre appels réseau** : on espace les requêtes (les hits de cache
    sont instantanés et ne comptent pas), ce qui évite la rafale qui déclenche le 429.
En cas d'échec persistant, on renvoie une série vide — le moteur dégrade proprement.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

try:
    from pytrends.request import TrendReq  # type: ignore
    _HAS_PYTRENDS = True
except ImportError:
    _HAS_PYTRENDS = False

_CACHE_DIR = Path(__file__).resolve().parent.parent / ".trends_cache"
_CACHE_TTL_SECONDS = 7 * 24 * 3600     # 7 j : une courbe 3 mois ne bouge pas en une semaine
_MIN_REQUEST_INTERVAL = 10.0           # Trends est strict : ≥10 s entre deux appels réseau
_last_request_ts = 0.0


class TrendsError(Exception):
    """Erreur d'accès à Google Trends."""


def _cache_path(key: str) -> Path:
    return _CACHE_DIR / f"{hashlib.sha256(key.encode()).hexdigest()[:20]}.json"


def _cache_get(key: str):
    p = _cache_path(key)
    if not p.exists():
        return None
    try:
        if time.time() - p.stat().st_mtime > _CACHE_TTL_SECONDS:
            return None
        d = json.loads(p.read_text())
        return d["ts"], d["vals"], d["meta"]
    except Exception:
        return None


def _cache_put(key: str, ts: list[float], vals: list[float], meta: dict) -> None:
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _cache_path(key).write_text(json.dumps({"ts": ts, "vals": vals, "meta": meta}))
    except Exception:
        pass  # cache best-effort


def fetch_interest(
    keyword: str,
    timeframe: str = "today 3-m",
    geo: str = "",
    retries: int = 3,
) -> tuple[list[float], list[float], dict]:
    """Récupère la série d'intérêt Google Trends d'un mot-clé.

    Returns:
        (timestamps_days, values, meta) — ``timestamps_days`` relatifs au début de la
        fenêtre (en jours), ``values`` = intérêt relatif 0–100. Série vide si indisponible.
    """
    if not _HAS_PYTRENDS:
        raise TrendsError("pytrends non installé. → pip install pytrends")

    cache_key = f"{keyword}|{timeframe}|{geo}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    global _last_request_ts
    last_exc: Exception | None = None
    for attempt in range(retries):
        wait = _MIN_REQUEST_INTERVAL - (time.time() - _last_request_ts)
        if wait > 0:
            time.sleep(wait)
        try:
            pt = TrendReq(hl="fr-FR", tz=0, timeout=(10, 25))
            pt.build_payload([keyword], timeframe=timeframe, geo=geo)
            df = pt.interest_over_time()
            _last_request_ts = time.time()
            if df is None or df.empty or keyword not in df:
                result = ([], [], {"keyword": keyword, "points": 0})
                _cache_put(cache_key, *result)  # mot-clé sans couverture : on s'en souvient
                return result
            series = df[keyword].tolist()
            dates = df.index.tolist()
            t0 = dates[0]
            timestamps = [(d - t0).total_seconds() / 86400.0 for d in dates]
            values = [float(v) for v in series]
            meta = {"keyword": keyword, "points": len(values),
                    "timeframe": timeframe, "geo": geo or "WW"}
            result = (timestamps, values, meta)
            _cache_put(cache_key, *result)
            return result
        except Exception as exc:  # 429, réseau, parsing
            _last_request_ts = time.time()
            last_exc = exc
            time.sleep(2 ** attempt * 3.0)  # backoff 3s, 6s, 12s (les 429 n'entrent pas en cache)
    raise TrendsError(f"Google Trends indisponible après {retries} essais : {last_exc}")


def trends_raw_signal(keyword: str, **kwargs):
    """Construit un ``RawSignal('google_trends', ...)`` (série vide si indisponible)."""
    from signals.features import RawSignal
    try:
        ts, vals, _meta = fetch_interest(keyword, **kwargs)
    except TrendsError:
        ts, vals = [], []
    return RawSignal("google_trends", ts, vals)


if __name__ == "__main__":  # test : python3 -m collectors.google_trends "portable blender"
    import sys
    kw = sys.argv[1] if len(sys.argv) > 1 else "portable blender"
    try:
        ts, vals, meta = fetch_interest(kw)
        print(f"Mot-clé : {kw}  | {meta['points']} points")
        if vals:
            print(f"Intérêt récent : {vals[-5:]}  (max {max(vals):.0f})")
    except TrendsError as exc:
        print(f"✗ {exc}")
