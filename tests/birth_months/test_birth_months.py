"""Tests for birth-date parsing, de-duplication, placeholder detection and month statistics."""
import numpy as np
import pandas as pd

from analyses.birth_months.data import (dedupe_by_id, dedupe_by_name_birthdate, detect_placeholder_days,
                                        normalise_name, parse_birthdate)
from analyses.birth_months.months import chi_square_gof, expected_counts, holm, month_counts


def test_parse_birthdate_robust():
    s = pd.Series(["19930316", "19930316.0", "19931301", "19930230", "", None, "abc", "1993"])
    out = parse_birthdate(s)
    assert out.notna().tolist() == [True, True, False, False, False, False, False, False]
    assert out.iloc[0] == pd.Timestamp("1993-03-16")


def test_dedupe_by_id_keeps_first():
    df = pd.DataFrame({"player_id": ["a", "a", "b"], "x": [1, 2, 3]})
    assert dedupe_by_id(df)["x"].tolist() == [1, 3]


def test_name_normalisation_and_name_birthdate_dedup():
    assert normalise_name("José  Müller-Smith") == normalise_name("smith muller jose")
    df = pd.DataFrame({
        "player_id": ["1", "2", "3", "4"],
        "name_norm": ["a b", "a b", "a b", "c d"],
        "birthdate": pd.to_datetime(["1990-01-05", "1990-01-05", "1991-02-02", None]),
        "n_matches": [0, 7, 1, 0]})
    out = dedupe_by_name_birthdate(df)
    assert sorted(out["player_id"]) == ["2", "3", "4"]   # busiest duplicate kept


def test_expected_counts_proportional_to_days():
    e = expected_counts(1000)
    assert abs(e.sum() - 1000) < 1e-9
    assert e[0] / e[1] == 31 / 28.25 and e[3] == e[5]


def test_uniform_by_days_has_zero_chi2_and_holm_monotone():
    c = np.round(expected_counts(36525)).astype(int)
    assert chi_square_gof(c)["p"] > 0.99
    assert (holm(np.array([0.01, 0.04, 0.03])) >= np.array([0.01, 0.04, 0.03])).all()


def test_placeholder_detection_flags_jan1():
    rng = np.random.default_rng(0)
    d = pd.to_datetime(pd.Series(pd.date_range("1980-01-02", periods=8000, freq="D").to_numpy()[rng.integers(0, 8000, 6000)]))
    d = pd.concat([d, pd.Series(pd.to_datetime(["1985-01-01"] * 80))], ignore_index=True)
    ph = detect_placeholder_days(d)
    assert ph.loc[ph.month == 1, "flagged"].item() and not ph.loc[ph.month == 6, "flagged"].item()


def test_month_counts_length():
    assert month_counts(pd.Series([1, 1, 12])).tolist() == [2] + [0] * 10 + [1]
