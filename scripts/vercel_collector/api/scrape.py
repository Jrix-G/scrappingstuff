"""Fonction Vercel — tourne sur LEURS serveurs, avec LEURS IPs.

AliExpress voit une IP Vercel (New York, Paris, Tokyo...) jamais la tienne.
Cette fonction reçoit un mot-clé + numéro de page, scrape AliExpress,
et renvoie les produits en JSON.
"""

from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import re
import urllib.request

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    # Pas de gzip : on veut du texte brut pour éviter les problèmes de décompression
    "Accept-Encoding": "identity",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Cache-Control": "no-cache",
}


def fetch_products(keyword: str, page: int) -> list[dict]:
    """Charge une page de résultats AliExpress et extrait les produits."""
    slug = keyword.strip().replace(" ", "-")
    url = f"https://fr.aliexpress.com/w/wholesale-{slug}.html?page={page}&SortType=total_transx_desc"

    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
            encoding = resp.headers.get("Content-Encoding", "")
            # Décompression manuelle si nécessaire
            if encoding == "gzip":
                import gzip as _gzip
                raw = _gzip.decompress(raw)
            elif encoding == "br":
                # brotli non dispo en stdlib, on renvoie erreur explicite
                return [{"error": "brotli encoding non supporté — enlever br de Accept-Encoding"}]
            try:
                html = raw.decode("utf-8")
            except UnicodeDecodeError:
                html = raw.decode("latin-1")
    except Exception as exc:
        return [{"error": str(exc), "url": url}]

    return _extract(html)


def _extract(html: str) -> list[dict]:
    """Tente plusieurs stratégies d'extraction, du plus stable au moins stable."""

    # Stratégie 1 : window.runParams (données serveur embeddées dans le HTML)
    products = _try_run_params(html)
    if products:
        return products

    # Stratégie 2 : __NEXT_DATA__ (apps Next.js)
    products = _try_next_data(html)
    if products:
        return products

    # Stratégie 3 : blocs JSON inline (fallback générique)
    products = _try_inline_json(html)
    if products:
        return products

    return []


def _try_run_params(html: str) -> list[dict]:
    match = re.search(
        r"window\.runParams\s*=\s*(\{.+?\});\s*(?:window|</script>)",
        html,
        re.DOTALL,
    )
    if not match:
        return []
    try:
        data = json.loads(match.group(1))
        return _walk_for_products(data)
    except (json.JSONDecodeError, ValueError):
        return []


def _try_next_data(html: str) -> list[dict]:
    match = re.search(
        r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.+?)</script>',
        html,
        re.DOTALL,
    )
    if not match:
        return []
    try:
        data = json.loads(match.group(1))
        return _walk_for_products(data)
    except (json.JSONDecodeError, ValueError):
        return []


def _try_inline_json(html: str) -> list[dict]:
    """Cherche des blocs JSON contenant des listes de produits."""
    candidates = re.findall(r'(\{["\'](?:productId|itemId)["\'].+?\})', html, re.DOTALL)
    products = []
    seen = set()
    for blob in candidates:
        try:
            obj = json.loads(blob)
            pid = str(obj.get("productId") or obj.get("itemId") or "")
            if pid and pid not in seen:
                seen.add(pid)
                products.append(_normalize(obj))
        except (json.JSONDecodeError, ValueError):
            continue
    return products


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------

_ID_KEYS = ("productId", "itemId", "product_id", "id")
_TITLE_KEYS = ("title", "subject", "productTitle", "name")
_PRICE_KEYS = ("salePrice", "price", "minPrice", "formattedPrice")
_ORDERS_KEYS = ("tradeDesc", "trade", "orders", "sold", "volume")
_RATING_KEYS = ("starRating", "rating", "evaluation", "averageStar")
_IMG_KEYS = ("imgUrl", "image", "imageUrl", "mainImage", "picUrl")
_URL_KEYS = ("productDetailUrl", "url", "detailUrl", "productUrl")

_ITEM_RE = re.compile(r"/item/(\d{6,})")
_PRICE_RE = re.compile(r"\d[\d.,]*")


def _first(d: dict, keys: tuple) -> str | None:
    for k in keys:
        v = d.get(k)
        if v not in (None, "", [], {}):
            if isinstance(v, dict):
                for sub in ("formattedPrice", "value", "text", "string"):
                    if v.get(sub):
                        return str(v[sub])
                continue
            return str(v)
    return None


