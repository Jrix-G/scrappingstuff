"""Collecteur DHgate — signal de VENTES réelles, en best-effort.

DHgate (place de marché B2B chinoise, sœur d'AliExpress) sert ses pages de
recherche via Next.js : le HTML embarque un blob JSON ``<script id="__NEXT_DATA__">``
où ``props.pageProps.data.totalProducts[]`` liste les ~40-50 produits de la
première page. Chaque produit porte ``recentlysold`` = son compteur « recently
sold » (ventes récentes affichées sur la fiche) et ``reviewCount`` = son nombre
d'avis. C'est un signal de demande directement comparable à AliExpress
(« unités réellement vendues » par type de produit), mais sur une IP maison
mono-adresse DHgate est BEAUCOUP plus permissif qu'AliExpress.

DÉTAIL CRITIQUE DÉCOUVERT EN LIVE : ``/wholesale/search.do`` répond **403** si
on l'attaque sans cookie de session. Il faut d'abord GET la **home page**
``https://www.dhgate.com/`` (qui pose les cookies anti-bot), PUIS taper la
recherche avec le même cookie jar. Sans ce « warm-up », tout est 403 ; pire,
matraquer search.do en 403 répétés déclenche un cooldown IP temporaire (~qq min)
même sur la home page. On respecte donc DHgate :

* **warm-up cookies une fois** par process, réutilisé sur toutes les recherches ;
* **cache disque 24 h** : une même recherche ne retape jamais DHgate dans la journée ;
* **intervalle mini de politesse** entre requêtes ;
* **détection de blocage** (403 / page trop courte / pas de __NEXT_DATA__) →
  on renvoie ``blocked=True`` sans matraquer ;
* **dégradation gracieuse** : ``fetch_demand`` ne lève JAMAIS. ``blocked=True``
  veut dire « donnée indisponible », PAS « zéro vente » (le scoring doit l'ignorer).

Le contrat de sortie est calqué sur ``collectors.aliexpress_orders`` afin de se
brancher tel quel dans ``demand_queue.record_aliexpress`` → table canonique
``sales_snapshots(keyword, observed_at, max_sold, median_sold, listings)``.

Aucune dépendance externe : urllib + gzip + json + re (stdlib) uniquement.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

from utils import http  # transport partagé curl_cffi chrome131 (→ urllib de repli)

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
_HOME_URL = "https://www.dhgate.com/"
_SEARCH_URL = "https://www.dhgate.com/wholesale/search.do?searchkey="
_CACHE_DIR = Path(__file__).resolve().parent.parent / ".dhgate_cache"
_CACHE_TTL_SECONDS = 24 * 3600          # 24 h : une recherche/jour suffit
_MIN_REQUEST_INTERVAL = 3.0             # politesse entre requêtes DHgate
_last_request_ts = 0.0

# Session partagée : porte le cookie jar de session (posé par la home page).
# curl_cffi (via utils.http) persiste les cookies entre le warm-up et les recherches.
_SESSION: "http.Session | None" = None
_WARMED = False

# Marqueurs de page anti-bot / blocage DHgate (PerimeterX & co).
_BLOCK_MARKERS = ("px-captcha", "Access Denied", "/akam/", "Request unsuccessful")
# Le blob Next.js qui contient la liste produits + compteurs de ventes.
_NEXT_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S
)
_DIGITS_RE = re.compile(r"\d[\d\s.,]*")


class DHgateBlocked(Exception):
    """L'IP a reçu un 403 / une page anti-bot : donnée momentanément indisponible."""


@dataclass(slots=True)
class DHgateDemand:
    """Photo des ventes DHgate pour un mot-clé (ou blocage signalé)."""

    keyword: str
    max_sold: int | None = None          # plus gros « recently sold » vu = plafond
    median_sold: int | None = None
    listings_with_sales: int = 0
    blocked: bool = False                # True = donnée indisponible (≠ zéro demande)

    def as_dict(self) -> dict:
        return {
            "keyword": self.keyword,
            "maxSold": self.max_sold,
            "medianSold": self.median_sold,
            "listingsWithSales": self.listings_with_sales,
            "blocked": self.blocked,
        }


# --- Cache disque ----------------------------------------------------------

def _cache_path(kw: str) -> Path:
    return _CACHE_DIR / f"{hashlib.sha256(kw.encode()).hexdigest()[:20]}.html"


def _cache_get(kw: str) -> str | None:
    p = _cache_path(kw)
    if not p.exists():
        return None
    try:
        if time.time() - p.stat().st_mtime > _CACHE_TTL_SECONDS:
            return None
        return p.read_text()
    except Exception:
        return None


def _cache_put(kw: str, text: str) -> None:
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _cache_path(kw).write_text(text)
    except Exception:
        pass  # cache best-effort


# --- Récupération HTML (cookies + politesse) -------------------------------

