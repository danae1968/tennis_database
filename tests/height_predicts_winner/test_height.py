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


# ---- height vs ranking (rank.py) --------------------------------------------------------------
from analyses.height_predicts_winner import rank as Rk  # noqa: E402


def _players_raw(n=60, seed=3):
    """Synthetic matches where taller players have better (smaller) ranks."""
    rng = np.random.default_rng(seed)
    ids = [f"p{i}" for i in range(n)]
    ht = {i: 165 + 2 * k for k, i in enumerate(ids)}
    rk = {i: 200 - 3 * k for k, i in enumerate(ids)}
    rows = []
    for m in range(n * 30):
        a, b = rng.choice(n, 2, replace=False)
        rows.append({"tour": "WTA", "tourney_level": "250", "winner_id": ids[a], "loser_id": ids[b],
                     "winner_ht": ht[ids[a]], "loser_ht": ht[ids[b]], "winner_rank": rk[ids[a]], "loser_rank": rk[ids[b]]})
    return pd.DataFrame(rows)


def test_player_table_filters_and_summarises():
    raw = _players_raw()
    raw.loc[0, "tourney_level"] = "D"                           # team events are ignored
    raw.loc[1, "winner_ht"] = 999                                # impossible height -> missing for that row only
    t = Rk.player_table(raw, min_matches=20)
    assert set(t.columns) == {"tour", "player", "n_matches", "median_rank", "best_rank", "height"}
    assert (t["n_matches"] >= 20).all() and (t["best_rank"] <= t["median_rank"]).all()
    assert Rk.player_table(raw, min_matches=10_000).empty


def test_spearman_sign_and_ci():
    t = Rk.player_table(_players_raw(), min_matches=1)
    s = Rk.spearman_height_rank(t, reps=200, seed=1)
    assert s["rho"] > 0.9 and s["lo"] <= s["rho"] <= s["hi"] and s["n"] == len(t)   # taller = better ranked
    assert Rk.spearman_height_rank(t, reps=200, seed=1) == s                       # deterministic


def test_height_bands_merge_thin_bands_and_cover_all():
    h = pd.Series([150] * 5 + [160] * 40 + [162] * 40 + [171] * 50 + [199] * 3)
    bands = Rk.height_bands(h, width=5, min_n=30)
    counts = [int(((h >= a) & (h < b)).sum()) for a, b in bands]
    assert sum(counts) == len(h) and min(counts) >= 30
    assert all(bands[i][1] == bands[i + 1][0] for i in range(len(bands) - 1))      # contiguous


def test_reach_by_band_shares():
    df = pd.DataFrame({"height": [170] * 10 + [185] * 10, "best_rank": [5] * 5 + [50] * 5 + [15] * 5 + [300] * 5})
    r = Rk.reach_by_band(df, [(165, 175), (180, 190)])
    assert r["top100"].tolist() == [1.0, 0.5] and r["top10"].tolist() == [0.5, 0.0] and r["top20"].tolist() == [0.5, 0.5]
    assert (r["top100_lo"] <= r["top100"] + 1e-9).all() and (r["top100"] <= r["top100_hi"] + 1e-9).all()


def _att_frame(n=3000, seed=4, informative=True):
    rng = np.random.default_rng(seed)
    ht = rng.normal(0, 8, n)                                           # height difference (cm)
    lr = (0.08 * ht if informative else 0) + rng.normal(0, 1, n)       # log rank ratio built from height (or not)
    p = 1 / (1 + np.exp(-(0.9 * lr + 0.01 * ht)))
    return pd.DataFrame({"ht_diff": ht, "log_rank_ratio": lr, "p1_won": (rng.random(n) < p).astype(int),
                         "tourney_id": rng.integers(0, 30, n).astype(str)})


def test_attenuation_zero_when_rank_independent_of_height_and_positive_when_built_from_it():
    ind = Rk.attenuation(_att_frame(informative=False), reps=20, seed=1)
    dep = Rk.attenuation(_att_frame(informative=True), reps=20, seed=1)
    assert abs(ind["share_absorbed"]) < 0.25 and abs(ind["share_absorbed_lpm"]) < 0.25
    assert dep["share_absorbed"] > 0.4 and dep["share_absorbed_lpm"] > 0.4
    assert dep["lo"] <= dep["share_absorbed"] <= dep["hi"]
    assert Rk.attenuation(_att_frame(), reps=20, seed=1) == Rk.attenuation(_att_frame(), reps=20, seed=1)


def test_attenuation_lpm_uses_centred_outcome():
    """Flipping player order (swap sign of predictors, flip outcome) must not change the LPM share."""
    x = _att_frame(seed=9)
    f = x.copy()
    f["ht_diff"], f["log_rank_ratio"], f["p1_won"] = -x["ht_diff"], -x["log_rank_ratio"], 1 - x["p1_won"]
    a, b = Rk.attenuation(x, reps=5, seed=1), Rk.attenuation(f, reps=5, seed=1)
    assert a["share_absorbed_lpm"] == pytest.approx(b["share_absorbed_lpm"], abs=1e-9)
