"""Collecteur AliExpress — ground-truth des VENTES réelles, en best-effort.

AliExpress embarque dans le HTML de recherche un blob JSON (``_init_data_``) où chaque
produit porte ``trade.tradeDesc`` = son nombre de ventes (« + 10 000 vendus »). C'est le
signal demande le plus pertinent qui soit : des **unités réellement vendues** pour le
type de produit, pas une simple intention de recherche.

MAIS AliExpress protège ces pages : une requête à FROID passe (HTML riche), puis l'IP
bascule en page « punish/captcha » sous accès automatisé répété. On ne peut donc pas en
faire une source fiable de cron — on l'exploite en **best-effort discipliné** :

* **cache disque 24 h** : une même recherche ne retape jamais AliExpress dans la journée ;
* **intervalle mini long** entre requêtes (politesse anti-déclenchement) ;
* **détection de la page punish** → on ARRÊTE immédiatement (lève ``AliExpressBlocked``),
  jamais de matraquage qui aggraverait le cooldown de l'IP ;
* **dégradation gracieuse** : si bloqué/erreur, on renvoie ``blocked=True`` — ce qui veut
  dire « donnée indisponible », surtout PAS « zéro demande » (le scoring doit l'ignorer,
  pas la compter comme nulle).

Le socle robuste de demande reste eBay (API officielle) : AliExpress n'est qu'un bonus.

Aucune dépendance externe : urllib + json + re (stdlib) uniquement.
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
_CACHE_DIR = Path(__file__).resolve().parent.parent / ".aliexpress_cache"
_CACHE_TTL_SECONDS = 24 * 3600          # 24 h : une recherche/jour suffit
_MIN_REQUEST_INTERVAL = 8.0             # politesse longue (anti-punish)
_last_request_ts = 0.0

# Signatures de la page anti-bot AliExpress (« x5/baxia »).
_PUNISH_MARKERS = ("_____tmd_____/punish", '"action":"captcha"', "x5secdata", "slidecaptcha")
# Compteur de ventes : « + 10 000 vendus », « 1 234 sold », « 500+ orders »…
_SOLD_RE = re.compile(r'tradeDesc"?\s*:\s*"([^"]*?)"')
_DIGITS_RE = re.compile(r"\d[\d\s  .,]*")


class AliExpressBlocked(Exception):
    """L'IP a reçu la page punish/captcha : donnée momentanément indisponible."""


@dataclass(slots=True)
class AliExpressDemand:
    """Photo des ventes AliExpress pour un mot-clé (ou blocage signalé)."""

    keyword: str
    max_sold: int | None = None          # plus gros compteur vu = plafond de demande
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


# --- Récupération HTML (à froid, polie) ------------------------------------

def _fetch_html(keyword: str) -> str:
    """GET de la page de recherche AliExpress. Lève si page punish détectée."""
    global _last_request_ts
    wait = _MIN_REQUEST_INTERVAL - (time.time() - _last_request_ts)
    if wait > 0:
        time.sleep(wait)
    url = "https://www.aliexpress.com/af/" + urllib.parse.quote(keyword) + ".html"
    try:
        res = http.get_text(url, headers={"Accept": "text/html,application/xhtml+xml"},
                            timeout=20)
    finally:
        _last_request_ts = time.time()
    body = res.text
    # status 0 = échec transport ; 403/429/503 = anti-bot ; sinon marqueurs punish.
    if (res.status in (0, 403, 429, 503)
            or any(m in body for m in _PUNISH_MARKERS) or len(body) < 5000):
        raise AliExpressBlocked("Page punish/captcha AliExpress (IP en cooldown).")
    return body


# --- Parsing des compteurs de ventes ---------------------------------------

def _parse_sold(desc: str) -> int | None:
    """« + 10 000 vendus » / « 1 234 sold » → 10000 / 1234. None si pas de chiffre."""
    m = _DIGITS_RE.search(desc)
    if not m:
        return None
    digits = re.sub(r"[^\d]", "", m.group(0))
    return int(digits) if digits else None


def fetch_demand(keyword: str) -> AliExpressDemand:
    """Renvoie les ventes AliExpress agrégées d'un mot-clé (best-effort).

    - Sert le cache 24 h si disponible.
    - Sinon tente UNE requête à froid ; si l'IP est punie, renvoie ``blocked=True``
      sans réessayer (évite d'aggraver le cooldown).
    """
    cached = _cache_get(keyword)
    if cached is not None:
        body = cached
    else:
        try:
            body = _fetch_html(keyword)
        except AliExpressBlocked:
            # Le transport (utils.http) ne lève pas : il renvoie status 0 sur échec
            # réseau, converti ici en blocage. Toute autre erreur inattendue = blocage.
            return AliExpressDemand(keyword=keyword, blocked=True)
        except Exception:
            return AliExpressDemand(keyword=keyword, blocked=True)
        _cache_put(keyword, body)

    sold_values = [s for s in (_parse_sold(d) for d in _SOLD_RE.findall(body)) if s]
    if not sold_values:
        # Page lisible mais aucun compteur : vraie absence de ventes listées (≠ blocage).
        return AliExpressDemand(keyword=keyword, blocked=False)
    sold_values.sort()
    mid = sold_values[len(sold_values) // 2]
    return AliExpressDemand(
        keyword=keyword,
        max_sold=max(sold_values),
        median_sold=mid,
        listings_with_sales=len(sold_values),
        blocked=False,
    )


if __name__ == "__main__":  # test : python3 -m collectors.aliexpress_orders "ceiling fan"
    import sys
    kw = sys.argv[1] if len(sys.argv) > 1 else "ceiling fan"
    d = fetch_demand(kw)
    if d.blocked:
        print(f"⚠ « {kw} » : donnée indisponible (IP punie ou page bloquée).")
    elif d.max_sold is None:
        print(f"« {kw} » : page OK mais aucun compteur de ventes trouvé.")
    else:
        print(f"Mot-clé             : {kw}")
        print(f"Ventes max (plafond): {d.max_sold:,}")
        print(f"Ventes médianes     : {d.median_sold:,}")
        print(f"Annonces avec ventes: {d.listings_with_sales}")
