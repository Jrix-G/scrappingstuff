"""Chargement et validation de la configuration centrale.

La configuration est lue depuis un fichier YAML puis surchargée, champ par
champ, par les variables d'environnement préfixées ``AEC_`` (ex.
``AEC_TARGET_URL``). Toute la configuration de l'application transite par
l'unique dataclass :class:`Settings`, ce qui évite les constantes magiques
dispersées dans le code.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

import yaml

ENV_PREFIX = "AEC_"


@dataclass(slots=True)
class Settings:
    """Configuration typée et immuable de l'application."""

    target_url: str
    max_products: int = 40
    enrich_product_pages: bool = True

    locale: str = "fr-FR"
    timezone: str = "Europe/Paris"
    headless: bool = False
    min_delay_seconds: float = 5.0
    max_delay_seconds: float = 11.0
    listing_scroll_steps: int = 8
    nav_timeout_seconds: int = 45

    storage_backend: str = "auto"  # auto | sqlite | json
    storage_path: str = "data/aliexpress.db"
    json_export_path: str = "data/products.json"

    log_level: str = "INFO"
    log_file: str = "logs/collector.log"

    # -- construction --------------------------------------------------------
    @classmethod
    def load(cls, config_path: str | Path | None = None) -> "Settings":
        """Construit les réglages depuis le YAML + surcharges d'environnement.

        Args:
            config_path: chemin du fichier YAML. Par défaut ``config/config.yaml``
                situé à côté de ce module.

        Returns:
            Une instance validée de :class:`Settings`.
        """
        path = Path(config_path) if config_path else Path(__file__).with_name("config.yaml")
        raw: dict[str, Any] = {}
        if path.exists():
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

        type_by_name = {f.name: f.type for f in fields(cls)}
        for name in type_by_name:
            env_val = os.environ.get(f"{ENV_PREFIX}{name.upper()}")
            if env_val is not None:
                raw[name] = env_val

        coerced = {
            name: cls._coerce(type_by_name[name], value)
            for name, value in raw.items()
            if name in type_by_name
        }
        settings = cls(**coerced)  # type: ignore[arg-type]
        settings.validate()
        return settings

    @staticmethod
    def _coerce(declared_type: Any, value: Any) -> Any:
        """Convertit une valeur (souvent str venant de l'env) vers son type."""
        if value is None:
            return None
        type_str = str(declared_type)
        if "bool" in type_str:
            if isinstance(value, bool):
                return value
            return str(value).strip().lower() in {"1", "true", "yes", "on"}
        if "int" in type_str:
            return int(value)
        if "float" in type_str:
            return float(value)
        return str(value)

    def validate(self) -> None:
        """Vérifie la cohérence des réglages, lève ``ValueError`` sinon."""
        if not self.target_url or not self.target_url.startswith("http"):
            raise ValueError("target_url doit être une URL http(s) valide.")
        if self.min_delay_seconds < 0 or self.max_delay_seconds < self.min_delay_seconds:
            raise ValueError("Intervalle de délai invalide (min <= max, >= 0).")
        if self.storage_backend not in {"auto", "sqlite", "json"}:
            raise ValueError("storage_backend doit être auto, sqlite ou json.")
