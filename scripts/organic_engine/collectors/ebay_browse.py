"""Collecteur eBay Browse API — signal demande robuste et pérenne (API officielle).

Pourquoi eBay (et pas le scraping) : AliExpress sert la donnée à froid mais bascule
en captcha sous accès automatisé répété (risque de soft-ban de l'IP). eBay expose au
contraire une **API officielle gratuite** sans anti-bot, idéale pour du cron.

Ce que l'API gratuite donne réellement :
* ``item_summary/search`` (Browse API) → **annonces ACTIVES** correspondant à un mot-clé
  (champ ``total``) + le **prix** de chaque annonce. C'est un signal de présence/
  concurrence sur une marketplace consommateur réelle (indépendant du ``listedNum``
  CJ, qui est côté fournisseur), et une validation indépendante de la bande de prix.
* Les vraies données de VENTES (sold/completed) sont derrière la *Marketplace Insights
  API* (limited release, refusée aux devs indépendants) et l'ancienne Finding API a été
  retirée début 2025. On ne les obtient donc PAS ici — le ground-truth ventes vient,
  best-effort, du collecteur AliExpress.

Auth : OAuth 2.0 **client credentials** (token applicatif, ~2 h), mis en cache fichier.
Identifiants attendus dans l'environnement (cf. ``~/tandor.env``) :
    EBAY_CLIENT_ID      = App ID (Client ID) de l'app de production eBay
    EBAY_CLIENT_SECRET  = Cert ID (Client Secret)

Aucune dépendance externe : urllib + json (stdlib) uniquement.
"""

from __future__ import annotations

import base64
import json
import os
import statistics
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

_OAUTH_URL = "https://api.ebay.com/identity/v1/oauth2/token"
_SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
_SCOPE = "https://api.ebay.com/oauth/api_scope"
_TOKEN_CACHE = Path(__file__).resolve().parent.parent / ".ebay_token.json"
# Le token applicatif vaut ~7200 s ; on le rafraîchit avec une marge de sécurité.
_TOKEN_TTL_MARGIN = 300
# Marketplace par défaut (FR : aligne devise/prix sur le marché ciblé).
_DEFAULT_MARKETPLACE = "EBAY_FR"


class EbayError(Exception):
    """Erreur d'accès à l'API eBay (auth, quota, indisponibilité)."""


@dataclass(slots=True)
class EbayDemand:
    """Photo de la demande eBay pour un mot-clé (annonces actives + prix)."""

    keyword: str
    active_listings: int                 # nb total d'annonces actives (champ `total`)
    price_min: float | None = None
    price_median: float | None = None
    price_max: float | None = None
    currency: str | None = None
    sample: int = 0                      # nb d'annonces réellement échantillonnées
    marketplace: str = _DEFAULT_MARKETPLACE

    def as_dict(self) -> dict:
        return {
            "keyword": self.keyword,
            "activeListings": self.active_listings,
            "priceMin": self.price_min,
            "priceMedian": self.price_median,
            "priceMax": self.price_max,
            "currency": self.currency,
            "sample": self.sample,
            "marketplace": self.marketplace,
        }


# --- OAuth (client credentials) --------------------------------------------

def _load_cached_token() -> str | None:
    if not _TOKEN_CACHE.exists():
        return None
    try:
        cached = json.loads(_TOKEN_CACHE.read_text())
        if time.time() < cached.get("expires_at", 0) - _TOKEN_TTL_MARGIN:
            return cached.get("token")
    except Exception:
        return None
    return None


def _store_token(token: str, expires_in: int) -> None:
    try:
        _TOKEN_CACHE.write_text(json.dumps(
            {"token": token, "expires_at": time.time() + float(expires_in)}))
    except Exception:
        pass  # cache best-effort


