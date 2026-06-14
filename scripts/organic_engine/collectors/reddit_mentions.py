"""Collecteur Reddit — signal organique PRÉCOCE, via le flux RSS public (sans clé).

Reddit a verrouillé son API legacy (création d'app réservée à la modération) ET bloque
ses endpoints ``.json`` depuis les clients non-navigateur (HTTP 403). En revanche, le
flux **RSS de recherche** (``search.rss``) reste servi (HTTP 200) :

    https://www.reddit.com/r/gadgets+BuyItForLife/search.rss?q=...&restrict_sr=on&sort=new

On en tire un signal de mentions, intelligemment :

* **1 seule requête multi-subreddit** (syntaxe ``/r/a+b+c/``) → N produits = N requêtes,
  pas N×(nb subs). Indispensable car le RSS public est agressivement rate-limité (429).
* **Cache disque (TTL)** : une même recherche ne retape jamais Reddit.
* **Backoff sur 429/5xx** + User-Agent navigateur + intervalle mini entre requêtes.
* **Filtre de pertinence** sur le titre (anti faux-positifs des recherches larges).
* **Buckets hebdomadaires** : les mentions produit sont rares ; agréger par semaine
  donne une série assez dense pour une vélocité stable.

Le RSS ne fournit pas les upvotes/commentaires (réservés au JSON bloqué) : le signal
est donc la **fréquence de mentions dans le temps**, qui EST le signal d'émergence
précoce recherché. Sortie : :class:`RawSignal` ``"reddit"`` consommé par le moteur.

Aucune dépendance externe : urllib + xml.etree (stdlib) uniquement.
"""

from __future__ import annotations

import hashlib
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# Subreddits où les ACHETEURS découvrent/commentent des produits avant les vendeurs.
DEFAULT_SUBREDDITS = [
    "shutupandtakemymoney", "BuyItForLife", "gadgets", "ofcoursethatsathing",
    "DidntKnowIWantedThat", "INEEEEDIT", "ProductPorn", "reviews",
]

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
_ATOM = {"a": "http://www.w3.org/2005/Atom"}
_CACHE_DIR = Path(__file__).resolve().parent.parent / ".reddit_cache"
_CACHE_TTL_SECONDS = 6 * 3600          # 6 h : frais sans marteler Reddit
_MIN_REQUEST_INTERVAL = 3.0            # politesse : ≥3 s entre deux appels réseau
_BUCKET_DAYS = 7                       # agrégation hebdomadaire (mentions rares)
_last_request_ts = 0.0


class RedditError(Exception):
    """Erreur d'accès au flux RSS public Reddit."""


# --- Cache disque ----------------------------------------------------------

def _cache_path(url: str) -> Path:
    return _CACHE_DIR / f"{hashlib.sha256(url.encode()).hexdigest()[:20]}.xml"


def _cache_get(url: str) -> str | None:
    p = _cache_path(url)
    if not p.exists():
        return None
    try:
        if time.time() - p.stat().st_mtime > _CACHE_TTL_SECONDS:
            return None
        return p.read_text()
    except Exception:
        return None


def _cache_put(url: str, text: str) -> None:
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _cache_path(url).write_text(text)
    except Exception:
        pass  # cache best-effort


# --- HTTP poli avec backoff ------------------------------------------------

def _get_rss(url: str, retries: int = 3) -> str:
    """GET du flux RSS, avec cache, politesse et backoff sur 429/5xx."""
    cached = _cache_get(url)
    if cached is not None:
        return cached

    global _last_request_ts
    last_exc: Exception | None = None
    for attempt in range(retries):
        wait = _MIN_REQUEST_INTERVAL - (time.time() - _last_request_ts)
        if wait > 0:
            time.sleep(wait)
        req = urllib.request.Request(
            url, headers={"User-Agent": _UA, "Accept": "application/atom+xml,text/xml"})
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                text = resp.read().decode("utf-8")
            _last_request_ts = time.time()
            if text.strip():
                _cache_put(url, text)
                return text
        except urllib.error.HTTPError as exc:
            _last_request_ts = time.time()
            last_exc = exc
            if exc.code in (429, 500, 502, 503):
                time.sleep(2 ** attempt * 3.0)  # backoff 3s, 6s, 12s
                continue
            raise RedditError(f"HTTP {exc.code} sur le RSS Reddit") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            last_exc = exc
            time.sleep(2 ** attempt * 2.0)
    raise RedditError(f"RSS Reddit indisponible après {retries} essais : {last_exc}")


