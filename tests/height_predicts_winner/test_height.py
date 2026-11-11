"""Tests for the height model: random player order, feature signs, metrics and the previous-season rates."""
import numpy as np
import pandas as pd
import pytest

from analyses.height_predicts_winner.data import build_matches, clean_height, player_ace_rates
from analyses.height_predicts_winner.model import evaluate, metrics, paired_bootstrap, taller_player_wins


def _raw(n=400, seed=1, year=2018, tour="ATP"):
    rng = np.random.default_rng(seed)
    hw = rng.normal(188, 7, n).round()
    hl = rng.normal(184, 7, n).round()
    return pd.DataFrame({
        "tourney_id": [f"{year}-{i % 20}" for i in range(n)], "tourney_date": year * 10000 + 101, "tourney_level": "250",
        "surface": "Hard", "score": "6-4 6-4", "round": "R32", "match_num": np.arange(n),
        "winner_id": [f"w{i % 30}" for i in range(n)], "loser_id": [f"l{i % 30}" for i in range(n)],
        "winner_ht": hw, "loser_ht": hl, "winner_rank": rng.integers(1, 100, n), "loser_rank": rng.integers(50, 300, n),
        "w_ace": 8, "l_ace": 4, "w_svpt": 60, "l_svpt": 60, "w_1stWon": 30, "w_2ndWon": 10, "l_1stWon": 25, "l_2ndWon": 8,
        "year": year, "tour": tour})


def test_random_order_is_balanced_deterministic_and_consistent():
    raw = _raw()
    a, _ = build_matches(raw, seed=5)
    b, _ = build_matches(raw, seed=5)
    pd.testing.assert_frame_equal(a, b)
    assert 0.4 < a["p1_won"].mean() < 0.6                         # no winner/loser leakage through the order
    # player 1's height is the winner's height exactly when player 1 won
    w = a["p1_won"] == 1
    assert (a.loc[w, "ht1"].values == raw.loc[w.values, "winner_ht"].values).all()
    assert (a.loc[~w, "ht1"].values == raw.loc[(~w).values, "loser_ht"].values).all()
    assert np.allclose(a["ht_diff"], a["ht1"] - a["ht2"])
    assert np.allclose(a["log_rank_ratio"], np.log(a["rank2"]) - np.log(a["rank1"]))


def test_heights_outside_range_are_missing_and_retirements_dropped():
    assert clean_height(pd.Series([170, 20080331, 0, None, 215])).isna().tolist() == [False, True, True, True, False]
    raw = _raw(n=10)
    raw.loc[0, "score"] = "6-4 2-1 RET"
    raw.loc[1, "tourney_level"] = "D"
    m, log = build_matches(raw)
    assert len(m) == 8


def test_previous_season_rates_are_lagged():
    raw = pd.concat([_raw(n=60, year=2018), _raw(n=60, year=2019)], ignore_index=True)
    rates = player_ace_rates(raw, min_svpt=100)
    m, _ = build_matches(raw, ace_rates=rates)
    assert m.loc[m.year == 2018, "ace1"].isna().all()               # no 2017 data -> unknown
    assert m.loc[m.year == 2019, "ace1"].notna().all()
    assert m["ace_diff"].abs().max() == pytest.approx((8 - 4) / 60 * 100)


def test_metrics_and_models():
    y = np.array([1, 0, 1, 0])
    assert metrics(y, np.full(4, 0.5)) == {"accuracy": 0.5, "auc": 0.5, "log_loss": pytest.approx(np.log(2)), "n": 4}
    assert metrics(y, np.array([0.9, 0.1, 0.8, 0.3]))["accuracy"] == 1.0
    m, _ = build_matches(_raw(n=2000))
    tab, fitted = evaluate(m.iloc[:1500], m.iloc[1500:])
    t = tab.set_index("model")
    assert t.loc["Coin flip", "log_loss"] == pytest.approx(np.log(2))
    assert t.loc["Height only", "height_or_per_10cm"] > 1              # winners are taller in the synthetic data
    tw = taller_player_wins(m)
    assert tw["taller_wins"] > 0.5 and 0 <= tw["share_equal_height"] < 0.2
    b = paired_bootstrap(m.iloc[1500:]["p1_won"].values, fitted["Coin flip"][1], fitted["Height only"][1], reps=50)
    assert b["d_logloss"] > 0 and b["d_logloss_lo"] <= b["d_logloss"] <= b["d_logloss_hi"]
