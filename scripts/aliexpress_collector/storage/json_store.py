"""Stockage JSON : adapté aux petits volumes ou à l'export/inspection humaine.

Charge l'existant en mémoire, déduplique par ``product_id`` et réécrit le
fichier de façon atomique (écriture dans un fichier temporaire puis remplacement)
pour résister à une interruption en cours d'écriture.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from core.exceptions import StorageError
from core.models import Product
from utils.logging_conf import setup_logging

logger = setup_logging()


class JSONStorage:
    """Persistance fichier JSON, indexée en mémoire par identifiant."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._index: dict[str, dict] = {}
        if self._path.exists():
            try:
                existing = json.loads(self._path.read_text(encoding="utf-8") or "[]")
                for item in existing:
                    pid = item.get("product_id")
                    if pid:
                        self._index[pid] = item
            except (json.JSONDecodeError, OSError) as exc:
                raise StorageError(f"Lecture JSON impossible : {exc}") from exc
        logger.debug("JSON prêt : %s (%d existants)", self._path, len(self._index))

    def known_ids(self) -> set[str]:
        return set(self._index)

    def upsert(self, product: Product) -> bool:
        is_new = product.product_id not in self._index
        self._index[product.product_id] = product.to_dict()
        self._flush()
        return is_new

    def count(self) -> int:
        return len(self._index)

    def _flush(self) -> None:
        """Réécriture atomique du fichier complet."""
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        try:
            tmp.write_text(
                json.dumps(list(self._index.values()), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            os.replace(tmp, self._path)
        except OSError as exc:  # pragma: no cover
            raise StorageError(f"Écriture JSON échouée : {exc}") from exc

    def close(self) -> None:
        self._flush()
