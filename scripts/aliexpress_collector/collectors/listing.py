"""Collecte des produits d'une page de listing AliExpress.

Stratégie en deux temps, du plus stable au moins stable :

1. **JSON interne** : on charge la page, on scrolle pour déclencher les appels
   réseau, et on extrait les produits des payloads JSON capturés. C'est la voie
   privilégiée (donnée structurée, peu sensible aux refontes CSS).
2. **Repli HTML** : si aucun JSON exploitable, on récupère au minimum les liens
   ``/item/<id>`` présents dans le DOM pour ne pas repartir les mains vides.
"""

from __future__ import annotations

from playwright.async_api import BrowserContext

from config.settings import Settings
from core.browser import new_capturing_page
from core.exceptions import NavigationError
from core.models import Product
from extractors.parser import extract_products
from utils.humanize import human_pause
from utils.logging_conf import setup_logging

logger = setup_logging()


async def collect_listing(context: BrowserContext, settings: Settings) -> list[Product]:
    """Charge ``settings.target_url`` et renvoie les produits trouvés."""
    page, collector = await new_capturing_page(context, settings)
    try:
        logger.info("Listing : ouverture de %s", settings.target_url)
        try:
            await page.goto(settings.target_url, wait_until="domcontentloaded")
        except Exception as exc:
            raise NavigationError(f"Chargement listing impossible : {exc}") from exc

        await human_pause(2.0, 4.0)
        for step in range(settings.listing_scroll_steps):
            await page.mouse.wheel(0, 1400)
            await human_pause(0.8, 2.0)
            logger.debug("Listing scroll %d/%d", step + 1, settings.listing_scroll_steps)

        products = extract_products(collector.drain())
        if products:
            logger.info("Listing : %d produits via JSON interne", len(products))
            return products

        logger.warning("Aucun JSON exploitable, repli sur extraction des liens DOM")
        return await _fallback_dom_links(page)
    finally:
        await page.close()


async def _fallback_dom_links(page) -> list[Product]:
    """Repli minimal : reconstruit des produits depuis les liens ``/item/``."""
    anchors = await page.query_selector_all("a[href*='/item/']")
    seen: dict[str, Product] = {}
    for anchor in anchors:
        href = await anchor.get_attribute("href") or ""
        title = await anchor.get_attribute("title")
        import re

        match = re.search(r"/item/(\d{6,})", href)
        if not match:
            continue
        pid = match.group(1)
        if pid in seen:
            continue
        url = href if href.startswith("http") else "https:" + href if href.startswith("//") else href
        seen[pid] = Product(product_id=pid, title=title, url=url)
    logger.info("Repli DOM : %d produits (données minimales)", len(seen))
    return list(seen.values())
