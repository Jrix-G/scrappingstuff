"""Validation du modèle de vendabilité et de la saisonnalité."""

from __future__ import annotations

from scoring.sellability import (
    DEFAULT_SELLABILITY,
    estimated_retail,
    score_sellability,
)
from signals.seasonality import seasonality_for


# --- Marge / retail --------------------------------------------------------

def test_markup_decreases_with_cost():
    """Le multiple de markup décroît quand le coût monte (ancrage de prix)."""
    m_cheap = estimated_retail(3) / 3
    m_mid = estimated_retail(20) / 20
    m_exp = estimated_retail(100) / 100
    assert m_cheap > m_mid > m_exp


def test_thin_margin_is_unsellable():
    """Un produit dont la marge ne couvre pas le CPA => PASS, gate dur."""
    # Coût 2€ -> retail 8€ -> marge brute 6€ < CPA 12€ => net négatif.
    res = score_sellability("thin", cost_eur=2.0, listed_num=5, age_days=10)
    assert res.net_after_cpa_eur < 0
    assert res.verdict == "PASS"
    assert res.margin_score == 0.0


def test_healthy_product_is_buy():
    """Produit bien margé, prix d'impulsion, peu saturé, récent => BUY."""
    # Coût 18€ -> retail 45€ -> marge 27€, net ~15€ après CPA.
    res = score_sellability("healthy", cost_eur=18.0, listed_num=6, age_days=20)
    assert res.net_after_cpa_eur > 0
    assert res.verdict == "BUY"
    assert res.sellability >= DEFAULT_SELLABILITY.buy_threshold


def test_saturation_penalizes_score():
    """À économie égale, plus de vendeurs = score plus bas."""
    low = score_sellability("a", cost_eur=18.0, listed_num=5, age_days=20)
    high = score_sellability("b", cost_eur=18.0, listed_num=300, age_days=20)
    assert low.sellability > high.sellability
    assert low.saturation_score > high.saturation_score


def test_freshness_penalizes_old_products():
    fresh = score_sellability("a", cost_eur=18.0, listed_num=5, age_days=10)
    stale = score_sellability("b", cost_eur=18.0, listed_num=5, age_days=900)
    assert fresh.sellability > stale.sellability


def test_missing_price_does_not_crash():
    res = score_sellability("noprice", cost_eur=None, listed_num=None, age_days=None)
    assert res.verdict == "PASS"
    assert res.retail_eur == 0.0


# --- Saisonnalité ----------------------------------------------------------

def test_water_gun_peaks_in_summer():
    """Un pistolet à eau doit être en saison en juillet, hors saison en janvier."""
    summer = seasonality_for("Kids Water Gun Toy", month=7)
    winter = seasonality_for("Kids Water Gun Toy", month=1)
    assert summer.profile == "summer_water"
    assert summer.multiplier > 1.0
    assert winter.multiplier < 1.0
    assert summer.multiplier > winter.multiplier


def test_christmas_peaks_in_december():
    dec = seasonality_for("Christmas Tree Ornament Set", month=12)
    jun = seasonality_for("Christmas Tree Ornament Set", month=6)
    assert dec.peak_month == 12
    assert dec.multiplier > jun.multiplier


def test_non_seasonal_is_neutral():
    res = seasonality_for("Stainless Steel Kitchen Knife", month=4)
    assert res.profile is None
    assert res.multiplier == 1.0


def test_seasonal_curves_average_to_one():
    """Chaque profil est normalisé : la moyenne sur 12 mois vaut ~1,0."""
    for kw in ("Water Gun", "Christmas Gift", "Yoga Mat"):
        vals = [seasonality_for(kw, m).multiplier for m in range(1, 13)]
        assert abs(sum(vals) / 12 - 1.0) < 0.05
