"""Collecteur eBay « sold/completed » — signal de VENTES réelles, gratuit et à fort volume.

Pourquoi cette source ?
-----------------------
AliExpress donne les unités vendues, mais son anti-bot rate-limite par IP : insoluble en
mono-IP. eBay, lui, expose publiquement la page des annonces **VENDUES / terminées** :

    https://www.ebay.com/sch/i.html?_nkw=<kw>&LH_Sold=1&LH_Complete=1

Cette page liste les ventes récentes (fenêtre « sold » d'eBay, ~90 derniers jours) et
affiche en tête un compteur « N+ results » = le **nombre d'annonces vendues** qui matchent
le mot-clé. C'est un signal de demande RÉELLE (des transactions, pas des intentions), à fort
volume et sans rate-limit par IP agressif.

⚠️  Ce collecteur N'UTILISE AUCUNE API.
    - `ebay_browse.py` utilise l'API officielle Browse (OAuth) qui ne renvoie QUE les annonces
      ACTIVES, jamais les ventes (sold = Marketplace Insights API, refusée aux indés ; Finding
      API retirée en 2025). On NE s'en inspire PAS.
    - Ici on SCRAPE la page web publique via curl (subprocess) : Akamai 503 l'empreinte
      TLS de urllib, curl (HTTP/2 + empreinte navigateur) passe. Parsing en re pur.

Anti-bot eBay (Akamai Bot Manager + interstitiel « Pardon Our Interruption ») :
    - Une requête directe sur /sch/i.html à froid → 403 / 503 / interstitiel.
    - La parade gratuite, validée en live : ouvrir une **session avec cookie jar**, visiter
      d'abord la home (qui pose les cookies `bm_*` / `__uzm*`), PUIS taper la recherche avec
      un `Referer` vers la home. Sur cette IP maison : 30/30 mots-clés OK à ~3-6 s d'intervalle,
      0 captcha. Un 503 transitoire arrive parfois sur le tout premier hit → on réamorce une
      session fraîche et on retente UNE fois.

Sémantique des champs (IMPORTANT pour ne pas tromper le scoring)
----------------------------------------------------------------
eBay n'expose PAS, sur cette page de résultats, un « X unités vendues » par annonce. Le signal
de demande est donc le **nombre d'annonces vendues** :

    * ``listings_with_sales`` = compteur « N results » d'eBay = nombre d'annonces VENDUES sur
      la fenêtre récente pour ce mot-clé. C'est la mesure d'intensité de demande principale.
    * ``max_sold``    = ce MÊME compteur « N results » (intensité de demande agrégée). On le
      réutilise comme ``max_sold`` pour rester compatible avec la forme ``sales_snapshots``
      partagée avec AliExpress, où ``max_sold`` est le plafond de demande. ⚠️ Ici ce n'est PAS
      un nombre d'unités d'une seule annonce, mais le total d'annonces vendues du mot-clé.
    * ``median_sold`` = nombre d'annonces vendues réellement échantillonnées sur la page
      (cartes parsées, typiquement ~60/page). Proxy de densité « il y a bien des ventes ».
    * Bonus prix : ``min_price`` / ``median_price`` / ``max_price`` (USD) des annonces vendues
      échantillonnées — utile pour situer le ticket, hors forme canonique.

Dégradation gracieuse : ``fetch_demand`` ne lève JAMAIS. En cas de blocage/erreur réseau →
``blocked=True`` (= donnée indisponible, surtout PAS « zéro demande » : le scoring doit
l'ignorer, pas la compter comme nulle).
"""

from __future__ import annotations

import hashlib
import os
import re
import statistics
import subprocess
import tempfile
import time
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

