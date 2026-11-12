"""Tests for clock parsing, tiebreak/set logic, score parsing and the trend helpers."""
import numpy as np
import pandas as pd

from analyses.match_length_trends.pbp import add_point_cycle, gender_from_match_id, is_tiebreak_game, parse_clock
from analyses.match_length_trends.tml import parse_score
from analyses.match_length_trends.trends import trend_per_decade, yearly_summary


def test_parse_clock_rejects_garbage():
    s = pd.Series(["0:01:05", "1:55:4", "0", "-19:21:22", None, "2:61:00"])
    out = parse_clock(s)
    assert out.iloc[0] == 65 and out.iloc[1:].isna().all()


def test_gender_from_match_id():
    g = gender_from_match_id(pd.Series(["2023-usopen-1101", "2023-usopen-2101", "2021-ausopen-MS101", "x-y-3101"]))
    assert g.tolist()[:3] == ["men", "women", "men"] and pd.isna(g.iloc[3])


def test_tiebreak_flag_uses_two_servers():
    # tiebreak: two servers and 7-6 / 13-12; advantage-set game that ends a set 7-6 has ONE server; 7-5 is never a tiebreak
    out = is_tiebreak_game(pd.Series([2, 1, 2, 2, 1]), pd.Series([7, 7, 13, 7, 13]), pd.Series([6, 6, 12, 5, 12]))
    assert out.tolist() == [True, False, True, False, False]


def test_set_winner_from_games_not_setwinner_column():
    from analyses.match_length_trends.pbp import legal_set_score, set_table
    d = pd.DataFrame({"match_id": ["m"] * 4, "SetNo": [1, 1, 2, 2], "sec": [0.0, 10, 20, 30], "raw_gap": [np.nan, 10, 10, 10],
                      "P1GamesWon": [6, 6, 7, 3], "P2GamesWon": [4, 4, 6, 6],
                      "SetWinner": [0, 2, 0, 1]})        # file flags are wrong/missing: winner must come from games
    t = set_table(d).set_index("set_no")
    assert t.loc[1, "winner"] == 1 and t.loc[2, "winner"] == 2 and bool(t.loc[2, "legal"])
    assert legal_set_score(pd.Series([3, 7, 12, 13]), pd.Series([5, 5, 10, 12])).tolist() == [False, True, True, True]
    d2 = d.assign(P1GamesWon=[6, 6, 5, 3], P2GamesWon=[4, 4, 2, 2])    # unfinished set 2 (5-2): illegal, winner 0
    assert set_table(d2).set_index("set_no").loc[2, "winner"] == 0


def test_point_cycle_cleaning():
    d = pd.DataFrame({"match_id": ["m"] * 6, "SetNo": [1] * 6, "GameNo": [1, 1, 1, 1, 1, 2],
                      "sec": [0, 30, 30, 70, 400, 430]})
    out = add_point_cycle(d)
    assert out["dt_status"].tolist() == ["na", "ok", "zero_or_neg", "ok", "too_long", "na"]
    assert out["dt"].dropna().tolist() == [30, 40]


def test_parse_score():
    a = parse_score("6-4 3-6 7-6(5)")
    assert a["valid"] and a["n_sets"] == 3 and a["n_games"] == 6 + 4 + 3 + 6 + 7 + 6 and a["n_tiebreaks"] == 1
    assert not parse_score("6-4 3-2 RET")["valid"] and not parse_score("W/O")["valid"] and not parse_score(None)["valid"]


def test_trend_recovers_known_slope_and_is_deterministic():
    rng = np.random.default_rng(1)
    df = pd.DataFrame({"year": np.repeat(np.arange(2014, 2025), 50)})
    df["y"] = 30 + 0.3 * (df["year"] - 2014) + rng.normal(0, 1, len(df))
    df["ed"] = df["year"]
    r = trend_per_decade(df, "y", "ed")
    assert abs(r["per_decade"] - 3.0) < 0.3 and r["p"] < 0.001
    assert yearly_summary(df, "y", []).equals(yearly_summary(df, "y", []))


def test_trend_with_step_separates_slope_from_level_shift():
    from analyses.match_length_trends.trends import trend_with_step
    rng = np.random.default_rng(2)
    df = pd.DataFrame({"year": np.repeat(np.arange(1995, 2026), 40)})
    df["y"] = 90 + 0.5 * (df["year"] - 1995) - 7 * (df["year"] >= 2013) + rng.normal(0, 1, len(df))
    df["ed"] = df["year"]
    out = trend_with_step(df, "y", "ed")
    assert abs(out["whole (step allowed)"]["per_decade"] - 5.0) < 0.5            # slope recovered despite the step
    assert abs(out["before"]["per_decade"] - 5.0) < 0.5 and abs(out["since"]["per_decade"] - 5.0) < 1.0
    assert trend_per_decade(df, "y", "ed")["per_decade"] < 4.0                    # ignoring the step biases the slope down


def test_restrict_to_reliable_and_blank_low_coverage():
    from analyses.match_length_trends.tml import blank_low_coverage, restrict_to_reliable
    d = pd.DataFrame({"group": ["ATP bo3", "ATP bo3", "ATP bo5", "ATP bo5", "WTA"], "year": [1994, 1995, 1999, 2000, 2008]})
    assert restrict_to_reliable(d)[["group", "year"]].values.tolist() == [["ATP bo3", 1995], ["ATP bo5", 2000]]
    x = pd.DataFrame({"group": ["C"] * 4 + ["C"] * 4, "year": [2015] * 4 + [2016] * 4,
                      "minutes": [90, np.nan, np.nan, np.nan, 80, 85, 90, np.nan], "sec_per_point": [30.0] * 8})
    out = blank_low_coverage(x, ["minutes", "sec_per_point"], ["group", "year"], 0.5)
    assert out[out.year == 2015]["minutes"].isna().all() and out[out.year == 2015]["sec_per_point"].isna().all()
    assert out[out.year == 2016]["minutes"].notna().sum() == 3 and out[out.year == 2016]["sec_per_point"].notna().all()
