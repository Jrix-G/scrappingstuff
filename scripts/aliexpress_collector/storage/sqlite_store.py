"""Stockage SQLite : produits + historique de prix/ventes (vélocité).

Pourquoi SQLite par défaut : le projet a besoin de comparer un produit dans le
temps (vélocité des ventes/prix = signal d'émergence). Une base relationnelle
légère, sans serveur, donne la dédup (clé primaire), la reprise (lecture des
ids connus) et une table d'historique time-series — impossible proprement avec
un simple dump JSON.

Schéma :
  products(product_id PK, ... , first_seen, last_seen)
  price_history(product_id FK, collected_at, price, orders_count, rating)
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from core.exceptions import StorageError
from core.models import Product
from utils.logging_conf import setup_logging

logger = setup_logging()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    product_id     TEXT PRIMARY KEY,
    title          TEXT,
    price          REAL,
    currency       TEXT,
    original_price REAL,
    rating         REAL,
    reviews_count  INTEGER,
    orders_count   INTEGER,
    seller         TEXT,
    url            TEXT,
    images         TEXT,
    variants       TEXT,
    category       TEXT,
    description    TEXT,
    available      INTEGER,
    source         TEXT,
    first_seen     TEXT,
    last_seen      TEXT
);
CREATE TABLE IF NOT EXISTS price_history (
    product_id   TEXT,
    collected_at TEXT,
    price        REAL,
    orders_count INTEGER,
    rating       REAL,
    PRIMARY KEY (product_id, collected_at)
);
CREATE INDEX IF NOT EXISTS idx_hist_pid ON price_history(product_id);
"""


class SQLiteStorage:
    """Persistance relationnelle avec historique time-series."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._conn = sqlite3.connect(self._path)
            self._conn.executescript(_SCHEMA)
            self._conn.commit()
        except sqlite3.Error as exc:  # pragma: no cover
            raise StorageError(f"Ouverture SQLite impossible : {exc}") from exc
        logger.debug("SQLite prêt : %s", self._path)

    def known_ids(self) -> set[str]:
        rows = self._conn.execute("SELECT product_id FROM products").fetchall()
        return {r[0] for r in rows}

    def upsert(self, product: Product) -> bool:
        """Écrit le produit et ajoute un point d'historique. Renvoie la nouveauté."""
        now = datetime.now(timezone.utc).isoformat()
        data = product.to_dict()
        is_new = self._conn.execute(
            "SELECT 1 FROM products WHERE product_id = ?", (product.product_id,)
        ).fetchone() is None
        try:
            self._conn.execute(
                """
                INSERT INTO products (
                    product_id, title, price, currency, original_price, rating,
                    reviews_count, orders_count, seller, url, images, variants,
                    category, description, available, source, first_seen, last_seen
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(product_id) DO UPDATE SET
                    title=excluded.title, price=excluded.price,
                    currency=excluded.currency, original_price=excluded.original_price,
                    rating=excluded.rating, reviews_count=excluded.reviews_count,
                    orders_count=excluded.orders_count, seller=excluded.seller,
                    url=excluded.url, images=excluded.images, variants=excluded.variants,
                    category=excluded.category, description=excluded.description,
                    available=excluded.available, last_seen=excluded.last_seen
                """,
                (
                    data["product_id"], data["title"], data["price"], data["currency"],
                    data["original_price"], data["rating"], data["reviews_count"],
                    data["orders_count"], data["seller"], data["url"],
                    json.dumps(data["images"], ensure_ascii=False),
                    json.dumps(data["variants"], ensure_ascii=False),
                    data["category"], data["description"],
                    None if data["available"] is None else int(data["available"]),
                    data["source"], now, now,
                ),
            )
            self._conn.execute(
                """
                INSERT OR IGNORE INTO price_history
                    (product_id, collected_at, price, orders_count, rating)
                VALUES (?,?,?,?,?)
                """,
                (data["product_id"], data["collected_at"], data["price"],
                 data["orders_count"], data["rating"]),
            )
            self._conn.commit()
        except sqlite3.Error as exc:
            self._conn.rollback()
            raise StorageError(f"Écriture SQLite échouée : {exc}") from exc
        return is_new

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]

    def close(self) -> None:
        self._conn.close()