# --- Pertinence ------------------------------------------------------------

def _is_relevant(keyword: str, title: str) -> bool:
    """Vrai si tous les mots-clés (>2 lettres) apparaissent dans le titre."""
    h = title.lower()
    tokens = [t for t in keyword.lower().split() if len(t) > 2]
    return all(t in h for t in tokens) if tokens else keyword.lower() in h


def _parse_entries(xml_text: str) -> list[tuple[str, float]]:
    """Extrait (titre, timestamp_epoch) de chaque entrée Atom."""
    out: list[tuple[str, float]] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return out
    for e in root.findall(".//a:entry", _ATOM):
        title_el = e.find("a:title", _ATOM)
        date_el = e.find("a:published", _ATOM)
        if date_el is None:
            date_el = e.find("a:updated", _ATOM)
        if title_el is None or date_el is None or not date_el.text:
            continue
        try:
            dt = datetime.fromisoformat(date_el.text.replace("Z", "+00:00"))
        except ValueError:
            continue
        out.append((title_el.text or "", dt.timestamp()))
    return out


# --- Collecte ---------------------------------------------------------------

def fetch_mentions(
    keyword: str,
    subreddits: list[str] | None = None,
    days: int = 365,
) -> tuple[list[float], list[float], dict]:
    """Récupère les mentions Reddit d'un mot-clé, agrégées par semaine.

    Returns:
        (timestamps_days, values, meta) — ``values[i]`` = nb de mentions pertinentes
        de la semaine ``i`` ; ``timestamps_days`` relatifs au début de la fenêtre.
    """
    subs = subreddits or DEFAULT_SUBREDDITS
    multi = "+".join(subs)
    now_ts = datetime.now(timezone.utc).timestamp()
    horizon = now_ts - days * 86400

    params = {"q": keyword, "restrict_sr": "on", "sort": "new", "limit": "100"}
    url = f"https://www.reddit.com/r/{multi}/search.rss?" + urllib.parse.urlencode(params)
    try:
        entries = _parse_entries(_get_rss(url))
    except RedditError:
        entries = []

    per_bucket: dict[int, float] = defaultdict(float)
    seen = kept = 0
    for title, created in entries:
        seen += 1
        if created < horizon or not _is_relevant(keyword, title):
            continue
        bucket = int((created - horizon) // (_BUCKET_DAYS * 86400))
        per_bucket[bucket] += 1.0
        kept += 1

    meta = {"keyword": keyword, "subreddits": subs,
            "posts_seen": seen, "posts_kept": kept, "days": days}
    if not per_bucket:
        return [], [], meta

    buckets = sorted(per_bucket)
    timestamps = [float(b * _BUCKET_DAYS) for b in buckets]
    values = [per_bucket[b] for b in buckets]
    return timestamps, values, meta


def reddit_raw_signal(keyword: str, **kwargs):
    """Construit un ``RawSignal('reddit', ...)`` (série vide si rien/indisponible)."""
    from signals.features import RawSignal
    try:
        ts, vals, _meta = fetch_mentions(keyword, **kwargs)
    except RedditError:
        ts, vals = [], []
    return RawSignal("reddit", ts, vals)


if __name__ == "__main__":  # test : python3 -m collectors.reddit_mentions "robot vacuum"
    import sys
    kw = sys.argv[1] if len(sys.argv) > 1 else "robot vacuum"
    try:
        ts, vals, meta = fetch_mentions(kw)
    except RedditError as exc:
        print(f"✗ {exc}")
        sys.exit(1)
    print(f"Mot-clé          : {kw}")
    print(f"Subreddits       : {len(meta['subreddits'])} en 1 requête RSS multi-sub")
    print(f"Posts vus/gardés : {meta['posts_seen']} / {meta['posts_kept']} (pertinents)")
    if ts:
        print(f"Série hebdo      : {len(ts)} semaines actives, {sum(vals):.0f} mentions")
        from signals.timeseries import extract_trend
        tf = extract_trend(ts, vals)
        print(f"Vélocité {tf.velocity:+.4f} log/j | croissance/mois {tf.monthly_growth*100:+.0f}% | R² {tf.r2:.2f}")
    else:
        print("Aucune mention pertinente sur la fenêtre.")