from utils import http  # transport partagé curl_cffi chrome131 (→ urllib de repli)

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
_CACHE_DIR = Path(__file__).resolve().parent.parent / ".ebay_sold_cache"
_CACHE_TTL_SECONDS = 24 * 3600          # 24 h : une recherche/jour suffit
# Pacing intra-process. Sur IP fraîche : 3-6 s tiennent (20/20 OK en live). Mais après
# une rafale l'IP « flappe » et n'encaisse plus qu'~1 requête sold / ~2 min. On choisit un
# plancher prudent pour un cron durable ; le runner espace de toute façon les mots-clés.
_MIN_REQUEST_INTERVAL = 30.0
_last_request_ts = 0.0
_last_request_ts = 0.0

_HOME = "https://www.ebay.com/"
_SEARCH = ("https://www.ebay.com/sch/i.html?_nkw={kw}"
           "&LH_Sold=1&LH_Complete=1")
# Même recherche SANS les filtres sold/complete = annonces ACTIVES (numérateur du glut).
_SEARCH_ACTIVE = "https://www.ebay.com/sch/i.html?_nkw={kw}"

# Interstitiel anti-bot eBay (Akamai / « Pardon Our Interruption »).
_BLOCK_MARKERS = ("Pardon Our Interruption", "Checking your browser",
                  "Something went wrong on our end")
# Compteur « N+ results » dans le bandeau <h1 class=...__count-heading> … </h1>.
_COUNT_RE = re.compile(
    r'__count-heading>.*?<span[^>]*>([\d,]+)</span>.*?(\+?)\s*results?', re.S)
# Prix d'une carte de résultat vendue : <span class="... s-card__price">$54.90</span>.
_PRICE_RE = re.compile(r's-card__price[^>]*>\s*\$?([\d,]+\.\d{2})')
# Tampon « Sold Jun 21, 2026 » = preuve qu'une carte est bien une vente.
_SOLD_DATE_RE = re.compile(r'Sold\s+[A-Z][a-z]{2}\s+\d{1,2}', re.I)


class EbaySoldBlocked(Exception):
    """eBay a servi l'interstitiel anti-bot : donnée momentanément indisponible."""


@dataclass(slots=True)
class EbaySoldDemand:
    """Photo des VENTES eBay pour un mot-clé (ou blocage signalé).

    Voir l'en-tête du module pour la sémantique exacte. En résumé : tous les compteurs
    expriment un **nombre d'annonces vendues**, pas un nombre d'unités par annonce.
    """

    keyword: str
    max_sold: int | None = None          # = « N results » : total annonces vendues du mot-clé
    median_sold: int | None = None       # = nb d'annonces vendues échantillonnées sur la page
    listings_with_sales: int = 0         # = « N results » (intensité de demande principale)
    blocked: bool = False                # True = donnée indisponible (≠ zéro demande)
    # Bonus prix (USD) — hors forme canonique sales_snapshots.
    min_price: float | None = None
    median_price: float | None = None
    max_price: float | None = None

    # --- Signal de SATURATION par l'offre (opt-in, with_glut=True) ----------
    # Nombre d'annonces ACTIVES (même recherche SANS &LH_Sold=1&LH_Complete=1).
    # None = donnée non collectée OU requête « actives » bloquée (≠ zéro annonce).
    active_count: int | None = None
    # « Glut » = engorgement = annonces actives / demande réelle.
    # Dénominateur choisi : ``max_sold`` (= compteur « N results » des annonces VENDUES,
    # notre mesure d'intensité de demande agrégée la plus directe et symétrique au numérateur
    # — actives et vendues sont tous deux des compteurs « N results » de la MÊME recherche,
    # donc le ratio est homogène : « combien d'annonces actives par annonce vendue »).
    # ``median_sold`` (cartes échantillonnées, plafonné ~60/page) serait borné et biaiserait
    # le ratio vers le haut sur les mots-clés populaires. Glut élevé = beaucoup d'offre pour
    # peu de ventes = marché engorgé = piège à fric.
    glut: float | None = None

    # Alias pour la forme canonique ``sales_snapshots`` (record_aliexpress lit ``n_results``).
    @property
    def n_results(self) -> int:
        return self.listings_with_sales

    def as_dict(self) -> dict:
        return {
            "keyword": self.keyword,
            "maxSold": self.max_sold,
            "medianSold": self.median_sold,
            "listingsWithSales": self.listings_with_sales,
            "blocked": self.blocked,
            "minPrice": self.min_price,
            "medianPrice": self.median_price,
            "maxPrice": self.max_price,
            "activeCount": self.active_count,
            "glut": self.glut,
        }


