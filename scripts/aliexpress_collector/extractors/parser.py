"""Extraction tolérante à la structure des produits depuis le JSON AliExpress.

Principe directeur : ne PAS dépendre d'un chemin JSON figé (qui change à chaque
refonte du site). On parcourt récursivement n'importe quel payload et on
reconnaît un produit à sa *forme* — un dictionnaire qui porte un identifiant
produit et au moins un titre ou un prix. Les champs sont ensuite récupérés par
une liste de clés candidates, ce qui absorbe les renommages côté AliExpress.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from core.models import Product

from .normalize import (
    clean_text,
    parse_currency,
    parse_float,
    parse_int,
    parse_price,
)

# Clés candidates par champ (insensible à la casse). Ordre = priorité.
_ID_KEYS = ("productid", "product_id", "itemid", "item_id", "id")
_TITLE_KEYS = ("title", "subject", "displaytitle", "name", "productitle")
_PRICE_KEYS = ("saleprice", "sale_price", "price", "minprice", "formattedprice", "actmin")
_ORIG_PRICE_KEYS = ("originalprice", "original_price", "oriminprice", "maxprice")
_RATING_KEYS = ("starrating", "star_rating", "rating", "averagestar", "evaluation")
_REVIEWS_KEYS = ("reviews", "totalvalidnum", "reviewcount", "comments", "feedback")
_ORDERS_KEYS = ("tradedesc", "trade", "orders", "sales", "volume", "ordercount", "sold")
_SELLER_KEYS = ("storename", "store_name", "sellername", "shopname", "store")
_IMAGE_KEYS = ("imgurl", "image", "imageurl", "img", "mainimage", "picurl")
_URL_KEYS = ("productdetailurl", "producturl", "url", "detailurl", "link", "href")

_ITEM_RE = re.compile(r"/item/(\d{6,})")
_DIGIT_ID_RE = re.compile(r"^\d{6,}$")


def _lower_keys(d: dict[str, Any]) -> dict[str, Any]:
    return {str(k).lower(): v for k, v in d.items()}


def _first(d: dict[str, Any], keys: Iterable[str]) -> Any:
    """Renvoie la première valeur scalaire/list non vide parmi ``keys``.

    Si la valeur est elle-même un dict (ex. ``price: {formattedPrice: ...}``),
    on plonge d'un niveau pour récupérer un scalaire utile.
    """
    for key in keys:
        if key not in d:
            continue
        value = d[key]
        if value in (None, "", [], {}):
            continue
        if isinstance(value, dict):
            nested = _lower_keys(value)
            for sub in (*_PRICE_KEYS, "value", "text", "displayvalue", "string"):
                if sub in nested and nested[sub] not in (None, "", [], {}):
                    return nested[sub]
            continue
        return value
    return None


def looks_like_product(d: dict[str, Any]) -> bool:
    """Vrai si le dict ressemble à un produit (id + titre/prix/url)."""
    low = _lower_keys(d)
    has_id = any(k in low for k in _ID_KEYS) or any(
        isinstance(low.get(k), str) and _ITEM_RE.search(low[k] or "") for k in _URL_KEYS
    )
    has_signal = any(k in low for k in (*_TITLE_KEYS, *_PRICE_KEYS, *_URL_KEYS))
    return bool(has_id and has_signal)


def _extract_id(low: dict[str, Any]) -> str | None:
    """Détermine l'identifiant produit (clé directe ou extrait de l'URL)."""
    raw = _first(low, _ID_KEYS)
    if raw is not None and _DIGIT_ID_RE.match(str(raw).strip()):
        return str(raw).strip()
    for key in _URL_KEYS:
        val = low.get(key)
        if isinstance(val, str):
            m = _ITEM_RE.search(val)
            if m:
                return m.group(1)
    if raw is not None:
        return str(raw).strip()
    return None


def _normalize_url(raw: Any, product_id: str | None) -> str | None:
    """Rend une URL absolue, ou la reconstruit depuis l'identifiant."""
    if isinstance(raw, str) and raw:
        if raw.startswith("//"):
            return "https:" + raw
        if raw.startswith("http"):
            return raw
        if raw.startswith("/"):
            return "https://fr.aliexpress.com" + raw
    if product_id and _DIGIT_ID_RE.match(product_id):
        return f"https://fr.aliexpress.com/item/{product_id}.html"
    return None


def map_item(d: dict[str, Any]) -> Product | None:
    """Convertit un dict « produit » brut en :class:`Product` normalisé."""
    low = _lower_keys(d)
    product_id = _extract_id(low)
    if not product_id:
        return None

    price_raw = _first(low, _PRICE_KEYS)
    images_raw = _first(low, _IMAGE_KEYS)
    images = [images_raw] if isinstance(images_raw, str) else (
        [i for i in images_raw if isinstance(i, str)] if isinstance(images_raw, list) else []
    )

    return Product(
        product_id=product_id,
        title=clean_text(str(_first(low, _TITLE_KEYS)) if _first(low, _TITLE_KEYS) else None),
        price=parse_price(price_raw),
        currency=parse_currency(str(price_raw) if price_raw is not None else None),
        original_price=parse_price(_first(low, _ORIG_PRICE_KEYS)),
        rating=parse_float(_first(low, _RATING_KEYS)),
        reviews_count=parse_int(_first(low, _REVIEWS_KEYS)),
        orders_count=parse_int(_first(low, _ORDERS_KEYS)),
        seller=clean_text(str(_first(low, _SELLER_KEYS)) if _first(low, _SELLER_KEYS) else None),
        url=_normalize_url(_first(low, _URL_KEYS), product_id),
        images=[i if i.startswith("http") else "https:" + i for i in images if isinstance(i, str)],
    )


def iter_product_dicts(node: Any) -> Iterable[dict[str, Any]]:
    """Parcourt récursivement un payload et cède chaque dict ressemblant à un produit."""
    if isinstance(node, dict):
        if looks_like_product(node):
            yield node
        for value in node.values():
            yield from iter_product_dicts(value)
    elif isinstance(node, list):
        for item in node:
            yield from iter_product_dicts(item)


def extract_products(payloads: Iterable[Any]) -> list[Product]:
    """Extrait et déduplique les produits d'une série de payloads JSON.

    La déduplication intra-lot garde la *première* occurrence rencontrée, qui
    est en général la plus complète (carte de listing principale).
    """
    seen: dict[str, Product] = {}
    for payload in payloads:
        for raw in iter_product_dicts(payload):
            product = map_item(raw)
            if product and product.product_id not in seen:
                seen[product.product_id] = product
    return list(seen.values())
