"""Enrichissement d'un produit via sa fiche individuelle.

On ne visite la fiche que pour les produits *nouveaux* (voir ``run.py``) afin de
limiter les requêtes. La donnée riche (variantes, description, vendeur) provient
des mêmes payloads JSON internes que le listing — on réutilise donc l'extracteur
tolérant à la structure plutôt que des sélecteurs CSS fragiles.
"""

from __future__ import annotations

from playwright.async_api import BrowserContext

from config.settings import Settings
from core.browser import new_capturing_page
from core.models import Product
from extractors.parser import extract_products
from utils.humanize import human_pause
from utils.logging_conf import setup_logging

logger = setup_logging()


async def enrich_product(
    context: BrowserContext, settings: Settings, product: Product
) -> Product:
    """Ouvre la fiche produit et fusionne les données enrichies.

    En cas d'échec (timeout, blocage), renvoie le produit inchangé : un
    enrichissement raté ne doit jamais faire perdre la donnée de listing.
    """
    if not product.url:
        return product

    page, collector = await new_capturing_page(context, settings)
    try:
        await page.goto(product.url, wait_until="domcontentloaded")
        await human_pause(1.5, 3.5)
        await page.mouse.wheel(0, 1200)
        await human_pause(0.8, 2.0)

        candidates = extract_products(collector.drain())
        match = next((c for c in candidates if c.product_id == product.product_id), None)
        if match is None and candidates:
            match = candidates[0]  # la fiche ne décrit qu'un produit
        if match is not None:
            enriched = product.merge(match)
            logger.debug("Produit %s enrichi", product.product_id)
            return enriched
        logger.debug("Produit %s : pas d'enrichissement JSON", product.product_id)
        return product
    except Exception as exc:
        logger.warning("Enrichissement %s échoué : %s", product.product_id, exc)
        return product
    finally:
        await page.close()
