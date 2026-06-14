"""Gestion du navigateur Playwright : contexte furtif et capture réseau.

Deux responsabilités :

* fournir un contexte navigateur réaliste (locale, fuseau, User-Agent, patch
  anti-``webdriver``) pour limiter la détection — usage strictement public et
  à faible cadence ;
* capturer les réponses JSON internes émises par AliExpress, qui contiennent
  la donnée déjà structurée (bien plus stable que le HTML/CSS).
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from playwright.async_api import Browser, BrowserContext, Page, Response, async_playwright

from config.settings import Settings
from utils.logging_conf import setup_logging

logger = setup_logging()

# User-Agent desktop courant : se fondre dans le trafic le plus banal possible.
_DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Script injecté avant tout JS de page : masque les marqueurs d'automatisation.
_STEALTH_INIT = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'languages', {get: () => ['fr-FR', 'fr']});
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
window.chrome = window.chrome || {runtime: {}};
"""

# Fragments d'URL des endpoints internes renvoyant du JSON produit.
_JSON_URL_HINTS = ("search-pc", "/fn/", "mtop.", "recommend", "nav-search")


class JSONResponseCollector:
    """Accumule les corps JSON pertinents vus pendant une navigation.

    On ne lit le corps que pour les réponses « prometteuses » (type ou URL),
    afin de ne pas télécharger inutilement images et bundles JS.
    """

    def __init__(self) -> None:
        self.payloads: list[Any] = []

    async def handle(self, response: Response) -> None:
        """Handler branché sur l'événement ``response`` de la page."""
        try:
            url = response.url
            ctype = response.headers.get("content-type", "")
            looks_json = "json" in ctype or url.endswith(".json")
            hinted = any(h in url for h in _JSON_URL_HINTS)
            if not (looks_json or hinted):
                return
            body = await response.text()
            if not body or body[0] not in "[{":
                return
            self.payloads.append(json.loads(body))
        except Exception:  # corps illisible / non-JSON : on ignore silencieusement
            return

    def drain(self) -> list[Any]:
        """Renvoie les payloads capturés et vide le tampon."""
        items, self.payloads = self.payloads, []
        return items


@asynccontextmanager
async def browser_session(settings: Settings) -> AsyncIterator[tuple[Browser, BrowserContext]]:
    """Ouvre un navigateur+contexte furtif et garantit leur fermeture."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=settings.headless)
        context = await browser.new_context(
            user_agent=_DEFAULT_UA,
            locale=settings.locale,
            timezone_id=settings.timezone,
            viewport={"width": 1366, "height": 768},
            extra_http_headers={"Accept-Language": f"{settings.locale},fr;q=0.9,en;q=0.8"},
        )
        await context.add_init_script(_STEALTH_INIT)
        try:
            yield browser, context
        finally:
            await context.close()
            await browser.close()


async def new_capturing_page(
    context: BrowserContext, settings: Settings
) -> tuple[Page, JSONResponseCollector]:
    """Crée une page neuve avec capture JSON branchée et timeouts configurés."""
    page = await context.new_page()
    collector = JSONResponseCollector()
    page.on("response", collector.handle)
    page.set_default_navigation_timeout(settings.nav_timeout_seconds * 1000)
    page.set_default_timeout(settings.nav_timeout_seconds * 1000)
    return page, collector
