"""Point d'entrée du collecteur AliExpress.

Pipeline :
    config -> stockage (reprise) -> navigateur furtif -> listing (JSON interne)
    -> dédup -> enrichissement des nouveaux -> stockage + historique.

Tolérant aux interruptions : chaque produit est persisté dès qu'il est traité,
et les identifiants déjà connus sont sautés au démarrage suivant (reprise).

Usage :
    python run.py                       # utilise config/config.yaml
    python run.py --config autre.yaml
    AEC_TARGET_URL="https://fr.aliexpress.com/w/wholesale-montre.html" python run.py
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from collectors.listing import collect_listing
from collectors.product import enrich_product
from config.settings import Settings
from core.browser import browser_session
from storage.factory import build_storage
from utils.humanize import human_pause
from utils.logging_conf import setup_logging


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collecteur AliExpress robuste.")
    parser.add_argument("--config", default=None, help="Chemin du fichier YAML de config.")
    return parser.parse_args(argv)


async def run(settings: Settings) -> int:
    """Exécute une passe de collecte. Renvoie le nombre de nouveaux produits."""
    logger = setup_logging(settings.log_level, settings.log_file)
    storage = build_storage(settings)
    new_count = 0
    try:
        known = storage.known_ids()
        logger.info("Reprise : %d produits déjà connus", len(known))

        async with browser_session(settings) as (_browser, context):
            products = await collect_listing(context, settings)

            # Dédup vs. base + respect du quota max_products.
            fresh = [p for p in products if p.product_id not in known]
            if settings.max_products > 0:
                fresh = fresh[: settings.max_products]
            logger.info("%d produits nouveaux à traiter", len(fresh))

            for idx, product in enumerate(fresh, start=1):
                if settings.enrich_product_pages:
                    product = await enrich_product(context, settings, product)
                is_new = storage.upsert(product)
                new_count += int(is_new)
                logger.info(
                    "[%d/%d] %s | %s | %s%s",
                    idx, len(fresh), product.product_id,
                    (product.title or "—")[:60],
                    product.price if product.price is not None else "?",
                    product.currency or "",
                )
                # Politesse : pause d'apparence humaine entre deux fiches.
                if idx < len(fresh):
                    await human_pause(settings.min_delay_seconds, settings.max_delay_seconds)

        logger.info("Terminé. %d nouveaux / %d en base", new_count, storage.count())
        return new_count
    except KeyboardInterrupt:  # pragma: no cover
        logger.warning("Interruption manuelle : données déjà persistées, reprise possible.")
        return new_count
    finally:
        storage.close()


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    settings = Settings.load(args.config)
    return asyncio.run(run(settings))


if __name__ == "__main__":
    raise SystemExit(0 if main() >= 0 else 1)
