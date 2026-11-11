"""Tests for tennis.scores: score parsing and score-based service-game counts."""
import pandas as pd
import pytest

from tennis.scores import (SetScore, parse_score, regular_games, score_game_counts, serve_plan,
                           service_games)


def test_parse_score_accepts_completed_and_rejects_incomplete():
    assert parse_score("6-4 7-6(5)") == [SetScore(6, 4, False), SetScore(7, 6, True)]
    assert parse_score("6-7(3) 7-6 13-12(4)")[2] == SetScore(13, 12, True)
    assert parse_score("4-6 6-3 12-10")[2] == SetScore(12, 10, False)       # advantage final set
    for bad in ("6-3 2-1 RET", "W/O", "6-4 5-4", "", None, "6-4 3-6", "6-5 6-0", "NA-6 6-1"):
        assert parse_score(bad) is None, bad


def test_match_tiebreak_only_when_allowed():
    assert parse_score("6-4 3-6 [10-7]") is None
    sets = parse_score("6-4 3-6 [10-7]", allow_match_tiebreak=True)
    assert sets[2] == SetScore(1, 0, True, True)
    assert regular_games(sets) == 19                                      # match tiebreak is no service game
    assert parse_score("6-4 3-6 [8-10]", allow_match_tiebreak=True) is None   # winner must win the last set


def test_service_games_exclude_tiebreaks_and_alternate():
    sets = parse_score("6-4 7-6(5)")
    assert regular_games(sets) == 22
    # winner serves first: set 1 (10 games) W 5 / L 5; set 2 still opened by W (10 is even),
    # 12 regular games -> 6 / 6; the tiebreak is not a service game
    assert service_games(sets, True) == (11.0, 11.0)
    sets = parse_score("6-3 6-4")
    # 9 games in set 1 -> the other player opens set 2
    assert serve_plan(sets, True) == [(True, 5, 4), (False, 5, 5)]
    assert service_games(sets, True) == (10.0, 9.0)
    assert service_games(sets, False) == (9.0, 10.0)
    assert service_games(sets) == (9.5, 9.5)                             # unknown first server: expectation


def test_tiebreak_counts_as_one_game_for_alternation():
    sets = parse_score("7-6(4) 6-0")
    # 13 games (tiebreak = 1) is odd -> the player who received first opens set 2
    plan = serve_plan(sets, True)
    assert [p[0] for p in plan] == [True, False]
    assert plan[0][1:] == (6, 6) and plan[1][1:] == (3, 3)


def test_plain_tuples_are_accepted():
    assert regular_games([(6, 4, False), (7, 6, True)]) == 22
    assert serve_plan([(6, 3, False)], True) == [(True, 5, 4)]


def test_score_game_counts_vectorised():
    s = pd.Series(["6-4 7-6(5)", "6-3 2-1 RET", "6-4 3-6 [10-7]"])
    out = score_game_counts(s)
    assert out.valid.tolist() == [True, False, True]
    assert out.loc[0, "service_games"] == 22 and out.loc[0, "tiebreaks"] == 1 and out.loc[0, "games"] == 23
    assert out.loc[2, "service_games"] == 19 and out.loc[2, "n_sets"] == 3
    assert pd.isna(out.loc[1, "service_games"])
    assert score_game_counts(pd.Series(["6-4 3-6 [10-7]"]), allow_match_tiebreak=False).valid.tolist() == [False]


@pytest.mark.parametrize("score", ["6-0 6-0", "7-6(1) 7-6(2) 7-6(3)", "6-4 3-6 7-5 4-6 70-68"])
def test_hypotheses_partition_regular_games(score):
    sets = parse_score(score)
    a = service_games(sets, True)
    b = service_games(sets, False)
    assert sum(a) == sum(b) == regular_games(sets) and a == b[::-1]
