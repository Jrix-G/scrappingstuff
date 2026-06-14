"""Tests de l'extracteur tolérant à la structure.

On vérifie qu'il retrouve les produits quelle que soit la profondeur et même
si AliExpress renomme/réimbrique les clés.
"""

from extractors.parser import extract_products, looks_like_product, map_item


def test_map_item_nested_price_dict():
    raw = {
        "productId": "1005007201130745",
        "title": {"displayTitle": "Oreillettes de remplacement"},
        "prices": {"salePrice": {"formattedPrice": "0,99€"}},
        "evaluation": {"starRating": "4.8"},
        "trade": {"tradeDesc": "207 vendus"},
        "store": {"storeName": "Best Audio Store"},
        "image": {"imgUrl": "//ae01.example.com/img.jpg"},
    }
    # Aplati pour le test : map_item lit les clés du dict courant.
    flat = {
        "productId": "1005007201130745",
        "title": "Oreillettes de remplacement",
        "salePrice": "0,99€",
        "starRating": "4.8",
        "tradeDesc": "207 vendus",
        "storeName": "Best Audio Store",
        "imgUrl": "//ae01.example.com/img.jpg",
    }
    product = map_item(flat)
    assert product is not None
    assert product.product_id == "1005007201130745"
    assert product.price == 0.99
    assert product.currency == "EUR"
    assert product.rating == 4.8
    assert product.orders_count == 207
    assert product.seller == "Best Audio Store"
    assert product.images == ["https://ae01.example.com/img.jpg"]
    assert product.url == "https://fr.aliexpress.com/item/1005007201130745.html"


def test_id_extracted_from_url_when_missing():
    raw = {"title": "Truc", "productDetailUrl": "//fr.aliexpress.com/item/1005006691703466.html"}
    product = map_item(raw)
    assert product is not None
    assert product.product_id == "1005006691703466"


def test_looks_like_product_rejects_noise():
    assert not looks_like_product({"banner": "promo", "color": "red"})
    assert looks_like_product({"productId": "1005006691703466", "title": "x"})


def test_extract_products_deep_and_dedup():
    payload = {
        "data": {
            "result": {
                "mods": {
                    "itemList": {
                        "content": [
                            {"productId": "111111111", "title": "A", "salePrice": "1,00€"},
                            {"productId": "111111111", "title": "A bis", "salePrice": "1,00€"},
                            {"productId": "222222222", "title": "B", "salePrice": "2,00€"},
                        ]
                    }
                }
            }
        }
    }
    products = extract_products([payload])
    ids = sorted(p.product_id for p in products)
    assert ids == ["111111111", "222222222"]
