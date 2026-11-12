"""Tests for the serve/return trend analysis: match frame, break rates from the score, winner flags."""
import numpy as np
import pandas as pd
import pytest

from analyses.serve_return_trends.data import build_match_frame
from analyses.serve_return_trends.winners import charting_totals, pbp_point_flags, provider


def _raw(**over):
    row = dict(tourney_id="2020-1", tourney_name="X", tourney_date=20200101, tourney_level="250", surface="Hard",
               score="6-4 7-6(5)", round="R32", best_of=3, winner_rank=10, loser_rank=50, w_ace=5, l_ace=3,
               w_svpt=60, l_svpt=55, w_bpFaced=2, w_bpSaved=2, l_bpFaced=4, l_bpSaved=3, year=2020, tour="WTA")
    row.update(over)
    return row


def test_breaks_per_return_game_use_score_not_svgms():
    d, log = build_match_frame(pd.DataFrame([_raw()]))
    r = d.iloc[0]
    assert r.service_games == 22                       # 10 + 12 regular games; the tiebreak is not a service game
    assert r.breaks == 1 and r.break_rate == pytest.approx(1 / 22)
    assert r.aces == 8 and r.svpt == 115 and r.ace_rate == pytest.approx(8 / 115)
    assert r.bp_conversion == pytest.approx(1 / 6)


def test_exclusions():
    rows = [_raw(), _raw(tourney_level="D"), _raw(score="6-4 2-1 RET"), _raw(w_svpt=np.nan),
            _raw(w_bpSaved=5, w_bpFaced=2), _raw(score="6-4 3-6 [10-7]")]
    d, log = build_match_frame(pd.DataFrame(rows))
    assert len(d) == 2                                 # the clean match and the match-tiebreak match
    assert d.service_games.tolist() == [22, 19]
    steps = dict(zip(log.step, log["count"]))
    assert steps["matches used"] == 2 and steps["  removed: team events (Davis Cup, BJK Cup)"] == 1


def test_partial_year_and_surface_flags():
    d, _ = build_match_frame(pd.DataFrame([_raw(year=2026), _raw(surface="Unknown")]))
    assert d.partial_year.tolist() == [True, False] and pd.isna(d.surface.iloc[1])


def test_pbp_winner_flags_exclude_aces_for_both_providers():
    # IBM: an ace is also flagged as a winner; Infosys: it is not. Both must give 1 winner_ex on point 2 only.
    ibm = pd.DataFrame({"match_id": ["m"] * 3, "PointNumber": ["0X", "1", "2"], "P1Ace": ["0", "1", "0"],
                        "P2Ace": ["0", "0", "0"], "P1Winner": ["0", "1", "0"], "P2Winner": ["0", "0", "1"],
                        "P1UnfErr": ["0", "0", "0"], "P2UnfErr": ["0", "0", "0"]})
    infosys = ibm.assign(P1Winner=["0", "0", "0"])
    for df in (ibm, infosys):
        f = pbp_point_flags(df)
        assert len(f) == 2 and f.ace.tolist() == [1, 0] and f.winner_ex_ace.tolist() == [0, 1]
    assert pbp_point_flags(ibm).winner_and_ace.sum() == 1 and pbp_point_flags(infosys).winner_and_ace.sum() == 0
    assert provider(2019, "ausopen") == "Infosys" and provider(2022, "usopen") == "IBM" and provider(2017, "frenchopen") == "IBM"


def test_charting_winners_exclude_aces():
    o = pd.DataFrame({"match_id": ["a", "a", "a", "b"], "player": ["P", "Q", "P", "R"], "set": ["Total", "Total", "1", "Total"],
                      "serve_pts": ["60", "50", "30", "40"], "aces": ["5", "2", "3", "1"], "winners": ["20", "12", "9", "8"],
                      "unforced": ["10", "14", "5", "3"]})
    t = charting_totals(o)
    assert t.match_id.tolist() == ["a"]                 # match b has only one player row
    r = t.iloc[0]
    assert (r.points, r.aces, r.winners_ex, r.ue) == (110, 7, 25, 24)


# ---- long window: tour start seasons, coverage, like-for-like levels and slope changes --------------------
from analyses.serve_return_trends import eras  # noqa: E402
from analyses.serve_return_trends.data import START, coverage_table  # noqa: E402
from analyses.serve_return_trends.winners import feed_check, round_reweighted  # noqa: E402