# --- Cache disque ----------------------------------------------------------

def _cache_path(kw: str, kind: str = "sold") -> Path:
    # ``kind`` ("sold"/"active") évite que les pages vendues et actives du même mot-clé
    # ne se collisionnent dans le cache. "sold" garde l'ancienne clé (rétro-compatible).
    key = kw if kind == "sold" else f"{kind}:{kw}"
    return _CACHE_DIR / f"{hashlib.sha256(key.encode()).hexdigest()[:20]}.html"


def _cache_get(kw: str, kind: str = "sold") -> str | None:
    p = _cache_path(kw, kind)
    if not p.exists():
        return None
    try:
        if time.time() - p.stat().st_mtime > _CACHE_TTL_SECONDS:
            return None
        return p.read_text()
    except Exception:
        return None


def _cache_put(kw: str, text: str, kind: str = "sold") -> None:
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _cache_path(kw, kind).write_text(text)
    except Exception:
        pass  # cache best-effort


# --- Récupération HTML (session + warm-up home, polie) ---------------------
#
# ⚠️  Transport = curl (subprocess), PAS urllib. Mesuré en live (2026-06-26) : Akamai
# Bot Manager 503 systématiquement l'empreinte TLS/HTTP-1.1 de urllib dès le warm-up
# home (0 succès, le cache n'avait jamais été créé). curl (HTTP/2 + empreinte navigateur)
# passe en 200 sur la MÊME IP, même UA. On reste 100 % scraping de la page publique, zéro API.

_CURL = "curl"


def _curl_get(url: str, jar: str, referer: str | None = None) -> str:
    """GET via curl, cookies persistés dans ``jar``. Lève EbaySoldBlocked sur échec/HTTP≥400."""
    cmd = [
        _CURL, "-s", "--compressed", "--max-time", "25",
        "-c", jar, "-b", jar,
        "-A", _UA,
        "-H", "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "-H", "Accept-Language: en-US,en;q=0.9",
        "-H", "Upgrade-Insecure-Requests: 1",
    ]
    if referer:
        cmd += ["-H", f"Referer: {referer}"]
    cmd += ["-w", "\n%{http_code}", url]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=40)
    except (subprocess.TimeoutExpired, OSError) as exc:
        raise EbaySoldBlocked(f"curl error: {exc}") from exc
    raw = proc.stdout
    nl = raw.rfind(b"\n")
    code = raw[nl + 1:].decode("ascii", "replace").strip() if nl >= 0 else ""
    body = raw[:nl].decode("utf-8", "replace") if nl >= 0 else ""
    if proc.returncode != 0 or not code.isdigit() or int(code) >= 400:
        raise EbaySoldBlocked(f"curl rc={proc.returncode} http={code or '?'}")
    return body