def _parse_price(raw: str | None) -> float | None:
    if not raw:
        return None
    m = _PRICE_RE.search(raw)
    if not m:
        return None
    num = m.group(0).replace(" ", "")
    if "," in num and "." in num:
        num = num.replace(".", "").replace(",", ".")
    elif "," in num:
        num = num.replace(",", ".")
    try:
        return float(num)
    except ValueError:
        return None


def _parse_int(raw: str | None) -> int | None:
    if not raw:
        return None
    digits = re.sub(r"[^\d]", "", raw)
    return int(digits) if digits else None


def _parse_float(raw: str | None) -> float | None:
    if not raw:
        return None
    m = re.search(r"\d+(?:[.,]\d+)?", raw)
    return float(m.group(0).replace(",", ".")) if m else None


def _normalize(d: dict) -> dict:
    pid = _first(d, _ID_KEYS)
    url_raw = _first(d, _URL_KEYS)
    if not pid:
        m = _ITEM_RE.search(url_raw or "")
        pid = m.group(1) if m else None
    if not pid:
        return {}

    url = url_raw or f"/item/{pid}.html"
    if url.startswith("//"):
        url = "https:" + url
    elif url.startswith("/"):
        url = "https://fr.aliexpress.com" + url

    img = _first(d, _IMG_KEYS)
    if img and img.startswith("//"):
        img = "https:" + img

    return {
        "product_id": pid,
        "title": _first(d, _TITLE_KEYS),
        "price": _parse_price(_first(d, _PRICE_KEYS)),
        "orders_count": _parse_int(_first(d, _ORDERS_KEYS)),
        "rating": _parse_float(_first(d, _RATING_KEYS)),
        "image": img,
        "url": url,
    }


def _looks_like_product(d: dict) -> bool:
    has_id = any(k in d for k in _ID_KEYS)
    has_url = any(
        isinstance(d.get(k), str) and _ITEM_RE.search(d[k])
        for k in _URL_KEYS
    )
    has_signal = any(k in d for k in (*_TITLE_KEYS, *_PRICE_KEYS))
    return (has_id or has_url) and has_signal


def _walk_for_products(node, _seen=None) -> list[dict]:
    """Parcourt récursivement le JSON et renvoie les produits normalisés."""
    if _seen is None:
        _seen = set()
    results = []
    if isinstance(node, dict):
        if _looks_like_product(node):
            norm = _normalize(node)
            pid = norm.get("product_id")
            if pid and pid not in _seen:
                _seen.add(pid)
                results.append(norm)
        for v in node.values():
            results.extend(_walk_for_products(v, _seen))
    elif isinstance(node, list):
        for item in node:
            results.extend(_walk_for_products(item, _seen))
    return results


# ---------------------------------------------------------------------------
# Handler Vercel
# ---------------------------------------------------------------------------

class handler(BaseHTTPRequestHandler):
    """Point d'entrée HTTP de la fonction Vercel."""

    def do_GET(self):
        params = parse_qs(urlparse(self.path).query)
        keyword = params.get("keyword", [""])[0].strip()
        page = int(params.get("page", ["1"])[0])
        debug = params.get("debug", ["0"])[0] == "1"

        if not keyword:
            self._respond(400, {"error": "keyword manquant"})
            return

        if debug:
            # Renvoie le HTML brut (premiers 3000 chars) pour diagnostiquer
            slug = keyword.replace(" ", "-")
            url = f"https://fr.aliexpress.com/w/wholesale-{slug}.html?page={page}"
            req = urllib.request.Request(url, headers=HEADERS)
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    raw = resp.read()
                    html = raw.decode("utf-8", errors="replace")
                has_runparams = "window.runParams" in html
                has_nextdata = "__NEXT_DATA__" in html
                has_items = "/item/" in html
                self._respond(200, {
                    "url_fetched": url,
                    "status": "ok",
                    "html_length": len(html),
                    "has_runParams": has_runparams,
                    "has_NEXT_DATA": has_nextdata,
                    "has_item_links": has_items,
                    "html_preview": html[:3000],
                })
            except Exception as exc:
                self._respond(200, {"error": str(exc)})
            return

        products = fetch_products(keyword, page)
        self._respond(200, {"keyword": keyword, "page": page, "products": products})

    def _respond(self, status: int, body: dict):
        payload = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_):
        pass  # silence les logs HTTP de BaseHTTPRequestHandler
