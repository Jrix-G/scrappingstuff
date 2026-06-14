"""Tests du modèle Product, notamment la fusion listing + fiche."""

import pytest

from core.models import Product


def test_merge_fills_only_empty_fields():
    listing = Product(product_id="1", title="Titre listing", price=9.99)
    detail = Product(
        product_id="1",
        title="Titre détaillé (ignoré)",
        seller="Boutique",
        description="Longue description",
        variants=["Rouge", "Bleu"],
    )
    merged = listing.merge(detail)
    assert merged.title == "Titre listing"          # non écrasé
    assert merged.price == 9.99                      # conservé
    assert merged.seller == "Boutique"              # comblé
    assert merged.description == "Longue description"
    assert merged.variants == ["Rouge", "Bleu"]


def test_merge_rejects_id_mismatch():
    with pytest.raises(ValueError):
        Product(product_id="1").merge(Product(product_id="2"))


def test_to_dict_roundtrip():
    p = Product(product_id="42", title="X", images=["a"])
    data = p.to_dict()
    assert data["product_id"] == "42"
    assert Product(**data).product_id == "42"
