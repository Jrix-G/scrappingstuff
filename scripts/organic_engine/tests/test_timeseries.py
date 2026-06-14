"""Tests des dérivées temporelles : la base scientifique du moteur."""

import numpy as np

from signals.timeseries import extract_trend, robust_zscores, percentile_rank


def _days(n):
    return list(range(0, n))


def test_exponential_growth_has_constant_velocity_zero_acceleration():
    # Croissance exponentielle pure : log-pente constante => accélération ~ 0.
    t = _days(8)
    v = [100 * (1.5**i) for i in range(8)]  # +50%/pas
    tf = extract_trend(t, v, smooth=False)
    assert tf.velocity > 0
    assert abs(tf.acceleration) < 1e-3        # pas d'accélération
    assert tf.monthly_growth > 0


def test_accelerating_growth_has_positive_acceleration():
    # Croissance super-exponentielle : l'accélération doit être positive.
    t = _days(8)
    v = [100 * np.exp(0.05 * i * i) for i in range(8)]  # exposant quadratique
    tf = extract_trend(t, v, smooth=False)
    assert tf.acceleration > 0


def test_declining_series_negative_velocity():
    t = _days(6)
    v = [500, 400, 320, 256, 205, 164]
    tf = extract_trend(t, v, smooth=False)
    assert tf.velocity < 0
    assert tf.monthly_growth < 0


def test_flat_series_near_zero_velocity():
    t = _days(6)
    v = [300, 301, 299, 300, 302, 298]
    tf = extract_trend(t, v, smooth=False)
    assert abs(tf.monthly_growth) < 0.05


def test_single_point_is_safe():
    tf = extract_trend([0], [100])
    assert tf.velocity == 0 and tf.acceleration == 0


def test_robust_zscores_resist_outlier():
    x = np.array([1, 2, 3, 4, 1000])  # un best-seller extrême
    z = robust_zscores(x)
    # La médiane (3) reste le centre ; l'outlier ne tire pas tout vers le haut.
    assert abs(z[2]) < 0.5
    assert z[4] > z[2]


def test_percentile_rank_bounds():
    x = np.array([10, 20, 30, 40])
    p = percentile_rank(x)
    assert p[0] == 0.0 and p[-1] == 1.0
