"""Collecteur Google Trends — vélocité de la demande de recherche.

Google Trends renvoie une série temporelle (intérêt relatif 0–100) sur plusieurs mois
EN UN SEUL APPEL : la vélocité et l'accélération sont donc calculables immédiatement,
sans attendre l'historique de snapshots. Sortie : un :class:`RawSignal` ``"google_trends"``.

Dépendance : ``pytrends`` (``pip install pytrends``). ATTENTION : l'API non officielle de
Google Trends renvoie fréquemment des HTTP 429 (rate-limit) depuis les IP datacenter.
Le collecteur réessaie avec backoff puis renvoie une série vide en cas d'échec — le
moteur dégrade alors proprement (confiance abaissée) sans planter.
"""

from __future__ import annotations

import time

try:
    from pytrends.request import TrendReq  # type: ignore
    _HAS_PYTRENDS = True
except ImportError:
    _HAS_PYTRENDS = False


class TrendsError(Exception):
    """Erreur d'accès à Google Trends."""


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

    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            pt = TrendReq(hl="fr-FR", tz=0, timeout=(10, 25))
            pt.build_payload([keyword], timeframe=timeframe, geo=geo)
            df = pt.interest_over_time()
            if df is None or df.empty or keyword not in df:
                return [], [], {"keyword": keyword, "points": 0}
            series = df[keyword].tolist()
            dates = df.index.tolist()
            t0 = dates[0]
            timestamps = [(d - t0).total_seconds() / 86400.0 for d in dates]
            values = [float(v) for v in series]
            meta = {"keyword": keyword, "points": len(values),
                    "timeframe": timeframe, "geo": geo or "WW"}
            return timestamps, values, meta
        except Exception as exc:  # 429, réseau, parsing
            last_exc = exc
            time.sleep(2 ** attempt * 1.5)  # backoff 1.5s, 3s, 6s
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
