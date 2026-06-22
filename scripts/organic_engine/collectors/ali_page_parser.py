"""Parseur d'extraction-MAX pour une page de recherche AliExpress.

Le HTML `/af/<kw>.html` (ou `/w/wholesale-<kw>.html`) embarque le blob
``_init_data_`` où ``itemList.content[]`` liste **des dizaines de produits**,
chacun avec : ``productId``, ``title.displayTitle``, ``prices.salePrice.cent``,
``evaluation.starRating`` et ``trade.tradeDesc`` (le compteur de ventes
« + 10 000 vendus »). Le collecteur naïf ne sortait qu'UN résumé par page : ici
on moissonne TOUT — une requête nourrit des dizaines de lignes.

Aucune dépendance externe : re + json + stdlib uniquement. Conçu pour être
validé hors-ligne sur ``.aliexpress_cache/*.html`` sans aucune requête live.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

# Marqueurs de la page anti-bot AliExpress (« x5/baxia ») : page < 5 ko, captcha.
_PUNISH_MARKERS = (
    "_____tmd_____/punish",
    '"action":"captcha"',
    "x5secdata",
    "slidecaptcha",
    "aecaptcha",
)

# Échelle « k/万 » éventuelle dans tradeDesc (ex. « 1.2k sold », « 5万 »).
_TRADE_RE = re.compile(r'"trade":\{"tradeDesc":"([^"]*)"')
_PRODUCTID_RE = re.compile(r'"productId":"(\d+)"')
_TITLE_RE = re.compile(r'"displayTitle":"((?:[^"\\]|\\.)*)"')
_CENT_RE = re.compile(r'"salePrice":\{[^}]*?"cent":(\d+)')
_STAR_RE = re.compile(r'"starRating":([\d.]+)')
# Compteur de ventes brut → nombre. Gère « + 10 000 vendus », « 1 234 sold »,
# « 1.2k+ sold », « 5万+ », espaces fines/insécables.
_DIGITS_RE = re.compile(r"\d[\d\s  .,]*\d|\d")


@dataclass(slots=True)
class AliProduct:
    product_id: str
    title: str
    sold: int | None          # unités vendues (None si pas de compteur lisible)
    price_cents: int | None   # prix de vente en centimes (devise de la page)
    star_rating: float | None


@dataclass(slots=True)
class AliPage:
    keyword: str | None       # mot-clé/recherche écho de la page (auto-détecté)
    total_results: int | None # nb total d'annonces déclaré par AliExpress
    products: list[AliProduct]
    blocked: bool = False

    @property
    def sold_values(self) -> list[int]:
        return [p.sold for p in self.products if p.sold]


def is_blocked(html: str) -> bool:
    """Page punish/captcha ou tronquée → True (donnée indisponible ≠ zéro)."""
    return (not html) or len(html) < 5000 or any(m in html for m in _PUNISH_MARKERS)


def parse_sold(desc: str | None) -> int | None:
    """« + 10 000 vendus » → 10000 ; « 1.2k sold » → 1200 ; « 5万 » → 50000."""
    if not desc:
        return None
    low = desc.lower()
    m = _DIGITS_RE.search(low)
    if not m:
        return None
    raw = m.group(0)
    digits = re.sub(r"[^\d.]", "", raw)
    if not digits:
        return None
    # Cas décimal d'échelle : « 1.2k » / « 1.2万 »
    if "." in digits and ("k" in low or "万" in low or "mil" in low):
        try:
            base = float(digits)
        except ValueError:
            return None
    else:
        digits = digits.replace(".", "")
        if not digits:
            return None
        base = float(digits)
    if "万" in desc:
        base *= 10000
    elif re.search(r"\d\s*k\b", low):
        base *= 1000
    return int(base)


def _detect_keyword(html: str) -> str | None:
    m = re.search(r'<title>([^<|]+?)\s*[-|]', html)
    if m:
        kw = m.group(1).strip()
        if kw and "aliexpress" not in kw.lower():
            return kw
    m = re.search(r'"query":"([^"]*)"', html) or re.search(r'"keyword":"([^"]*)"', html)
    return m.group(1) if m else None


def _detect_total(html: str) -> int | None:
    m = re.search(r'"totalResults":"?(\d+)', html) or re.search(r'"resultCount":"?(\d+)', html)
    return int(m.group(1)) if m else None


def parse_page(html: str, keyword: str | None = None) -> AliPage:
    """Extrait TOUS les produits d'une page de recherche AliExpress.

    `keyword` force l'attribution ; sinon on auto-détecte depuis la page.
    """
    if is_blocked(html):
        return AliPage(keyword=keyword, total_results=None, products=[], blocked=True)

    kw = keyword or _detect_keyword(html)
    total = _detect_total(html)
    products: list[AliProduct] = []
    seen: set[str] = set()

    # On itère par productId : chaque produit ouvre un objet item. On lit ses
    # champs dans une fenêtre bornée (l'objet item fait < ~4 ko).
    for m in _PRODUCTID_RE.finditer(html):
        pid = m.group(1)
        if pid in seen:
            continue
        chunk = html[m.start():m.start() + 4000]
        title_m = _TITLE_RE.search(chunk)
        if not title_m:
            continue  # pas un vrai objet produit (réf. croisée)
        seen.add(pid)
        title = _unescape(title_m.group(1))
        sold_m = _TRADE_RE.search(chunk)
        cent_m = _CENT_RE.search(chunk)
        star_m = _STAR_RE.search(chunk)
        products.append(AliProduct(
            product_id=pid,
            title=title,
            sold=parse_sold(sold_m.group(1)) if sold_m else None,
            price_cents=int(cent_m.group(1)) if cent_m else None,
            star_rating=float(star_m.group(1)) if star_m else None,
        ))

    return AliPage(keyword=kw, total_results=total, products=products, blocked=False)


def _unescape(s: str) -> str:
    try:
        return json.loads(f'"{s}"')
    except Exception:
        return s.replace('\\"', '"').replace("\\u00a0", " ").replace("\\/", "/")


# ─── Agrégat compatible avec record_aliexpress / sales_snapshots ─────────────

@dataclass(slots=True)
class AliExpressDemand:
    """Même forme que collectors.aliexpress_orders.AliExpressDemand, enrichie."""
    keyword: str
    max_sold: int | None = None
    median_sold: int | None = None
    listings_with_sales: int = 0
    n_results: int | None = None      # total d'annonces déclaré par la page
    blocked: bool = False

    def as_dict(self) -> dict:
        return {
            "keyword": self.keyword, "maxSold": self.max_sold,
            "medianSold": self.median_sold,
            "listingsWithSales": self.listings_with_sales,
            "nResults": self.n_results, "blocked": self.blocked,
        }


def page_to_demand(page: AliPage, keyword: str | None = None) -> AliExpressDemand:
    """Réduit une page parsée en l'agrégat ventes attendu par la persistance."""
    kw = keyword or page.keyword or ""
    if page.blocked:
        return AliExpressDemand(keyword=kw, blocked=True)
    sv = sorted(page.sold_values)
    if not sv:
        return AliExpressDemand(keyword=kw, n_results=page.total_results, blocked=False)
    return AliExpressDemand(
        keyword=kw, max_sold=sv[-1], median_sold=sv[len(sv) // 2],
        listings_with_sales=len(sv), n_results=page.total_results, blocked=False,
    )


if __name__ == "__main__":  # validation hors-ligne sur le cache
    import sys
    from pathlib import Path
    cache = Path(__file__).resolve().parent.parent / ".aliexpress_cache"
    files = sorted(cache.glob("*.html"))
    if len(sys.argv) > 1:
        files = [Path(sys.argv[1])]
    tot_prod = tot_sold = 0
    for f in files:
        html = f.read_text(encoding="utf-8", errors="replace")
        page = parse_page(html)
        if page.blocked:
            print(f"{f.name}: BLOQUÉ")
            continue
        d = page_to_demand(page)
        ws = len(page.sold_values)
        tot_prod += len(page.products)
        tot_sold += ws
        print(f"{f.name}: kw={str(page.keyword)[:22]:22} "
              f"prod={len(page.products):3} sold={ws:3} "
              f"max={d.max_sold} med={d.median_sold} total={page.total_results}")
    print(f"\n== {len(files)} pages · {tot_prod} produits · {tot_sold} avec compteur ventes ==")