def _fetch_once(keyword: str, search_tmpl: str = _SEARCH) -> str:
    """UNE tentative : session fraîche → home (seed cookies) → recherche.

    ``search_tmpl`` = gabarit d'URL ({kw}) : sold par défaut, actives en opt-in.
    Lève ``EbaySoldBlocked`` si interstitiel/erreur HTTP, pour permettre un retry propre.
    """
    global _last_request_ts
    wait = _MIN_REQUEST_INTERVAL - (time.time() - _last_request_ts)
    if wait > 0:
        time.sleep(wait)
    # Session FRAÎCHE par tentative (cookies bm_*/__uzm* posés par la home), désormais
    # via curl_cffi impersonate chrome131 : empreinte TLS/JA3 + HTTP/2 d'un VRAI Chrome,
    # strictement meilleure que le curl-subprocess générique (mesuré live : home 200,
    # recherche sold 200 / 1,4 Mo, Akamai passé) — et sans subprocess ni cookie jar temp.
    sess = http.Session()
    try:
        home = sess.get_text(_HOME, headers={"Upgrade-Insecure-Requests": "1"}, timeout=25)
        if home.status == 0 or home.status >= 400:
            raise EbaySoldBlocked(f"home http={home.status}")
        url = search_tmpl.format(kw=urllib.parse.quote(keyword))
        res = sess.get_text(url, headers={
            "Upgrade-Insecure-Requests": "1",
            "Referer": _HOME,
        }, timeout=25)
        if res.status == 0 or res.status >= 400:
            raise EbaySoldBlocked(f"search http={res.status}")
        body = res.text
    finally:
        _last_request_ts = time.time()
        sess.close()
    if any(m in body for m in _BLOCK_MARKERS) or len(body) < 100_000:
        raise EbaySoldBlocked("Interstitiel anti-bot eBay (Akamai).")
    return body


def _fetch_html(keyword: str, retries: int = 0, search_tmpl: str = _SEARCH) -> str:
    """Récupère la page sold. Par défaut UNE seule tentative (``retries=0``).

    ⚠️  Leçon mesurée en live : quand l'IP est en cooldown léger (après une rafale),
    elle « flappe » et n'accepte qu'environ **une requête sold toutes les ~2 min**. Or
    chaque tentative = 2 hits (warm-up home + recherche). Empiler des retries rapides
    déclenche systématiquement le blocage au lieu de le contourner — c'est CONTRE-productif.

    On fait donc UN essai propre par appel et on laisse la cadence au CALLER (le runner
    24/7 espace déjà les mots-clés de plusieurs minutes ; ``_MIN_REQUEST_INTERVAL`` garantit
    un plancher intra-process). ``retries`` reste réglable pour un usage interactif où l'on
    accepte d'attendre, avec backoff long entre tentatives."""
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return _fetch_once(keyword, search_tmpl)
        except EbaySoldBlocked as exc:
            last = exc
            if attempt < retries:
                # backoff LONG : on attend que le flap retombe (≥ 2 min observées).
                time.sleep(120 * (attempt + 1))
    raise last if last else EbaySoldBlocked("blocage inconnu")


# --- Parsing de la page de résultats vendus --------------------------------

def _parse(body: str) -> tuple[int | None, int, list[float]]:
    """→ (n_results, nb_cartes_vendues_échantillonnées, prix USD)."""
    n_results: int | None = None
    m = _COUNT_RE.search(body)
    if m:
        try:
            n_results = int(m.group(1).replace(",", ""))
        except ValueError:
            n_results = None
    sampled = len(_SOLD_DATE_RE.findall(body))
    prices: list[float] = []
    for p in _PRICE_RE.findall(body):
        try:
            prices.append(float(p.replace(",", "")))
        except ValueError:
            pass
    return n_results, sampled, prices


def _fetch_active_count(keyword: str) -> int | None:
    """Nombre d'annonces ACTIVES pour ``keyword`` (recherche sans filtre sold/complete).

    Réutilise le cache (namespace "active"), le pacing et le warm-up de la voie sold.
    Renvoie ``None`` si blocage/erreur ou compteur introuvable (donnée indisponible,
    PAS zéro) — ne lève jamais : l'appelant garde le reste du résultat sold intact.
    """
    cached = _cache_get(keyword, kind="active")
    if cached is not None:
        body = cached
    else:
        try:
            body = _fetch_html(keyword, search_tmpl=_SEARCH_ACTIVE)
        except EbaySoldBlocked:
            return None
        _cache_put(keyword, body, kind="active")
    n_results, _sampled, _prices = _parse(body)
    return n_results


