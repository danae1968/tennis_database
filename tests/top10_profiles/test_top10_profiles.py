"""Tests for the top-10 profiles: score-based service games, top-10 selection, rate helpers."""
import numpy as np
import pandas as pd

from analyses.top10_profiles import data, metrics
from analyses.top10_profiles.boot import boot_ci
from tennis.scores import parse_score, regular_games, service_games


def test_service_games_from_score_not_svgms():
    sets = parse_score("6-4 7-6(5)", allow_match_tiebreak=True)
    assert regular_games(sets) == 10 + 12                  # the tiebreak game is not a service game
    assert service_games(sets) == (11.0, 11.0)             # expectation: half each


def test_match_tiebreak_not_a_service_game():
    sets = parse_score("6-4 3-6 [10-7]", allow_match_tiebreak=True)
    assert regular_games(sets) == 10 + 9


def test_retirement_dropped_from_long_table():
    assert parse_score("6-3 2-1 RET", allow_match_tiebreak=True) is None


def _match(**kw):
    base = dict(tourney_id="T", match_num=1, date=pd.Timestamp("2026-05-01"), surface="Clay", best_of=3, tourney_level="250",
                winner_id="A", loser_id="B", winner_name="A", loser_name="B", score="6-4 6-4",
                w_svpt=60, l_svpt=60, w_1stWon=30, l_1stWon=25, w_2ndWon=10, l_2ndWon=10, w_bpSaved=2, w_bpFaced=3,
                l_bpSaved=1, l_bpFaced=5, w_SvGms=999, l_SvGms=999)   # absurd SvGms must be ignored
    base.update(kw)
    return base


def test_long_table_ignores_svgms_and_counts_breaks():
    d = pd.DataFrame([_match()])
    L = data.long_table(d, pd.Timestamp("2026-06-01"))
    a, b = L[L.id == "A"].iloc[0], L[L.id == "B"].iloc[0]
    assert a.svg == 10 and b.svg == 10                     # 20 regular games, half each
    assert a.conceded == 1 and a.breaks == 4               # B saved 1 of 5 => A broke 4 times
    assert a.o_svg == b.svg
    m = metrics.hold_break(L[L.id == "A"], seed=1)
    assert abs(m["hold"] - 0.9) < 1e-9 and abs(m["brk"] - 0.4) < 1e-9


def test_window_is_52_weeks():
    d = pd.DataFrame([_match(date=pd.Timestamp("2025-01-01")), _match(date=pd.Timestamp("2026-05-01"), match_num=2)])
    L = data.long_table(d, pd.Timestamp("2026-06-01"))
    assert set(L.match_id) == {"T-2"}


def test_top10_skips_stale_ranks_and_orders_by_rank():
    rows = []
    for i, (pid, rk, day) in enumerate([("a", 1, "2026-03-01"), ("b", 2, "2026-11-01"), ("c", 3, "2026-11-02"),
                                        ("d", 3, "2026-11-03")]):
        rows.append(dict(date=pd.Timestamp(day), match_num=i, winner_id=pid, winner_name=pid, winner_rank=rk, winner_rank_points=100 - i,
                         loser_id="z", loser_name="z", loser_rank=50.0, loser_rank_points=1.0))
    top, info = data.current_top10(pd.DataFrame(rows))
    assert "a" not in set(top.id)                          # last played > 12 weeks before the data end
    assert list(top.id[:3]) == ["b", "c", "d"]
    assert info["as_of"] == "2026-11-03"


def test_boot_ci_is_deterministic_and_brackets_estimate():
    c = np.array([[3, 10], [5, 10], [7, 10], [2, 10]], float)
    r1 = boot_ci(c, lambda s: s[..., 0] / s[..., 1], seed=3)
    r2 = boot_ci(c, lambda s: s[..., 0] / s[..., 1], seed=3)
    assert r1 == r2 and r1[1] <= r1[0] <= r1[2]


def test_norm_name():
    assert data.norm_name("Félix Auger-Aliassime") == data.norm_name("Felix Auger Aliassime")


def test_force_include_overrides_staleness_only_for_named_player():
    rows = []
    for i, (pid, rk, day) in enumerate([("a", 1, "2026-03-01"), ("s", 2, "2026-03-02"), ("b", 3, "2026-11-01")]):
        rows.append(dict(date=pd.Timestamp(day), match_num=i, winner_id=pid, winner_name=pid, winner_rank=rk, winner_rank_points=100 - i,
                         loser_id="z", loser_name="z", loser_rank=50.0, loser_rank_points=1.0))
    top, info = data.current_top10(pd.DataFrame(rows), {"s": "test"})
    assert list(top.id[:2]) == ["s", "b"] and "a" not in set(top.id)
    assert bool(top.forced.iloc[0]) and info["forced_include"] == {"s": "test"}


def test_level_filter_keeps_prague_drops_team_events():
    d = pd.DataFrame({"tourney_level": ["A", "A", "A", "D", "G", "C"],
                      "tourney_name": ["Prague Open", "United Cup", "Laver Cup", "Davis Cup R1", "Wimbledon", "Challenger X"]})
    assert data.tour_level_mask(d).tolist() == [True, False, False, False, True, False]


def test_window_mask_start_exclusive_end_inclusive():
    asof = pd.Timestamp("2026-11-08")
    dates = pd.Series(pd.to_datetime(["2025-11-10", "2025-11-09", "2026-11-08", "2026-11-09"]))
    assert data.window_mask(dates, asof).tolist() == [True, False, True, False]


def test_gap_tests_holm_and_selection():
    rows = [dict(gap=5.0, tour_gap=0.0, sd=1.0), dict(gap=0.1, tour_gap=0.0, sd=1.0), dict(gap=-0.2, tour_gap=0.0, sd=1.0)]
    t = metrics.gap_tests(rows)
    assert t.p_holm.iloc[0] < 0.001 and (t.p_holm.iloc[1:] == 1.0).all() and (t.p_holm >= t.p).all()
    # selecting the top by hold + break induces a negative correlation although the two are independent
    rng = np.random.default_rng(0)
    tab = pd.DataFrame({"id": [str(i) for i in range(400)], "hold": rng.normal(0.7, 0.05, 400), "brk": rng.normal(0.3, 0.05, 400)})
    sel = metrics.selection_check(tab, set(tab.assign(s=tab.hold + tab.brk).nlargest(10, "s").id))
    assert abs(sel["corr_all"]) < 0.15 and sel["corr_top10"] < -0.4
