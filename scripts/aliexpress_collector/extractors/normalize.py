"""Normalisation des champs bruts (prix, devise, entiers).

AliExpress renvoie des chaînes localisées hétérogènes : ``"0,99€"``,
``"€3.48"``, ``"207 vendus"``, ``"4.8"``. Ces fonctions tolèrent le bruit et
renvoient toujours un type propre ou ``None``.
"""

from __future__ import annotations

import re

# Symbole/► code devise -> code ISO. Étendre au besoin.
_CURRENCY_MAP = {
    "€": "EUR",
    "$": "USD",
    "£": "GBP",
    "EUR": "EUR",
    "USD": "USD",
    "GBP": "GBP",
}


def parse_currency(text: str | None) -> str | None:
    """Détecte le code devise ISO dans une chaîne de prix."""
    if not text:
        return None
    for token, iso in _CURRENCY_MAP.items():
        if token in text:
            return iso
    return None


def parse_price(text: str | float | int | None) -> float | None:
    """Extrait un float depuis un prix localisé.

    Gère virgule décimale française et séparateurs de milliers. Sur plage de
    prix (``"3,48 - 5,90"``) renvoie la borne basse.
    """
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return float(text)
    cleaned = text.replace("\xa0", " ").strip()
    match = re.search(r"\d[\d.,\s]*", cleaned)
    if not match:
        return None
    num = match.group(0).strip().replace(" ", "")
    if "," in num and "." in num:  # "1.234,56" -> milliers '.' + décimale ','
        num = num.replace(".", "").replace(",", ".")
    elif "," in num:  # "0,99" -> décimale française
        num = num.replace(",", ".")
    try:
        return float(num)
    except ValueError:
        return None


def parse_int(text: str | int | float | None) -> int | None:
    """Extrait le premier entier d'une chaîne (``"207 vendus"`` -> 207)."""
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return int(text)
    digits = re.sub(r"[^\d]", "", str(text))
    return int(digits) if digits else None


def parse_float(text: str | int | float | None) -> float | None:
    """Extrait un flottant simple (note d'évaluation, ``"4.8"`` -> 4.8)."""
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return float(text)
    match = re.search(r"\d+(?:[.,]\d+)?", str(text))
    if not match:
        return None
    return float(match.group(0).replace(",", "."))


def clean_text(text: str | None) -> str | None:
    """Compacte les espaces et retire les blancs superflus."""
    if not text:
        return None
    collapsed = re.sub(r"\s+", " ", text).strip()
    return collapsed or None
