"""Tests de la boucle de feedback : backtest + apprentissage des poids."""

import numpy as np

from analytics.backtest import roc_auc, precision_at_k, run_backtest, brier_score
from analytics.learning import fit_logistic, FEATURE_ORDER


def test_perfect_separation_auc_one():
    scores = np.array([10, 20, 30, 80, 90, 95])
    outcomes = np.array([0, 0, 0, 1, 1, 1])
    assert roc_auc(scores, outcomes) == 1.0


def test_random_scores_auc_near_half():
    rng = np.random.default_rng(0)
    scores = rng.random(2000)
    outcomes = rng.integers(0, 2, 2000)
    assert 0.45 < roc_auc(scores, outcomes) < 0.55


def test_precision_at_k_picks_top():
    scores = np.array([0.1, 0.2, 0.9, 0.95, 0.3])
    outcomes = np.array([0, 0, 1, 1, 0])
    assert precision_at_k(scores, outcomes, k=2) == 1.0


def test_brier_perfect_is_zero():
    probs = np.array([0.0, 1.0, 1.0, 0.0])
    outcomes = np.array([0, 1, 1, 0])
    assert brier_score(probs, outcomes) == 0.0


def test_run_backtest_report():
    scores = np.array([5, 15, 25, 70, 85, 92, 40, 60])
    outcomes = np.array([0, 0, 0, 1, 1, 1, 0, 1])
    report = run_backtest(scores, outcomes, k=3)
    assert report.n == 8
    assert report.auc > 0.7
    assert 0.0 <= report.precision_at_k <= 1.0
    assert isinstance(report.summary(), str)


def test_logistic_learns_predictive_signal():
    # momentum prédit l'issue ; le bruit ne doit pas dominer.
    rng = np.random.default_rng(1)
    n = 400
    momentum = rng.normal(0, 1, n)
    noise = rng.normal(0, 1, n)
    prob = 1 / (1 + np.exp(-(2.5 * momentum)))
    y = (rng.random(n) < prob).astype(int)
    X = np.column_stack([momentum, noise])
    model = fit_logistic(X, y, ["momentum", "noise"])
    pv = model.predictive_value()
    # Le signal vraiment prédictif doit peser bien plus que le bruit.
    assert pv["momentum"] > pv["noise"]
    assert pv["momentum"] > 0.6