def _session() -> "http.Session":
    """Session partagée (cookie jar persistant) : la home warm-up pose les cookies
    anti-bot, réutilisés par search.do dans le MÊME process."""
    global _SESSION
    if _SESSION is None:
        _SESSION = http.Session()
    return _SESSION


def _http_get(url: str) -> str:
    """GET poli (intervalle mini) avec le cookie jar partagé. Lève si bloqué."""
    global _last_request_ts
    wait = _MIN_REQUEST_INTERVAL - (time.time() - _last_request_ts)
    if wait > 0:
        time.sleep(wait)
    try:
        res = _session().get_text(url, headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
        }, timeout=25)
    finally:
        _last_request_ts = time.time()
    # 403 = anti-bot DHgate (IP pas/plus « warmée ») ; 0 = échec transport ; 429/503 idem.
    if res.status == 403 or res.status == 0 or res.status in (429, 503):
        raise DHgateBlocked(f"HTTP {res.status} sur {url}")
    body = res.text
    if any(m in body for m in _BLOCK_MARKERS) or len(body) < 20000:
        raise DHgateBlocked("Page anti-bot DHgate (IP en cooldown).")
    return body


def _warm() -> None:
    """Pose les cookies de session via la home page (obligatoire avant search.do).

    Sans ce warm-up, ``search.do`` répond systématiquement 403. On ne le fait
    qu'une fois par process ; si DHgate refuse déjà la home, l'IP est en cooldown
    et on laisse remonter ``DHgateBlocked``.
    """
    global _WARMED
    if _WARMED:
        return
    _http_get(_HOME_URL)   # lève DHgateBlocked si l'IP est punie
    _WARMED = True


def _fetch_search_html(keyword: str) -> str:
    """Warm-up cookies puis GET de la page de recherche DHgate."""
    _warm()
    return _http_get(_SEARCH_URL + urllib.parse.quote(keyword))


# --- Parsing des compteurs de ventes ---------------------------------------

def _parse_int(value) -> int | None:
    """« 1,234 » / « 45 » → 1234 / 45. None si pas de chiffre."""
    if value is None:
        return None
    m = _DIGITS_RE.search(str(value))
    if not m:
        return None
    digits = re.sub(r"[^\d]", "", m.group(0))
    return int(digits) if digits else None


def _extract_products(body: str) -> list[dict]:
    """Renvoie ``totalProducts`` depuis le blob Next.js, [] si absent."""
    m = _NEXT_RE.search(body)
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
        prods = data["props"]["pageProps"]["data"]["totalProducts"]
        return prods if isinstance(prods, list) else []
    except (ValueError, KeyError, TypeError):
        return []


def fetch_demand(keyword: str) -> DHgateDemand:
    """Renvoie les ventes DHgate agrégées d'un mot-clé (best-effort).

    - Sert le cache 24 h si disponible.
    - Sinon warm-up cookies + UNE requête de recherche ; si l'IP est bloquée
      (403/anti-bot), renvoie ``blocked=True`` sans réessayer.
    """
    cached = _cache_get(keyword)
    if cached is not None:
        body = cached
    else:
        try:
            body = _fetch_search_html(keyword)
        except DHgateBlocked:
            return DHgateDemand(keyword=keyword, blocked=True)
        except Exception:
            # Le transport (utils.http) ne lève pas ; tout imprévu = indisponible.
            return DHgateDemand(keyword=keyword, blocked=True)
        _cache_put(keyword, body)

    products = _extract_products(body)
    if not products:
        # Page servie mais pas de blob produits exploitable : on traite comme
        # indisponible (probable variante anti-bot), pas comme « zéro vente ».
        return DHgateDemand(keyword=keyword, blocked=True)

    sold_values = [s for s in (_parse_int(p.get("recentlysold")) for p in products) if s]
    if not sold_values:
        # Page produits lisible mais aucun compteur : vraie absence de ventes
        # récentes affichées sur cette recherche (≠ blocage).
        return DHgateDemand(keyword=keyword, blocked=False)
    sold_values.sort()
    mid = sold_values[len(sold_values) // 2]
    return DHgateDemand(
        keyword=keyword,
        max_sold=max(sold_values),
        median_sold=mid,
        listings_with_sales=len(sold_values),
        blocked=False,
    )


if __name__ == "__main__":  # test : python3 -m collectors.dhgate_sold "ceiling fan"
    import sys
    kw = sys.argv[1] if len(sys.argv) > 1 else "ceiling fan"
    d = fetch_demand(kw)
    if d.blocked:
        print(f"⚠ « {kw} » : donnée indisponible (IP bloquée ou page anti-bot).")
    elif d.max_sold is None:
        print(f"« {kw} » : page OK mais aucun compteur « recently sold » trouvé.")
    else:
        print(f"Mot-clé                 : {kw}")
        print(f"Ventes récentes max     : {d.max_sold:,}")
        print(f"Ventes récentes médianes: {d.median_sold:,}")
        print(f"Annonces avec ventes    : {d.listings_with_sales}")
