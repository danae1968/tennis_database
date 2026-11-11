"""Tests for tennis.stats."""
import numpy as np
import pandas as pd
import pytest
from scipy import stats as st

from tennis.stats import (boot_median_ci, chisq_gof, clopper_pearson, cluster_prop_ci, expit, holm, logit_cluster,
                          wilson_ci)


def test_wilson_known_values_and_edge_cases():
    lo, hi = wilson_ci(50, 100)
    assert (lo, hi) == pytest.approx((0.40383, 0.59617), abs=1e-5)
    lo0, hi0 = wilson_ci(0, 20)
    assert lo0 == pytest.approx(0.0, abs=1e-12) and 0 < hi0 < 0.2
    assert all(np.isnan(wilson_ci(0, 0)))


def test_cluster_prop_ci_reduces_to_wilson_and_widens_with_clustering():
    y = np.array([1, 0] * 50)
    r = cluster_prop_ci(y)
    assert (r["lo"], r["hi"]) == pytest.approx(wilson_ci(50, 100)) and r["deff"] == 1.0
    y2 = np.repeat(y[:50], 2)                                   # perfectly correlated pairs
    r2 = cluster_prop_ci(y2, np.repeat(np.arange(50), 2))
    assert r2["deff"] == pytest.approx(2 * 50 / 49) and r2["n_clusters"] == 50
    assert r2["hi"] - r2["lo"] > r["hi"] - r["lo"]


def test_clopper_pearson_matches_scipy_exact_interval():
    for k, n in ((0, 10), (3, 10), (10, 10), (123, 1000)):
        ci = st.binomtest(k, n).proportion_ci(method="exact")
        assert clopper_pearson(k, n) == pytest.approx((ci.low, ci.high), abs=1e-12)


def test_holm_known_example():
    adj = holm(np.array([0.01, 0.04, 0.03, 0.005]))
    assert adj == pytest.approx([0.03, 0.06, 0.06, 0.02])
    assert (adj <= 1).all()


def test_boot_median_ci_deterministic_and_small_n():
    x = np.arange(100, dtype=float)
    a = boot_median_ci(x, np.random.default_rng(1))
    b = boot_median_ci(x, np.random.default_rng(1))
    assert a == b and a[0] < 49.5 < a[1]
    assert all(np.isnan(boot_median_ci(np.array([1.0, 2.0]), np.random.default_rng(1))))


def test_chisq_gof_matches_scipy():
    obs = np.array([30, 20, 25, 25])
    probs = np.array([0.25, 0.25, 0.25, 0.25])
    r = chisq_gof(obs, probs)
    chi2, p = st.chisquare(obs, obs.sum() * probs)
    assert r["chi2"] == pytest.approx(chi2) and r["p"] == pytest.approx(p) and r["df"] == 3 and r["n"] == 100
    assert r["cramers_v"] == pytest.approx(np.sqrt(chi2 / (100 * 3)))


def test_logit_cluster_recovers_level_probability():
    rng = np.random.default_rng(7)
    n = 4000
    x = rng.normal(size=n)
    p = 1 / (1 + np.exp(-(0.2 + 1.0 * x)))
    d = pd.DataFrame({"y": rng.random(n) < p, "x": x, "c": np.repeat(np.arange(n // 2), 2)})
    r = logit_cluster(d, "y", ["x"], "c")
    assert r["lo"] < expit(0.2) < r["hi"]
    assert r["coef_x"] == pytest.approx(1.0, abs=0.15) and r["n_clusters"] == n // 2
