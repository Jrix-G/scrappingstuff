"""Tests de normalisation : c'est là que vit le bruit du monde réel."""

from extractors.normalize import parse_currency, parse_float, parse_int, parse_price


def test_parse_price_french_decimal():
    assert parse_price("0,99€") == 0.99


def test_parse_price_thousands_and_decimal():
    assert parse_price("1.234,56 €") == 1234.56


def test_parse_price_plain_number():
    assert parse_price(3.48) == 3.48


def test_parse_price_range_takes_low_bound():
    assert parse_price("3,48 - 5,90") == 3.48


def test_parse_price_garbage_returns_none():
    assert parse_price("gratuit") is None
    assert parse_price(None) is None


def test_parse_currency():
    assert parse_currency("0,99€") == "EUR"
    assert parse_currency("$12.00") == "USD"
    assert parse_currency("12.00") is None


def test_parse_int_from_sold_label():
    assert parse_int("207 vendus") == 207
    assert parse_int("1\xa0234 commandes") == 1234
    assert parse_int(None) is None


def test_parse_float_rating():
    assert parse_float("4.8") == 4.8
    assert parse_float("note 4,4 / 5") == 4.4