def test_seasons_before_each_tour_start_are_dropped():
    rows = [_raw(tour="WTA", year=START["WTA"] - 1), _raw(tour="WTA", year=START["WTA"]),
            _raw(tour="Challenger", year=2009), _raw(tour="ATP", year=1991)]
    d, log = build_match_frame(pd.DataFrame(rows))
    assert sorted(zip(d.tour, d.year)) == [("ATP", 1991), ("WTA", START["WTA"])]
    assert dict(zip(log.step, log["count"]))[
        "  removed: seasons before reliable serve stats (WTA < 2009, Challenger < 2010)"] == 2


def test_coverage_table_counts_completed_matches_only():
    rows = [_raw(year=2008), _raw(year=2008, w_ace=np.nan, winner_rank=200, loser_rank=300),
            _raw(year=2008, score="6-4 1-0 RET"), _raw(year=2008, tourney_level="D")]
    c = coverage_table(pd.DataFrame(rows)).iloc[0]
    assert c.matches == 2 and c.with_stats == 1 and c.share == 0.5          # RET and team event not counted
    assert c.median_rank_covered == 10 and c.median_rank_missing == 200 and not c.used   # WTA 2008 < 2009


def _panel(slope_before: float, slope_after: float, knot: int = 2016, seed: int = 0) -> pd.DataFrame:
    """Matches at 6 tournaments with different levels, rate following a kinked line plus noise."""
    rng = np.random.default_rng(seed)
    rows = []
    for k in range(6):
        for y in range(2000, 2026):
            for _ in range(20):
                mu = 0.20 + 0.02 * k + slope_before * min(y - knot, 0) / 10 + slope_after * max(y - knot, 0) / 10
                rows.append({"tournament": f"T{k}", "year": y, "den": 30.0, "rate": mu + rng.normal(0, 0.01)})
    d = pd.DataFrame(rows)
    d["num"] = d["rate"] * d["den"]
    return d


def test_slope_change_recovers_a_kink():
    r = eras.slope_change(_panel(0.03, -0.01), "rate", "den")
    assert r["slope_before"] == pytest.approx(3.0, abs=0.1) and r["slope_after"] == pytest.approx(-1.0, abs=0.1)
    assert r["change"] == pytest.approx(-4.0, abs=0.2) and r["change_lo"] < r["change"] < r["change_hi"] < 0
    assert r["p_change"] < 0.001
    flat = eras.slope_change(_panel(0.01, 0.01, seed=1), "rate", "den")
    assert flat["change_lo"] < 0 < flat["change_hi"]


def test_like_for_like_index_ignores_calendar_changes():
    d = _panel(0.0, 0.0)
    # a high-level tournament only appears from 2015: the pooled rate jumps, the like-for-like level does not
    extra = d[d.tournament == "T5"].assign(tournament="NEW", rate=lambda x: x.rate + 0.2)
    d = pd.concat([d, extra[extra.year >= 2015]])
    d["num"] = d["rate"] * d["den"]
    ix = eras.like_for_like_index(d, "rate", "num", "den", ref_year=2025)
    assert (ix.rate.max() - ix.rate.min()) < 0.01
    ref = d[d.year == 2025]
    assert ix.set_index("year").rate[2025] == pytest.approx(ref.num.sum() / ref.den.sum())
    j = eras.year_on_year_jumps(ix)
    assert len(j) == len(ix) - 1 and (j.relative_to_median_change >= 0).all()


def test_feed_check_and_round_reweighting():
    p = pd.DataFrame({"year": [2012, 2012, 2019, 2019], "slam": ["usopen", "usopen", "ausopen", "ausopen"],
                      "provider": ["IBM", "IBM", "Infosys", "Infosys"], "match_id": list("abcd"), "annotated": True,
                      "aces": [5, 5, 4, 6], "winner_and_ace": [5, 5, 0, 0], "points": [100] * 4,
                      "winners_ex": [20, 30, 25, 25], "gender": ["M"] * 4, "round": ["R128", "F", "R128", "F"]})
    f = feed_check(p).set_index("slam")
    assert f.loc["usopen", "share_aces_flagged_winner"] == 1 and f.loc["ausopen", "share_aces_flagged_winner"] == 0
    r = round_reweighted(p, p).set_index("year")
    assert r.loc[2012, "raw"] == pytest.approx(25) and r.loc[2012, "round_reweighted"] == pytest.approx(25)