def get_app_token(client_id: str | None = None, client_secret: str | None = None) -> str:
    """Récupère un token applicatif eBay (depuis le cache fichier si encore valide)."""
    cached = _load_cached_token()
    if cached:
        return cached
    cid = client_id or os.environ.get("EBAY_CLIENT_ID", "")
    secret = client_secret or os.environ.get("EBAY_CLIENT_SECRET", "")
    if not cid or not secret:
        raise EbayError("EBAY_CLIENT_ID / EBAY_CLIENT_SECRET manquants "
                        "(crée une app sur developer.ebay.com puis renseigne ~/tandor.env).")
    basic = base64.b64encode(f"{cid}:{secret}".encode()).decode()
    body = urllib.parse.urlencode({
        "grant_type": "client_credentials", "scope": _SCOPE}).encode()
    req = urllib.request.Request(
        _OAUTH_URL, data=body, method="POST",
        headers={"Authorization": f"Basic {basic}",
                 "Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:200]
        raise EbayError(f"OAuth eBay HTTP {exc.code} : {detail}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise EbayError(f"OAuth eBay injoignable : {exc}") from exc
    token = payload.get("access_token")
    if not token:
        raise EbayError("Token absent de la réponse OAuth eBay.")
    _store_token(token, payload.get("expires_in", 7200))
    return token


# --- Recherche d'annonces ---------------------------------------------------

def fetch_demand(
    keyword: str,
    marketplace: str = _DEFAULT_MARKETPLACE,
    limit: int = 50,
    new_only: bool = True,
) -> EbayDemand:
    """Interroge Browse API pour un mot-clé → annonces actives + stats de prix.

    Dégradation gracieuse : en cas d'erreur réseau/quota, renvoie un
    :class:`EbayDemand` à 0 annonce plutôt que de lever (le pipeline continue).
    """
    try:
        token = get_app_token()
    except EbayError:
        return EbayDemand(keyword=keyword, active_listings=0, marketplace=marketplace)

    params = {"q": keyword, "limit": str(limit)}
    if new_only:
        params["filter"] = "conditions:{NEW}"
    url = f"{_SEARCH_URL}?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "X-EBAY-C-MARKETPLACE-ID": marketplace,
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # 401 = token périmé/invalide : on purge le cache pour forcer un refresh au prochain run.
        if exc.code == 401:
            try:
                _TOKEN_CACHE.unlink(missing_ok=True)
            except Exception:
                pass
        return EbayDemand(keyword=keyword, active_listings=0, marketplace=marketplace)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return EbayDemand(keyword=keyword, active_listings=0, marketplace=marketplace)

    total = int(data.get("total", 0) or 0)
    prices: list[float] = []
    currency: str | None = None
    for item in data.get("itemSummaries", []) or []:
        p = item.get("price") or {}
        try:
            prices.append(float(p.get("value")))
            currency = currency or p.get("currency")
        except (TypeError, ValueError):
            continue
    prices.sort()
    return EbayDemand(
        keyword=keyword,
        active_listings=total,
        price_min=round(prices[0], 2) if prices else None,
        price_median=round(statistics.median(prices), 2) if prices else None,
        price_max=round(prices[-1], 2) if prices else None,
        currency=currency,
        sample=len(prices),
        marketplace=marketplace,
    )


if __name__ == "__main__":  # test : python3 -m collectors.ebay_browse "ceiling fan"
    import sys
    kw = sys.argv[1] if len(sys.argv) > 1 else "ceiling fan"
    try:
        get_app_token()
        print("✓ Token applicatif eBay obtenu")
    except EbayError as exc:
        print(f"✗ {exc}")
        sys.exit(1)
    d = fetch_demand(kw)
    print(f"Mot-clé          : {d.keyword}  ({d.marketplace})")
    print(f"Annonces actives : {d.active_listings:,}")
    if d.sample:
        print(f"Prix (n={d.sample}) : min {d.price_min} / méd {d.price_median} / "
              f"max {d.price_max} {d.currency}")
    else:
        print("Aucun prix échantillonné (mot-clé sans annonce ?).")