def fetch_demand(keyword: str, with_glut: bool = False) -> EbaySoldDemand:
    """Renvoie les VENTES eBay agrégées d'un mot-clé. Ne lève JAMAIS.

    - Sert le cache 24 h si dispo.
    - Sinon : session fraîche + warm-up home + recherche sold (avec retries + backoff sur blocage).
    - Blocage/erreur → ``blocked=True`` (donnée indisponible, ≠ zéro demande).

    ``with_glut`` (opt-in, défaut False) : si True, effectue +1 requête réseau pour
    compter les annonces ACTIVES et calcule le ``glut`` (saturation par l'offre).
    Avec False, comportement strictement inchangé : zéro requête supplémentaire.
    Si la requête « actives » est bloquée → active_count/glut restent None, le reste
    du résultat est préservé.
    """
    cached = _cache_get(keyword)
    if cached is not None:
        body = cached
    else:
        try:
            body = _fetch_html(keyword)
        except EbaySoldBlocked:
            return EbaySoldDemand(keyword=keyword, blocked=True)
        _cache_put(keyword, body)

    n_results, sampled, prices = _parse(body)

    if not n_results and sampled == 0:
        # Page lisible mais aucune vente listée : vraie absence de ventes (≠ blocage).
        result = EbaySoldDemand(keyword=keyword, blocked=False)
    else:
        # Plafond de demande = « N results » si dispo, sinon au moins l'échantillon vu.
        demand = n_results if n_results is not None else sampled

        min_p = med_p = max_p = None
        if prices:
            min_p = min(prices)
            max_p = max(prices)
            med_p = round(statistics.median(prices), 2)

        result = EbaySoldDemand(
            keyword=keyword,
            max_sold=demand,
            median_sold=sampled,
            listings_with_sales=demand,
            blocked=False,
            min_price=min_p,
            median_price=med_p,
            max_price=max_p,
        )

    if with_glut:
        active = _fetch_active_count(keyword)
        if active is not None:
            result.active_count = active
            # Dénominateur = demande réelle. ``max_sold`` (compteur N annonces vendues)
            # si dispo (symétrique au numérateur), sinon ``listings_with_sales`` ; on borne
            # à 1 pour éviter une division par zéro. Glut élevé = offre >> ventes = engorgé.
            denom = max(result.max_sold or result.listings_with_sales or 0, 1)
            result.glut = round(active / denom, 3)

    return result


if __name__ == "__main__":  # python3 -m collectors.ebay_sold "ceiling fan" [--glut]
    import sys
    args = [a for a in sys.argv[1:] if a != "--glut"]
    with_glut = "--glut" in sys.argv
    kw = args[0] if args else "ceiling fan"
    d = fetch_demand(kw, with_glut=with_glut)
    if d.blocked:
        print(f"⚠ « {kw} » : donnée indisponible (interstitiel eBay ou réseau).")
    elif d.max_sold is None:
        print(f"« {kw} » : page OK mais aucune vente trouvée.")
    else:
        print(f"Mot-clé                 : {kw}")
        print(f"Annonces vendues (N)    : {d.listings_with_sales:,}")
        print(f"  → max_sold (=N)       : {d.max_sold:,}")
        print(f"  → median_sold (éch.)  : {d.median_sold:,} cartes sur la page")
        if d.median_price is not None:
            print(f"Prix USD (min/méd/max)  : "
                  f"${d.min_price:.2f} / ${d.median_price:.2f} / ${d.max_price:.2f}")
        if with_glut:
            ac = "indispo" if d.active_count is None else f"{d.active_count:,}"
            gl = "indispo" if d.glut is None else f"{d.glut}"
            print(f"Annonces ACTIVES        : {ac}")
            print(f"Glut (actives/vendues)  : {gl}")
