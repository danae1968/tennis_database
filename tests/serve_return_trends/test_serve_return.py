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
