"""Collecteur Wayback Machine — l'HORLOGE du détecteur de pièges à fric.

Pourquoi cette source ?
-----------------------
Les autres collecteurs (eBay sold, Amazon « bought in past month », DHgate
recentlysold) ne donnent qu'une PHOTO instantanée de la demande. Or un piège à
fric, ce n'est pas « peu de demande aujourd'hui » — c'est « la demande s'EFFONDRE »
(la hype est passée, tu arrives trop tard). Pour détecter un DÉCLIN il faut un
HISTORIQUE, et nous n'avons pas d'archive maison qui remonte assez loin.

archive.org (la Wayback Machine) a, lui, archivé pendant des années les pages de
recherche eBay/Amazon/DHgate. On reconstruit donc rétroactivement la série
temporelle du « sold count » d'un mot-clé en :

  1. listant les snapshots archivés d'une URL de recherche via l'API CDX ;
  2. téléchargeant le HTML archivé brut de ~6-12 snapshots étalés dans le temps ;
  3. parsant le sold count dans chaque snapshot avec les MÊMES regex que les
     collecteurs live (réutilisées ci-dessous) ;
  4. construisant (timestamps_days, values) et en dérivant un score de déclin via
     ``signals.timeseries.extract_trend`` (vélocité < 0 = déclin ; accélération
     < 0 = la chute s'aggrave).

IP de prod : ZÉRO risque. On ne tape JAMAIS eBay/Amazon/DHgate ici — uniquement
web.archive.org, qui sert des copies cachées et tolère un volume raisonnable.

DÉGRADATION GRACIEUSE (crucial)
-------------------------------
Ce module NE LÈVE JAMAIS. Si pas d'archives, parsing impossible, réseau KO →
série vide + ``decline_score`` absent. ABSENCE = « inconnu », JAMAIS « zéro
demande / produit mort » : un produit non archivé n'est pas un produit en déclin.
C'est pour ça que ``meta["points"] < 3`` doit être traité comme « pas d'opinion »
par l'intégrateur (cf. note en bas de fichier).

COUVERTURE HONNÊTE
------------------
Wayback archive bien les pages POPULAIRES (best-sellers, mots-clés génériques
souvent visités : « stanley cup », « fidget spinner », « yoga mat »…). La longue
traîne (niche, requêtes rares) est peu ou pas archivée → série vide → inconnu.
Ce collecteur est donc un signal OPPORTUNISTE : quand l'historique existe il est
en or (déclin chiffré, gratuit, sans risque IP) ; quand il manque on s'abstient.

Aucune dépendance externe : urllib + gzip + json + re (stdlib) uniquement.
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
import zlib
from pathlib import Path

# On réutilise extract_trend (vélocité/accélération/r2) — cf. signals/timeseries.py.
try:  # import paquet (usage normal : python3 -m collectors.wayback_decline)
    from signals.timeseries import extract_trend
except ImportError:  # exécution directe du fichier
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from signals.timeseries import extract_trend


_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

_CACHE_DIR = Path(__file__).resolve().parent.parent / ".wayback_cache"
_CACHE_TTL_SECONDS = 7 * 24 * 3600       # 7 j : l'historique archivé bouge lentement

# Politesse envers archive.org : un plancher entre requêtes (le module fait peu
# de hits, mais on reste un bon citoyen — CDX puis quelques snapshots).
_MIN_REQUEST_INTERVAL = 1.5
_last_request_ts = 0.0

# Combien de snapshots on télécharge au maximum (étalés dans le temps).
_MAX_SNAPSHOTS = 10

_CDX_URL = (
    "http://web.archive.org/cdx/search/cdx?url={url}"
    "&output=json&fl=timestamp,statuscode,digest"
    "&collapse=digest&filter=statuscode:200"
)
# Snapshot HTML brut SANS la barre Wayback (suffixe id_ = original capturé).
_SNAPSHOT_URL = "http://web.archive.org/web/{ts}id_/{url}"


# ---------------------------------------------------------------------------
# Regex de sold count — RÉPLIQUÉES depuis les collecteurs live.
#
# On NE peut PAS toujours réutiliser tel quel le parsing live : un snapshot
# Wayback peut être vieux de 2 ans, avec un layout eBay/Amazon différent de
# l'actuel. On garde donc plusieurs variantes par source et on prend la première
# qui matche. Les regex « actuelles » sont reprises des modules respectifs.
# ---------------------------------------------------------------------------

# eBay — compteur « N results » (cf. collectors/ebay_sold.py::_COUNT_RE), plus
# d'anciennes variantes de layout (« 1,234 results », srp-controls__count-heading).
_EBAY_COUNT_RES = [
    re.compile(r'__count-heading>.*?<span[^>]*>([\d,]+)</span>.*?\+?\s*results?', re.S),
    re.compile(r'<span[^>]*class="[^"]*srp-controls__count[^"]*"[^>]*>'
               r'\s*<span[^>]*>([\d,]+)</span>', re.S),
    re.compile(r'([\d,]{2,})\s*\+?\s*results?\s+for', re.I),
]

# Amazon — badge « X bought in past month » (cf. collectors/amazon_demand.py::_BADGE_RE).
# C'est apparu fin 2023 ; les snapshots plus vieux n'en ont pas → fallback sur le
# nombre de résultats (« 1-48 of over 2,000 results »).
_AMAZON_BADGE_RE = re.compile(r"([\d.,]+[KkMm]?\+?)\s*bought in past month")
_AMAZON_RESULTS_RE = re.compile(r"of\s+(?:over\s+)?([\d,]+)\s+results", re.I)

# DHgate — blob Next.js + champ recentlysold (cf. collectors/dhgate_sold.py).
_DHGATE_NEXT_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S)
# Vieux layout DHgate (avant Next.js) : « 1234 Sold » / « Sold: 1234 » par carte.
_DHGATE_OLD_SOLD_RE = re.compile(r'(?:Sold[:\s]*)([\d,]+)|([\d,]+)\s*Sold', re.I)
_DIGITS_RE = re.compile(r"\d[\d\s.,]*")

_SOURCES = ("ebay", "amazon", "dhgate")


# --- Normalisation « 2K+ » → 2000 (copie de amazon_demand.normalize_bought) ---

def _normalize_bought(raw: str) -> int | None:
    v = raw.replace("+", "").replace(",", "").strip().upper()
    mult = 1
    if v.endswith("K"):
        mult, v = 1000, v[:-1]
    elif v.endswith("M"):
        mult, v = 1_000_000, v[:-1]
    try:
        return int(float(v) * mult)
    except ValueError:
        return None


def _parse_int(value) -> int | None:
    if value is None:
        return None
    m = _DIGITS_RE.search(str(value))
    if not m:
        return None
    digits = re.sub(r"[^\d]", "", m.group(0))
    return int(digits) if digits else None


# --- Construction de l'URL de recherche par source -------------------------

def search_url(keyword: str, source: str) -> str:
    """Construit l'URL de recherche « sold/demande » d'un mot-clé.

    Reproduit EXACTEMENT les URLs des collecteurs live, afin que la Wayback
    indexe la même page que celle qu'on scrape aujourd'hui :
      - ebay   : cf. collectors/ebay_sold.py   (_SEARCH, LH_Sold/LH_Complete)
      - amazon : cf. collectors/amazon_demand.py (/s?k=)
      - dhgate : cf. collectors/dhgate_sold.py  (/wholesale/search.do?searchkey=)
    """
    src = source.lower()
    if src == "ebay":
        return ("https://www.ebay.com/sch/i.html?_nkw="
                + urllib.parse.quote(keyword) + "&LH_Sold=1&LH_Complete=1")
    if src == "amazon":
        return "https://www.amazon.com/s?k=" + urllib.parse.quote_plus(keyword)
    if src == "dhgate":
        return ("https://www.dhgate.com/wholesale/search.do?searchkey="
                + urllib.parse.quote(keyword))
    raise ValueError(f"source inconnue : {source!r} (attendu : {_SOURCES})")


# --- Cache disque (best-effort, ne lève jamais) ----------------------------

def _cache_path(key: str) -> Path:
    return _CACHE_DIR / f"{hashlib.sha256(key.encode()).hexdigest()[:20]}.txt"


def _cache_get(key: str) -> str | None:
    p = _cache_path(key)
    if not p.exists():
        return None
    try:
        if time.time() - p.stat().st_mtime > _CACHE_TTL_SECONDS:
            return None
        return p.read_text()
    except Exception:
        return None


def _cache_put(key: str, text: str) -> None:
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _cache_path(key).write_text(text)
    except Exception:
        pass  # cache best-effort


# --- HTTP poli vers archive.org --------------------------------------------

def _http_get(url: str, timeout: int = 30) -> str | None:
    """GET poli vers web.archive.org. Renvoie None sur toute erreur (jamais lève)."""
    global _last_request_ts
    wait = _MIN_REQUEST_INTERVAL - (time.time() - _last_request_ts)
    if wait > 0:
        time.sleep(wait)
    req = urllib.request.Request(url, headers={
        "User-Agent": _UA,
        "Accept": "text/html,application/json,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            enc = resp.headers.get("Content-Encoding") or ""
            if "gzip" in enc:
                raw = gzip.decompress(raw)
            elif "deflate" in enc:
                try:
                    raw = zlib.decompress(raw)
                except zlib.error:
                    raw = zlib.decompress(raw, -zlib.MAX_WBITS)
            return raw.decode("utf-8", "replace")
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError,
            ConnectionError, OSError, ValueError):
        return None
    finally:
        _last_request_ts = time.time()


# --- CDX : liste + sélection des snapshots ---------------------------------

def _list_snapshots(target_url: str) -> list[str]:
    """Renvoie les timestamps (YYYYMMDDhhmmss) de tous les snapshots 200/uniques."""
    cdx = _CDX_URL.format(url=urllib.parse.quote(target_url, safe=""))
    cache_key = "cdx::" + target_url
    body = _cache_get(cache_key)
    if body is None:
        body = _http_get(cdx)
        if body is not None:
            _cache_put(cache_key, body)
    if not body:
        return []
    try:
        rows = json.loads(body)
    except ValueError:
        return []
    if not rows or len(rows) < 2:
        return []
    # rows[0] = header ["timestamp","statuscode","digest"] ; reste = données.
    timestamps = []
    for row in rows[1:]:
        if row and row[0] and row[0].isdigit():
            timestamps.append(row[0])
    return sorted(set(timestamps))


def _spread(timestamps: list[str], k: int) -> list[str]:
    """Échantillonne ≤ k snapshots ÉTALÉS uniformément dans le temps.

    On garde toujours le plus ancien et le plus récent, et on répartit le reste
    régulièrement : on veut une couverture temporelle large, pas une grappe de
    snapshots du même jour (qui fausserait la tendance)."""
    n = len(timestamps)
    if n <= k:
        return timestamps
    idx = [round(i * (n - 1) / (k - 1)) for i in range(k)]
    seen, out = set(), []
    for i in idx:
        if i not in seen:
            seen.add(i)
            out.append(timestamps[i])
    return out


# --- Parsing du sold count par source --------------------------------------

def _parse_ebay(html: str) -> int | None:
    for rx in _EBAY_COUNT_RES:
        m = rx.search(html)
        if m:
            n = _parse_int(m.group(1))
            if n:
                return n
    return None


def _parse_amazon(html: str) -> int | None:
    # Préféré : agrégat des badges « bought in past month » (vraie vélocité).
    vals = [v for v in (_normalize_bought(m.group(1))
                        for m in _AMAZON_BADGE_RE.finditer(html)) if v]
    if vals:
        return max(vals)
    # Fallback (snapshots d'avant le badge) : nb de résultats de la recherche.
    m = _AMAZON_RESULTS_RE.search(html)
    if m:
        return _parse_int(m.group(1))
    return None


def _parse_dhgate(html: str) -> int | None:
    # Layout Next.js actuel : blob JSON + recentlysold (cf. dhgate_sold.py).
    m = _DHGATE_NEXT_RE.search(html)
    if m:
        try:
            data = json.loads(m.group(1))
            prods = data["props"]["pageProps"]["data"]["totalProducts"]
            if isinstance(prods, list):
                vals = [s for s in (_parse_int(p.get("recentlysold"))
                                    for p in prods) if s]
                if vals:
                    return max(vals)
        except (ValueError, KeyError, TypeError):
            pass
    # Vieux layout (avant Next.js) : « N Sold » dans le HTML brut.
    vals = []
    for g1, g2 in _DHGATE_OLD_SOLD_RE.findall(html):
        n = _parse_int(g1 or g2)
        if n:
            vals.append(n)
    return max(vals) if vals else None


_PARSERS = {"ebay": _parse_ebay, "amazon": _parse_amazon, "dhgate": _parse_dhgate}


def _parse_sold(html: str, source: str) -> int | None:
    parser = _PARSERS.get(source.lower())
    return parser(html) if parser else None


def _ts_to_epoch_days(ts: str) -> float:
    """YYYYMMDDhhmmss → jours epoch (float). Robuste aux timestamps tronqués."""
    ts = (ts + "00000000000000")[:14]
    tm = time.strptime(ts, "%Y%m%d%H%M%S")
    return time.mktime(tm) / 86400.0


# --- Score de déclin --------------------------------------------------------

def _decline_score(velocity: float, acceleration: float, r2: float,
                   n_points: int) -> float:
    """0..1, 1 = déclin fort et fiable.

    Déclin = vélocité (pente log/jour) NÉGATIVE. On mappe la magnitude de la
    pente négative sur [0,1] (une chute de ~3 %/jour ≈ -0.03 → score plein),
    on bonifie si l'accélération est aussi négative (la chute s'aggrave), et on
    pondère par r2 et le nombre de points (peu de points / série bruitée =
    score atténué, on n'invente pas de certitude). Vélocité ≥ 0 → 0 (pas de déclin).
    """
    if n_points < 3 or velocity >= 0:
        return 0.0
    # Magnitude de la pente négative, saturée. -0.03 log/jour ≈ -60 %/mois.
    mag = min(1.0, abs(velocity) / 0.03)
    # Bonus chute qui s'aggrave (accélération négative), saturé à +30 %.
    accel_bonus = 1.0 + 0.3 * min(1.0, abs(acceleration) / 0.003) if acceleration < 0 else 1.0
    raw = min(1.0, mag * accel_bonus)
    # Pondération confiance : r2 (qualité d'ajustement) et richesse de la série.
    conf = max(0.0, min(1.0, r2)) * min(1.0, n_points / 5.0)
    return round(raw * conf, 3)


# --- API principale ---------------------------------------------------------

def fetch_sold_history(target_url: str, source: str) -> tuple[list[float], list[float], dict]:
    """Reconstruit la série historique du sold count via la Wayback Machine.

    Args:
        target_url: URL de recherche à reconstituer (cf. ``search_url``).
        source: "ebay" | "amazon" | "dhgate" (choisit le parseur de sold count).

    Returns:
        (timestamps_days, values, meta) où :
          - timestamps_days : jours relatifs depuis le 1er snapshot parsé ;
          - values          : sold count à chaque date ;
          - meta            : dict avec AU MOINS ``points``, ``velocity``,
            ``acceleration``, ``decline_score`` (0..1), ``source``.

    NE LÈVE JAMAIS. Si aucune archive exploitable → ([], [], meta avec points=0).
    ABSENCE = inconnu, pas « zéro demande » : l'intégrateur DOIT traiter
    ``points < 3`` comme « pas d'opinion » et NON comme un déclin.
    """
    src = source.lower()
    meta: dict = {
        "source": src, "target_url": target_url, "points": 0,
        "velocity": 0.0, "acceleration": 0.0, "r2": 0.0, "span_days": 0.0,
        "decline_score": 0.0, "snapshots_seen": 0, "snapshots_parsed": 0,
    }
    if src not in _SOURCES:
        meta["error"] = f"source inconnue : {source!r}"
        return [], [], meta

    timestamps = _list_snapshots(target_url)
    meta["snapshots_seen"] = len(timestamps)
    if not timestamps:
        return [], [], meta  # pas d'archive = inconnu (surtout pas déclin)

    chosen = _spread(timestamps, _MAX_SNAPSHOTS)

    points: list[tuple[float, float]] = []  # (epoch_days, value)
    for ts in chosen:
        snap_url = _SNAPSHOT_URL.format(ts=ts, url=target_url)
        cache_key = f"snap::{src}::{ts}::{target_url}"
        html = _cache_get(cache_key)
        if html is None:
            html = _http_get(snap_url)
            if html is not None:
                _cache_put(cache_key, html)
        if not html:
            continue
        sold = _parse_sold(html, src)
        if sold is None:
            continue
        try:
            points.append((_ts_to_epoch_days(ts), float(sold)))
        except (ValueError, OverflowError):
            continue

    meta["snapshots_parsed"] = len(points)
    if not points:
        return [], [], meta  # archives présentes mais rien de parsable = inconnu

    points.sort()
    t0 = points[0][0]
    timestamps_days = [round(p[0] - t0, 4) for p in points]
    values = [p[1] for p in points]

    meta["points"] = len(points)

    # ≥ 2 points → on peut sortir une tendance (vélocité). extract_trend gère
    # proprement les séries courtes (vélocité dès 2 pts, accélération dès 3).
    if len(points) >= 2:
        tr = extract_trend(timestamps_days, values)
        meta.update({
            "velocity": round(tr.velocity, 6),
            "acceleration": round(tr.acceleration, 6),
            "r2": round(tr.r2, 4),
            "span_days": round(tr.span_days, 2),
            "monthly_growth": round(tr.monthly_growth, 4),
            "decline_score": _decline_score(
                tr.velocity, tr.acceleration, tr.r2, tr.n_points),
        })

    return timestamps_days, values, meta


def fetch_keyword_history(keyword: str, source: str
                          ) -> tuple[list[float], list[float], dict]:
    """Confort : construit l'URL depuis un mot-clé puis appelle fetch_sold_history."""
    try:
        url = search_url(keyword, source)
    except ValueError as exc:
        return [], [], {"source": source, "points": 0, "velocity": 0.0,
                        "acceleration": 0.0, "decline_score": 0.0, "error": str(exc)}
    ts, vals, meta = fetch_sold_history(url, source)
    meta["keyword"] = keyword
    return ts, vals, meta


if __name__ == "__main__":  # python3 -m collectors.wayback_decline "fidget spinner" [source]
    import sys
    kw = sys.argv[1] if len(sys.argv) > 1 else "fidget spinner"
    source = sys.argv[2] if len(sys.argv) > 2 else "ebay"
    print(f"Mot-clé : {kw!r}  |  source : {source}")
    ts_days, values, meta = fetch_keyword_history(kw, source)
    print(f"URL reconstituée : {search_url(kw, source)}")
    print(f"Snapshots vus / parsés : {meta['snapshots_seen']} / "
          f"{meta['snapshots_parsed']}")
    if meta["points"] < 2:
        print("→ Pas assez d'historique archivé : INCONNU "
              "(surtout PAS « déclin » — un produit non archivé n'est pas mort).")
    else:
        print(f"Points reconstitués : {meta['points']}  "
              f"(sur {meta['span_days']} jours)")
        for d, v in zip(ts_days, values):
            print(f"  jour +{d:>7.1f} : sold = {v:,.0f}")
        print(f"Vélocité (log/jour) : {meta['velocity']:+.5f} "
              f"({meta.get('monthly_growth', 0)*100:+.0f} %/mois)")
        print(f"Accélération        : {meta['acceleration']:+.6f}")
        print(f"R²                  : {meta['r2']}")
        print(f"DECLINE SCORE       : {meta['decline_score']}  (0=stable/croît, 1=déclin fort)")
        if meta["decline_score"] >= 0.5:
            print("  ⛔ DÉCLIN MARQUÉ : la hype est passée, piège probable.")
        elif meta["velocity"] < 0:
            print("  ⚠️  léger déclin.")
        else:
            print("  ✅ stable ou en croissance sur la fenêtre archivée.")
