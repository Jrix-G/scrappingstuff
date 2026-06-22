"""Signal de tendance gratuit, no-VPN, depuis l'IP maison — via autocomplete.

Remplaçant de `google_trends.py` (widgetdata mort sous volume depuis IP résidentielle).
Source principale : Google Suggest client=chrome → renvoie des scores numériques
(`google:suggestrelevance` / `verbatimrelevance`). Plan B : Bing osjson.

Comme l'autocomplete n'a PAS de série temporelle native, on en fabrique une en
accumulant un snapshot par jour dans `.trends_cache/`. La série retournée est donc
historique-maison : elle se remplit avec le temps (1 point/jour). La DÉRIVÉE de
cette série = montée/déclin ; la composition des suggestions = saturation.

Interface identique à google_trends.fetch_interest : (timestamps_days, values, meta).
Budget réseau : 1 requête/mot-clé/jour grâce au cache snapshot.
"""

from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

_CACHE_DIR = Path(__file__).resolve().parent.parent / ".trends_cache"
_SNAP_TTL = 20 * 3600          # 1 snapshot / ~jour max (évite de re-taper l'endpoint)
_TIMEOUT = 15
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

# Marqueurs de saturation commerciale dans les suggestions.
_BRANDS = ("ninja", "xiaomi", "nutribullet", "blendjet", "philips", "tefal",
           "moulinex", "beast", "cuisinart", "magic bullet")
_RETAILERS = ("amazon", "walmart", "carrefour", "kmart", "target", "ebay",
              "aliexpress", "temu", "costco")


class SuggestError(Exception):
    pass


def _http_json(url: str) -> object:
    req = urllib.request.Request(url, headers={
        "User-Agent": _UA,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
    })
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
        if r.status != 200:
            raise SuggestError(f"HTTP {r.status}")
        body = r.read().decode("utf-8", "replace")
    # Détection blocage/captcha sommaire.
    low = body[:400].lower()
    if "captcha" in low or "unusual traffic" in low or body.strip().startswith("<"):
        raise SuggestError("blocage/captcha détecté")
    return json.loads(body)


# ── Sources autocomplete ────────────────────────────────────────────────────────

def _google_suggest(keyword: str) -> tuple[list[str], float]:
    """Retourne (suggestions, verbatim_relevance). client=chrome → scores numériques."""
    url = ("https://www.google.com/complete/search?client=chrome&q="
           + urllib.parse.quote(keyword))
    data = _http_json(url)
    suggestions = data[1] if len(data) > 1 else []
    verbatim = 0.0
    if len(data) > 4 and isinstance(data[4], dict):
        verbatim = float(data[4].get("google:verbatimrelevance", 0) or 0)
    return list(suggestions), verbatim


def _bing_suggest(keyword: str) -> tuple[list[str], float]:
    """Plan B : pas de scores → proxy = nombre de suggestions."""
    url = ("https://api.bing.com/osjson.aspx?market=en-US&query="
           + urllib.parse.quote(keyword))
    data = _http_json(url)
    suggestions = data[1] if len(data) > 1 else []
    return list(suggestions), float(len(suggestions))


# ── Features de saturation / direction ──────────────────────────────────────────

def _saturation_index(suggestions: list[str]) -> float:
    """Part de suggestions citant une marque ou un retailer (0..1). Haut = saturé."""
    if not suggestions:
        return 0.0
    hits = 0
    for s in suggestions:
        sl = s.lower()
        if any(b in sl for b in _BRANDS) or any(r in sl for r in _RETAILERS):
            hits += 1
    return round(hits / len(suggestions), 3)


def _normalize_score(verbatim: float, n_suggestions: int) -> float:
    """Score 0..100 façon Trends. verbatim Google ~1300 = plafond observé."""
    if verbatim > 0:
        return round(min(100.0, verbatim / 13.0), 1)   # 1300 -> 100
    return round(min(100.0, n_suggestions * 6.5), 1)    # fallback Bing : ~16 sugg -> 100


# ── Snapshot / série temporelle maison ──────────────────────────────────────────

