"""Tests des backends de stockage : dédup, reprise, historique."""

from core.models import Product
from storage.json_store import JSONStorage
from storage.sqlite_store import SQLiteStorage


def _sample(pid: str = "123456789", price: float = 9.99) -> Product:
    return Product(product_id=pid, title="Demo", price=price, currency="EUR")


def test_sqlite_upsert_dedup_and_resume(tmp_path):
    db = tmp_path / "test.db"
    store = SQLiteStorage(db)
    assert store.upsert(_sample()) is True       # nouveau
    assert store.upsert(_sample()) is False      # déjà connu -> pas nouveau
    assert store.count() == 1
    store.close()

    # Reprise : un nouveau handle voit l'id déjà stocké.
    store2 = SQLiteStorage(db)
    assert "123456789" in store2.known_ids()
    store2.close()


def test_sqlite_price_history_accumulates(tmp_path):
    store = SQLiteStorage(tmp_path / "h.db")
    p1 = Product(product_id="999", price=10.0, collected_at="2026-01-01T00:00:00+00:00")
    p2 = Product(product_id="999", price=12.0, collected_at="2026-02-01T00:00:00+00:00")
    store.upsert(p1)
    store.upsert(p2)
    rows = store._conn.execute(
        "SELECT price FROM price_history WHERE product_id='999' ORDER BY collected_at"
    ).fetchall()
    assert [r[0] for r in rows] == [10.0, 12.0]
    store.close()


def test_json_store_dedup_and_persistence(tmp_path):
    path = tmp_path / "products.json"
    store = JSONStorage(path)
    assert store.upsert(_sample()) is True
    assert store.upsert(_sample(price=8.0)) is False  # même id -> maj, pas nouveau
    store.close()

    store2 = JSONStorage(path)
    assert store2.count() == 1
    assert "123456789" in store2.known_ids()
    store2.close()
