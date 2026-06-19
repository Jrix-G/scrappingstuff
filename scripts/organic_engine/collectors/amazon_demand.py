"""Collecteur Amazon — signal de demande PRIMAIRE de Tandor (« bought in past month »).

Amazon affiche sur ses pages de recherche un badge « X bought in past month » par
produit (ex. « 2K+ bought in past month »). C'est de la **vélocité de vente sur 30
jours glissants** chez les acheteurs occidentaux — le signal de demande le plus frais
et le plus pertinent pour détecter un produit qui monte MAINTENANT.

Mesuré le 2026-06-17 : ~40 produits avec badge par recherche, et l'IP maison encaisse
des dizaines de requêtes rapprochées sans captcha. C'est donc une source à HAUT volume
(contrairement à AliExpress, plafonné ~250/jour par x5sec — cf collectors/aliexpress_orders.py).

Stratégie best-effort discipliné, identique en esprit à AliExpress :
* cache disque (TTL configurable) : un même mot-clé ne retape jamais Amazon dans la fenêtre ;
* pacing aléatoire 5–10 s entre requêtes (anti-pattern, géré par le runner) ;
* détection robuste de la page captcha/throttle → on lève ``AmazonBlocked`` (jamais de
  matraquage) ;
* dégradation gracieuse : si bloqué/erreur → ``blocked=True`` = « donnée indisponible »,
  surtout PAS « zéro demande ».

Dépendance : curl_cffi (impersonate Chrome = empreinte TLS/HTTP2 réaliste).
"""

from __future__ import annotations

import hashlib
import random
import re
import time
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

from curl_cffi import requests as creq

_CACHE_DIR = Path(__file__).resolve().parent.parent / ".amazon_cache"
_CACHE_TTL_SECONDS = 12 * 3600          # 12 h : la vélocité bouge lentement

# Personas Chrome : profil curl_cffi (empreinte TLS/JA3) + UA + Client Hints assortis.
# CRITIQUE : sec-ch-ua "Not_A Brand" version change selon Chrome :
#   Chrome 131 → v="24", Chrome 124 → v="8", Chrome 120 → v="99"
# L'ordre des headers (cache-control → sec-ch-ua → user-agent → ...) est reproduit
# par curl_cffi via BoringSSL — ne pas modifier l'ordre dans _headers().
_PERSONAS = [
    ("chrome131",
     "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
     "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
     '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"'),
    ("chrome124",
     "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
     "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
     '"Google Chrome";v="124", "Chromium";v="124", "Not_A Brand";v="8"'),
    ("chrome120",
     "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
     "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
     '"Google Chrome";v="120", "Chromium";v="120", "Not_A Brand";v="99"'),
]

# Marqueurs de la page captcha/robot-check d'Amazon (servie en HTTP 200 !).
_BLOCK_MARKERS = (
    "api-services-support@amazon.com",
    "Enter the characters you see below",
    "/errors/validateCaptcha",
    "Type the characters you see in this image",
    "To discuss automated access to Amazon data",
    "Robot Check",
    "Sorry, we just need to make sure you're not a robot",
)
# Marqueur POSITIF : une vraie page /s contient toujours des cartes résultat.
_RESULT_MARKER = 'data-component-type="s-search-result"'


def _headers(ua: str, sec_ch_ua: str) -> dict:
    # Ordre exact de Chrome 131 sur Windows : cache-control en premier, sec-ch-ua
    # AVANT user-agent. Les WAFs (Akamai/CloudFront) scorent l'ordre des headers.
    return {
        "cache-control": "max-age=0",
        "sec-ch-ua": sec_ch_ua,
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "upgrade-insecure-requests": "1",
        "user-agent": ua,
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,"
                  "image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "sec-fetch-site": "none",
        "sec-fetch-mode": "navigate",
        "sec-fetch-user": "?1",
        "sec-fetch-dest": "document",
        "accept-encoding": "gzip, deflate, br, zstd",
        "accept-language": "en-US,en;q=0.9",
    }


def _human_delay(base_min: float = 3.0, base_max: float = 7.0) -> None:
    """Pause avec jitter gaussien — plus réaliste qu'un uniform pur."""
    base = random.uniform(base_min, base_max)
    jitter = abs(random.gauss(0, 0.4))
    time.sleep(base + jitter)

_BADGE_RE = re.compile(r"([\d.,]+[KkMm]?\+?)\s*bought in past month")
_ASIN_RE = re.compile(r'data-asin="([A-Z0-9]{10})"')


class AmazonBlocked(Exception):
    """Page captcha/robot-check Amazon : donnée momentanément indisponible."""