def _snap_path(keyword: str) -> Path:
    safe = re.sub(r"[^a-z0-9]+", "_", keyword.lower()).strip("_")[:60]
    return _CACHE_DIR / f"suggest_{safe}.json"


def _load_snaps(keyword: str) -> list[dict]:
    p = _snap_path(keyword)
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text())
    except Exception:
        return []


def _append_snap(keyword: str, snap: dict, history: list[dict]) -> list[dict]:
    history = history + [snap]
    history = history[-180:]   # garde ~6 mois de points journaliers
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _snap_path(keyword).write_text(json.dumps(history))
    except Exception:
        pass
    return history


def _take_snapshot(keyword: str) -> dict:
    """Un appel réseau (Google, sinon Bing). Lève SuggestError si tout échoue."""
    backend, suggestions, verbatim = "google", [], 0.0
    try:
        suggestions, verbatim = _google_suggest(keyword)
    except Exception:
        time.sleep(1.0)
        suggestions, _n = _bing_suggest(keyword)   # peut lever -> propagé
        backend, verbatim = "bing", 0.0
    return {
        "t": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "score": _normalize_score(verbatim, len(suggestions)),
        "saturation": _saturation_index(suggestions),
        "n": len(suggestions),
        "suggestions": suggestions,
        "backend": backend,
    }


# ── API publique (drop-in pour google_trends) ────────────────────────────────────

def fetch_interest(keyword: str, timeframe: str = "", geo: str = "",
                   retries: int = 2) -> tuple[list[float], list[float], dict]:
    """Retourne (timestamps_days, values, meta).

    Ajoute au plus 1 snapshot/jour (cache TTL). values = score 0..100 par jour.
    Dégradation gracieuse : série existante renvoyée si le réseau échoue.
    """
    history = _load_snaps(keyword)
    fresh = bool(history) and (
        time.time() - _snap_path(keyword).stat().st_mtime < _SNAP_TTL)

    if not fresh:
        for attempt in range(retries):
            try:
                snap = _take_snapshot(keyword)
                history = _append_snap(keyword, snap, history)
                break
            except SuggestError:
                if attempt + 1 < retries:
                    time.sleep(2 ** attempt * 3.0)
            except Exception:
                break   # offline -> on sert l'historique tel quel

    values = [h["score"] for h in history]
    timestamps = [float(i) for i in range(len(values))]   # 1 point = 1 jour
    last = history[-1] if history else {}
    meta = {
        "keyword": keyword,
        "points": len(values),
        "backend": last.get("backend", "none"),
        "saturation": last.get("saturation"),     # 0..1, proxy "piège à fric"
        "direction": _direction(values),          # 'up'/'down'/'flat'/'unknown'
        "latest_suggestions": last.get("suggestions", [])[:6],
    }
    return timestamps, values, meta


def _direction(values: list[float], window: int = 7) -> str:
    """Dérivée approx : moyenne récente vs précédente."""
    if len(values) < 4:
        return "unknown"
    w = min(window, len(values) // 2)
    recent = sum(values[-w:]) / w
    prior = sum(values[-2 * w:-w]) / w
    if prior == 0:
        return "unknown"
    delta = (recent - prior) / prior
    if delta > 0.10:
        return "up"
    if delta < -0.10:
        return "down"
    return "flat"


def trends_raw_signal(keyword: str, **kwargs):
    """RawSignal('google_trends', ...) — compatible scoring existant."""
    from signals.features import RawSignal
    try:
        ts, vals, _meta = fetch_interest(keyword, **kwargs)
    except Exception:
        ts, vals = [], []
    return RawSignal("google_trends", ts, vals)


if __name__ == "__main__":
    import sys
    kw = sys.argv[1] if len(sys.argv) > 1 else "portable blender"
    ts, vals, meta = fetch_interest(kw)
    print(f"{kw} | {meta['points']} snapshot(s) | backend={meta['backend']}")
    print(f"  score actuel : {vals[-1] if vals else 'n/a'} | "
          f"direction={meta['direction']} | saturation={meta['saturation']}")
    print(f"  suggestions  : {meta['latest_suggestions']}")
