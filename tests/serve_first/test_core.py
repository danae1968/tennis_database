"""Tests for first-server detection, set reconstruction, CIs, name matching and the SvGms rule."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from analyses.serve_first.inference import parse_score, serve_plan, svgms_fit
from analyses.serve_first.sets import (add_match_context, build_games, build_sets, flag_usable,
                                       is_valid_set_score, next_set_first_server, renumber_games)
from tennis.stats import cluster_prop_ci, wilson_ci
from analyses.serve_first.linking import names_match


# ------------------------------------------------------------------ synthetic point data
def make_points(sets: list[list[tuple[int, int]]], first_server: int, cumulative: bool = False,
                with_winner_cols: bool = True, match_id: str = "2020-test-1101") -> pd.DataFrame:
    """Build a points frame. ``sets`` = per set a list of (game winner, n points); servers follow the
    real rotation from ``first_server`` (tiebreak = game at 6-6, server rotates every two points)."""
    rows, pn, gno_cum, server = [], 0, 0, first_server
    for s_idx, games in enumerate(sets, start=1):
        g1 = g2 = 0
        for g_idx, (winner, npts) in enumerate(games, start=1):
            gno_cum += 1
            tb = g1 == g2 == 6
            for k in range(npts):
                pn += 1
                srv = server if not tb else (server if (k % 4 in (0, 3)) else 3 - server)
                last = k == npts - 1
                rows.append(dict(match_id=match_id, SetNo=s_idx, GameNo=gno_cum if cumulative else g_idx,
                                 PointNumber=pn, PointServer=srv, PointWinner=winner if last else srv,
                                 GameWinner=(winner if last else 0) if with_winner_cols else 0,
                                 SetWinner=0, P1GamesWon=0, P2GamesWon=0))
            g1, g2 = g1 + (winner == 1), g2 + (winner == 2)
            server = 3 - server
    return pd.DataFrame(rows)


def run_pipeline(P: pd.DataFrame) -> pd.DataFrame:
    M = pd.DataFrame(dict(match_id=[P.match_id.iloc[0]], year=[2020], slam=["usopen"], surface=["Hard"],
                          gender=["W"], best_of=[3], player1=["A"], player2=["B"]))
    P = renumber_games(P)
    return flag_usable(add_match_context(build_sets(P, build_games(P)), M))


SET_64_P1 = [(1, 4), (2, 4), (1, 4), (1, 5), (1, 4), (2, 4), (1, 4), (2, 4), (2, 6), (1, 4)]   # 6-4 to P1
SET_63_P2 = [(2, 4)] * 6 + [(1, 4)] * 3


def test_valid_set_scores():
    assert is_valid_set_score(6, 4, False)
    assert is_valid_set_score(7, 5, False)
    assert is_valid_set_score(7, 6, True)
    assert is_valid_set_score(13, 12, True)
    assert is_valid_set_score(12, 10, False)
    assert not is_valid_set_score(6, 5, False)
    assert not is_valid_set_score(7, 6, False)       # 7-6 needs a tiebreak
    assert not is_valid_set_score(5, 3, False)       # unfinished


def test_next_set_first_server_parity():
    assert next_set_first_server(1, 6, 4) == 1       # 10 games: same player opens the next set
    assert next_set_first_server(1, 6, 3) == 2       # 9 games: the other player
    assert next_set_first_server(2, 7, 6) == 1       # tiebreak counts as one game: 13 -> switch


@pytest.mark.parametrize("cumulative,with_cols", [(False, True), (True, False)])
def test_first_server_and_winner_detection(cumulative, with_cols):
    P = make_points([SET_64_P1, SET_63_P2], first_server=2, cumulative=cumulative, with_winner_cols=with_cols)
    S = run_pipeline(P)
    s1, s2 = S.iloc[0], S.iloc[1]
    assert (s1.fs, s1.set_winner, s1.g1, s1.g2) == (2, 1, 6, 4)
    assert not s1.fs_won
    # 10 games -> player 2 opens set 2 as well; set 2 won 6-3 by player 2
    assert (s2.fs, s2.set_winner, s2.min_game) == (2, 2, 1)
    assert s2.fs_won
    assert s2.predicted_fs == s2.fs
    assert S.usable.all() and not S.complete_match.any()   # 1-1 in sets: best of 3 not finished


def test_tiebreak_detected_and_counted_once():
    tb_set = [(1, 4), (2, 4)] * 6 + [(1, 9)]          # 6-6 then a 9-point tiebreak to player 1
    P = make_points([tb_set, SET_63_P2], first_server=1)
    S = run_pipeline(P)
    assert bool(S.iloc[0].has_tb) and (S.iloc[0].g1, S.iloc[0].g2) == (7, 6)
    assert S.iloc[1].fs == 2 == S.iloc[1].predicted_fs   # 13 games -> switch


def test_missing_game1_uses_parity_and_unfinished_set_excluded():
    P = make_points([SET_64_P1, [(2, 4), (1, 4), (1, 4)]], first_server=1)
    P = P[~((P.SetNo == 1) & (P.GameNo == 1))]        # drop game 1 of set 1
    S = run_pipeline(P)
    assert S.iloc[0].fs_direct == 0 and S.iloc[0].fs == 1
    assert S.iloc[1].exclude_reason.startswith("set not completed")
    assert not S.iloc[1].complete_match


def test_wilson_and_cluster_ci():
    lo, hi = wilson_ci(50, 100)
    assert lo == pytest.approx(0.40383, abs=1e-4) and hi == pytest.approx(0.59617, abs=1e-4)
    y = np.array([1, 0] * 50)
    r = cluster_prop_ci(y)                            # one obs per cluster -> exactly Wilson
    assert (r["lo"], r["hi"]) == pytest.approx((lo, hi))
    # perfectly correlated pairs -> design effect 2 -> wider interval
    y2 = np.repeat(np.array([1, 0] * 25), 2)
    r2 = cluster_prop_ci(y2, np.repeat(np.arange(50), 2))
    assert r2["deff"] == pytest.approx(2 * 50 / 49, rel=1e-6)
    assert r2["hi"] - r2["lo"] > hi - lo


def test_names_match():
    assert names_match("A. Dolgopolov", "Alexandr Dolgopolov")
    assert names_match("C Moutet", "Corentin Moutet")
    assert names_match("J. Del Potro", "Juan Martin Del Potro")
    assert names_match("Rafael Nadal", "Rafael Nadal")
    assert names_match("Lara Arruabarrena-Vecino", "Lara Arruabarrena Vecino")
    assert not names_match("K. Pliskova", "Karolina Muchova")
    assert not names_match("A. Zverev", "Mischa Zverev")


def test_svgms_rule():
    sets = parse_score("6-3 6-4")
    # winner served first: set 1 W serves 5, L 4; 9 games -> L opens set 2: L 5, W 5
    assert serve_plan(sets, True) == [(True, 5, 4), (False, 5, 5)]
    assert svgms_fit(sets, 10, 9) == (True, False)
    assert svgms_fit(sets, 9, 10) == (False, True)
    # tiebreak not counted in SvGms: 7-6 6-4 -> 12 regular games in set 1
    sets = parse_score("7-6(4) 6-4")
    plan = serve_plan(sets, True)
    assert plan[0][1] + plan[0][2] == 12
    assert parse_score("6-3 2-1 RET") is None


# ------------------------------------------------------------------ orientation of strength covariates and links
def _analysis_table(sets, first_server, p1_is_tml_winner):
    from analyses.serve_first.estimate import build_analysis_table
    P = renumber_games(make_points(sets, first_server=first_server))
    M = pd.DataFrame(dict(match_id=[P.match_id.iloc[0]], year=[2020], slam=["usopen"], surface=["Hard"],
                          gender=["W"], best_of=[3], player1=["A"], player2=["B"]))
    S = flag_usable(add_match_context(build_sets(P, build_games(P)), M))
    links = pd.DataFrame(dict(match_id=[P.match_id.iloc[0]], tml_row=[0], p1_is_tml_winner=[p1_is_tml_winner],
                              link_status=["linked"]))
    T = pd.DataFrame(dict(tml_row=[0], winner_rank=[10.0], loser_rank=[80.0], winner_rank_points=[1.0],
                          loser_rank_points=[1.0]))
    return build_analysis_table(S, P, links, T)


def _swap(sets):
    return [[(3 - w, n) for w, n in s] for s in sets]


def test_covariates_are_antisymmetric_and_label_invariant():
    """Relabelling player 1 <-> player 2 must not change anything seen from the first server's side."""
    sets = [SET_64_P1, SET_63_P2, [(1, 4)] * 6]        # P1 wins 6-4, P2 wins 6-3, P1 wins 6-0
    D = _analysis_table(sets, first_server=2, p1_is_tml_winner=True)
    Dsw = _analysis_table(_swap(sets), first_server=1, p1_is_tml_winner=False)
    for c in ("y", "d_logrank", "prev", "d_spw_loo"):
        assert np.allclose(D[c].values, Dsw[c].values, equal_nan=True), c
    # player 1 is the TML winner (rank 10) vs rank 80: in set 1 player 2 serves first -> d_logrank < 0
    s1 = D[D.set_no == 1].iloc[0]
    assert s1.fs == 2 and s1.d_logrank == pytest.approx(np.log(10) - np.log(80))
    # set 2 first server (player 2, 10 games in set 1) lost set 1 -> prev = -1; set 3 opened by player 1
    s2, s3 = D[D.set_no == 2].iloc[0], D[D.set_no == 3].iloc[0]
    assert s2.prev == -1 and s2.y == 1
    assert s3.fs == 1 and s3.prev == -1 and s3.y == 1


def test_link_orientation():
    from analyses.serve_first.linking import link_matches
    M = pd.DataFrame(dict(match_id=["x", "y"], year=[2015, 2015], slam=["usopen"] * 2, gender=["M"] * 2,
                          player1=["R. Nadal", "N Djokovic"], player2=["Novak Djokovic", "Roger Federer"]))
    T = pd.DataFrame(dict(tml_row=[0, 1], year=[2015, 2015], slam=["usopen"] * 2, gender=["M"] * 2,
                          winner_name=["Novak Djokovic", "Roger Federer"], loser_name=["Rafael Nadal", "Novak Djokovic"]))
    L = link_matches(M, T).set_index("match_id")
    assert L.loc["x", "tml_row"] == 0 and not L.loc["x", "p1_is_tml_winner"]
    assert L.loc["y", "tml_row"] == 1 and not L.loc["y", "p1_is_tml_winner"]