@dataclass(slots=True)
class AmazonDemand:
    """Photo de la vélocité de vente Amazon pour un mot-clé (ou blocage signalé)."""

    keyword: str
    max_bought: int | None = None        # plus gros « bought/month » = plafond de demande
    median_bought: int | None = None
    n_with_velocity: int = 0             # nb de produits portant un badge
    n_results: int = 0                   # nb total de résultats vus
    blocked: bool = False

    def as_dict(self) -> dict:
        return {
            "keyword": self.keyword,
            "maxBought": self.max_bought,
            "medianBought": self.median_bought,
            "nWithVelocity": self.n_with_velocity,
            "nResults": self.n_results,
            "blocked": self.blocked,
        }


# --- Normalisation « 2K+ » → 2000 -----------------------------------------

def normalize_bought(raw: str) -> int | None:
    """« 50+ »→50, « 1K+ »→1000, « 20K+ »→20000, « 1.5M+ »→1500000."""
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
        pass


# --- Session (réutilisable par le runner pour garder les cookies) ----------

def make_session() -> "creq.Session":
    """Nouvelle persona : profil curl_cffi + UA + Client Hints assortis, cookies warmés."""
    profile, ua, sec_ch_ua = random.choice(_PERSONAS)
    s = creq.Session(impersonate=profile)
    s.headers.update(_headers(ua, sec_ch_ua))
    s._tandor_ua      = ua         # mémorise pour les requêtes suivantes
    s._tandor_sec_cua = sec_ch_ua
    try:
        # Warmup homepage : pose session-id + ubid-main + aws-waf-token
        # Sans ce warm-up, le score de confiance Amazon est faible dès la 1ère req cible
        s.get("https://www.amazon.com/", headers=_headers(ua, sec_ch_ua), timeout=20)
        _human_delay(1.5, 3.0)
    except Exception:
        pass
    return s


# --- Récupération + parsing ------------------------------------------------

def _is_blocked(status: int, body: str) -> bool:
    if status in (429, 503, 403, 500):
        return True
    if len(body) < 100_000:
        return True
    # Check uniquement les 4 000 premiers chars (O(1) vs O(n)) — captcha est dans le title
    probe = body[:4000].lower()
    if any(m.lower() in probe for m in _BLOCK_MARKERS):
        return True
    if _RESULT_MARKER not in body:
        return True
    return False


def _fetch_html(keyword: str, session: "creq.Session | None") -> str:
    s = session or make_session()
    ua    = getattr(s, "_tandor_ua",     _PERSONAS[0][1])
    s_cua = getattr(s, "_tandor_sec_cua", _PERSONAS[0][2])
    url = "https://www.amazon.com/s?k=" + urllib.parse.quote_plus(keyword)
    r = s.get(url, headers=_headers(ua, s_cua), timeout=25)
    body = r.text
    if _is_blocked(r.status_code, body):
        raise AmazonBlocked(f"Captcha/throttle Amazon (status {r.status_code}, len {len(body)}).")
    return body


def _parse(keyword: str, body: str) -> AmazonDemand:
    asins = [(m.start(), m.group(1)) for m in _ASIN_RE.finditer(body)]
    values: list[int] = []
    for m in _BADGE_RE.finditer(body):
        n = normalize_bought(m.group(1))
        if n is not None:
            values.append(n)
    n_results = len({a for _, a in asins})
    if not values:
        return AmazonDemand(keyword=keyword, n_results=n_results, blocked=False)
    values.sort()
    return AmazonDemand(
        keyword=keyword,
        max_bought=max(values),
        median_bought=values[len(values) // 2],
        n_with_velocity=len(values),
        n_results=n_results,
        blocked=False,
    )


def fetch_demand(keyword: str, session: "creq.Session | None" = None) -> AmazonDemand:
    """Vélocité de vente Amazon agrégée d'un mot-clé (best-effort).

    Sert le cache si frais ; sinon UNE requête. Si captcha/throttle → ``blocked=True``
    sans réessayer (le runner gère le backoff).
    """
    cached = _cache_get(keyword)
    if cached is not None:
        return _parse(keyword, cached)
    try:
        body = _fetch_html(keyword, session)
    except AmazonBlocked:
        return AmazonDemand(keyword=keyword, blocked=True)
    except Exception:
        return AmazonDemand(keyword=keyword, blocked=True)
    _cache_put(keyword, body)
    return _parse(keyword, body)


if __name__ == "__main__":  # test : python3 -m collectors.amazon_demand "yoga mat"
    import sys
    kw = sys.argv[1] if len(sys.argv) > 1 else "yoga mat"
    d = fetch_demand(kw)
    if d.blocked:
        print(f"⚠ « {kw} » : donnée indisponible (captcha/throttle).")
    else:
        print(f"Mot-clé          : {kw}")
        print(f"Vélocité max     : {d.max_bought}")
        print(f"Vélocité médiane : {d.median_bought}")
        print(f"Produits/vélocité: {d.n_with_velocity}/{d.n_results}")
