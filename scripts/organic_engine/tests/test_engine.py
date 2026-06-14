"""Tests du moteur de scoring : le bon produit doit gagner."""

import numpy as np

from signals.features import RawSignal, build_product_features
from scoring.engine import score_population
from scoring.phases import Phase


def _series(start, factor, n=6, accel=1.0):
    """Génère une série croissante (factor par pas), accel>1 = accélère."""
    t = list(range(n))
    v = []
    cur = float(start)
    rate = factor
    for _ in range(n):
        v.append(cur)
        cur *= rate
        rate *= accel
    return RawSignal("", t, v), t, v


def _product(pid, sources: dict, **meta):
    raws = []
    for name, (start, factor, accel) in sources.items():
        t = list(range(6))
        v, cur, rate = [], float(start), factor
        for _ in range(6):
            v.append(cur)
            cur *= rate
            rate *= accel
        raws.append(RawSignal(name, t, v))
    return build_product_features(pid, raws, **meta)


def test_emerging_product_outscores_mature_one():
    # A : émergent, accélère sur sources organiques, bas niveau, jeune.
    emerging = _product(
        "emerging",
        {
            "sales": (50, 1.4, 1.05),
            "reddit": (5, 1.6, 1.10),
            "google_trends": (10, 1.5, 1.08),
        },
        age_days=20, seller_count=3, review_count=15,
    )
    # B : mature, gros volume plat, vieux, beaucoup de vendeurs.
    mature = _product(
        "mature",
        {
            "sales": (5000, 1.0, 1.0),
            "reddit": (200, 1.0, 1.0),
            "google_trends": (800, 1.0, 1.0),
        },
        age_days=400, seller_count=120, review_count=9000,
    )
    # C : en déclin.
    declining = _product(
        "declining",
        {"sales": (2000, 0.8, 1.0), "google_trends": (300, 0.85, 1.0)},
        age_days=300, seller_count=80, review_count=4000,
    )

    results = {r.product_id: r for r in score_population([emerging, mature, declining])}

    # Le produit émergent doit dominer.
    assert results["emerging"].organic_score > results["mature"].organic_score
    assert results["emerging"].organic_score > results["declining"].organic_score
    # Et être classé en phase précoce.
    assert results["emerging"].phase in (Phase.EMERGENT, Phase.EARLY_GROWTH)
    assert results["declining"].phase == Phase.DECLINING


def test_corroboration_counts_independent_rising_sources():
    p = _product(
        "multi",
        {
            "sales": (50, 1.4, 1.05),
            "reddit": (5, 1.6, 1.10),
            "tiktok": (8, 1.7, 1.10),
        },
        age_days=20,
    )
    flat = _product("flat", {"sales": (5000, 1.0, 1.0)}, age_days=300)
    results = {r.product_id: r for r in score_population([p, flat])}
    # 3 sources en hausse nette => corroboration élevée.
    assert results["multi"].corroboration >= 2


def test_confidence_reflects_source_coverage():
    rich = _product(
        "rich",
        {"sales": (50, 1.3, 1.0), "reddit": (5, 1.4, 1.0),
         "tiktok": (8, 1.5, 1.0), "google_trends": (10, 1.3, 1.0)},
        age_days=30,
    )
    poor = _product("poor", {"sales": (50, 1.3, 1.0)}, age_days=30)
    results = {r.product_id: r for r in score_population([rich, poor])}
    assert results["rich"].confidence > results["poor"].confidence


def test_explanation_is_decomposable():
    p = _product("x", {"sales": (50, 1.4, 1.05), "reddit": (5, 1.6, 1.1)}, age_days=20)
    q = _product("y", {"sales": (5000, 1.0, 1.0)}, age_days=300)
    results = {r.product_id: r for r in score_population([p, q])}
    reasons = results["x"].top_reasons()
    assert len(reasons) >= 1
    assert all(isinstance(s, str) for s in reasons)


def test_empty_population_is_safe():
    assert score_population([]) == []
