"""Saisonnalité — « est-ce le bon MOMENT de l'année pour ce produit ? ».

Certains produits sont structurellement saisonniers : les pistolets à eau se
vendent en été, les guirlandes en décembre. Un excellent produit poussé à
contre-saison est un mauvais investissement. Ce module estime, à partir du nom et
de la catégorie d'un produit, un **multiplicateur de demande pour le mois courant**.

Approche : une table de profils saisonniers (12 multiplicateurs mensuels, un par
thème) + un appariement par mots-clés sur le nom/catégorie du produit. La courbe est
normalisée pour que la moyenne annuelle = 1,0 : un multiplicateur > 1 signifie
« au-dessus de la moyenne annuelle ce mois-ci », < 1 « hors saison ».

C'est une heuristique transparente. Elle pourra être remplacée/affinée par des
courbes empiriques Google Trends (12 mois) une fois ce collecteur branché.
"""

from __future__ import annotations

from dataclasses import dataclass

# Profils saisonniers : 12 valeurs (janv→déc), centrées autour de 1,0 après
# normalisation. Pic = 1,5 environ, creux = 0,5 environ.
# Chaque profil est associé à des mots-clés (minuscules, anglais — CJ est en EN).
_SEASON_PROFILES: dict[str, tuple[list[str], list[float]]] = {
    "summer_water": (
        ["water gun", "pool", "swim", "beach", "inflatable", "snorkel", "sunscreen",
         "cooling", "fan", "popsicle", "water balloon", "paddle"],
        [0.4, 0.4, 0.6, 0.9, 1.3, 1.6, 1.7, 1.6, 1.1, 0.7, 0.4, 0.4],
    ),
    "winter_warm": (
        ["heater", "scarf", "glove", "thermal", "blanket", "beanie", "warm",
         "snow", "ski", "earmuff"],
        [1.5, 1.3, 1.0, 0.7, 0.5, 0.4, 0.4, 0.4, 0.6, 1.0, 1.4, 1.6],
    ),
    "christmas_gift": (
        ["christmas", "xmas", "santa", "ornament", "advent", "garland", "gift box",
         "stocking", "wreath"],
        [0.5, 0.4, 0.4, 0.4, 0.4, 0.4, 0.5, 0.6, 0.9, 1.3, 1.8, 2.0],
    ),
    "halloween": (
        ["halloween", "costume", "pumpkin", "skeleton", "spooky", "scary mask"],
        [0.5, 0.5, 0.5, 0.5, 0.5, 0.6, 0.8, 1.2, 1.8, 2.2, 0.6, 0.5],
    ),
    "valentine": (
        ["valentine", "rose", "couple gift", "love heart", "romantic"],
        [1.4, 1.9, 1.1, 0.9, 0.9, 0.9, 0.8, 0.8, 0.8, 0.8, 0.9, 1.0],
    ),
    "back_to_school": (
        ["backpack", "school", "stationery", "pencil case", "notebook", "student",
         "lunch box", "desk"],
        [0.8, 0.8, 0.8, 0.8, 0.8, 0.9, 1.3, 1.8, 1.4, 0.9, 0.8, 0.8],
    ),
    "new_year_fitness": (
        ["fitness", "yoga", "gym", "workout", "resistance band", "dumbbell",
         "training", "weight loss", "diet"],
        [1.7, 1.3, 1.1, 1.0, 0.9, 0.8, 0.8, 0.8, 0.9, 0.9, 0.8, 0.9],
    ),
    "spring_garden": (
        ["garden", "planter", "seed", "flower pot", "bbq", "grill", "patio",
         "lawn", "picnic", "watering"],
        [0.6, 0.7, 1.1, 1.5, 1.6, 1.4, 1.2, 1.0, 0.8, 0.7, 0.6, 0.6],
    ),
}


@dataclass(slots=True)
class SeasonalityResult:
    """Résultat saisonnier d'un produit pour un mois donné."""

    multiplier: float          # multiplicateur de demande du mois courant (≈0.4–2.0)
    profile: str | None        # profil saisonnier apparié (ou None = non saisonnier)
    peak_month: int | None     # mois de pic (1–12) du profil apparié
    label: str                 # phrase lisible

    def as_dict(self) -> dict:
        return {
            "multiplier": round(self.multiplier, 3),
            "profile": self.profile,
            "peak_month": self.peak_month,
            "label": self.label,
        }


def _normalize(curve: list[float]) -> list[float]:
    """Recentre la courbe pour une moyenne annuelle = 1,0."""
    mean = sum(curve) / len(curve)
    if mean <= 0:
        return [1.0] * 12
    return [v / mean for v in curve]


_MONTH_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
             "août", "septembre", "octobre", "novembre", "décembre"]


def seasonality_for(text: str, month: int) -> SeasonalityResult:
    """Estime le multiplicateur saisonnier d'un produit pour ``month`` (1–12).

    ``text`` : nom + catégorie concaténés. L'appariement prend le profil dont un
    mot-clé apparaît ; en cas de multiples, celui au multiplicateur courant le plus
    fort (le signal saisonnier le plus marqué l'emporte).
    """
    if not 1 <= month <= 12:
        raise ValueError("month doit être dans 1..12")
    haystack = (text or "").lower()
    idx = month - 1

    best: SeasonalityResult | None = None
    for profile, (keywords, curve) in _SEASON_PROFILES.items():
        if not any(kw in haystack for kw in keywords):
            continue
        norm = _normalize(curve)
        mult = norm[idx]
        peak = max(range(12), key=lambda i: norm[i]) + 1
        if best is None or mult > best.multiplier:
            in_season = mult >= 1.0
            label = (
                f"{profile} : {'en saison' if in_season else 'hors saison'} en "
                f"{_MONTH_FR[idx]} (×{mult:.2f}, pic en {_MONTH_FR[peak-1]})"
            )
            best = SeasonalityResult(multiplier=mult, profile=profile,
                                     peak_month=peak, label=label)

    if best is None:
        return SeasonalityResult(
            multiplier=1.0, profile=None, peak_month=None,
            label="non saisonnier (demande stable sur l'année)",
        )
    return best
