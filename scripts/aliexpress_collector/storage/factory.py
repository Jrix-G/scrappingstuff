"""Sélection du backend de stockage selon la configuration.

``auto`` privilégie SQLite : le projet vise un historique temporel (vélocité),
ce que JSON ne sait pas faire proprement. JSON reste disponible pour les petits
jeux de données ou l'inspection manuelle.
"""

from __future__ import annotations

from config.settings import Settings
from storage.base import Storage
from storage.json_store import JSONStorage
from storage.sqlite_store import SQLiteStorage
from utils.logging_conf import setup_logging

logger = setup_logging()


def build_storage(settings: Settings) -> Storage:
    """Instancie le backend de stockage adapté aux réglages."""
    backend = settings.storage_backend
    if backend == "json":
        logger.info("Stockage : JSON (%s)", settings.json_export_path)
        return JSONStorage(settings.json_export_path)
    # "auto" comme "sqlite" -> SQLite, pour l'historique time-series.
    logger.info("Stockage : SQLite (%s)", settings.storage_path)
    return SQLiteStorage(settings.storage_path)
