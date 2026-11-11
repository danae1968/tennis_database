"""Match scores (TennisMyLife / Sackmann format) and score-based service-game counts.

Use these instead of ``w_SvGms`` / ``l_SvGms``: those columns are wrong in about 26% of Grand Slam
matches 2016-23 (see ``analyses/serve_first``).

Serve rules used
----------------
* Serve alternates every game, also across set boundaries.
* A tiebreak (7-6, 13-12, or a match tiebreak written ``[10-7]``) counts as ONE game for the
  alternation but is NOT a service game.
* Hence the regular (service) games of a match = sum over sets of (games - 1 if tiebreak set),
  and they split between the two players almost evenly; the exact split needs the first server.

Example: ``6-4 7-6(5)`` has 10 + 12 = 22 service games (11 each if the alternation is even).
"""
from __future__ import annotations

import re
from typing import NamedTuple

import numpy as np
import pandas as pd

SET_RE = re.compile(r"^(\d+)-(\d+)(?:\((\d+)\))?$")
MTB_RE = re.compile(r"^\[(\d+)-(\d+)\]$")


class SetScore(NamedTuple):
    """One set from the match winner's point of view."""
    w: int                  # games (or match-tiebreak points) of the match winner
    l: int                  # games of the match loser
    tiebreak: bool          # set decided by a tiebreak game (incl. a match tiebreak)
    match_tiebreak: bool = False   # the "set" is a match tiebreak such as [10-7]


def parse_score(score: object, allow_match_tiebreak: bool = False) -> list[SetScore] | None:
    """Parse a completed match score into sets; ``None`` if not a clean completed match.

    Rejected: retirements (``RET``), walkovers (``W/O``), defaults, unfinished/malformed sets and,
    unless ``allow_match_tiebreak``, bracketed match tiebreaks such as ``[10-7]``.
    Tiebreak sets are 7-6 or 13-12 (or any n-(n-1) with n-1 >= 6); regular sets are 6-x (x <= 4),
    7-5 or advantage sets with a two-game lead.  The match winner must win the last set.
    """
    if not isinstance(score, str):
        return None
    out: list[SetScore] = []
    for t in score.split():
        m = SET_RE.match(t)
        if m:
            a, b = int(m[1]), int(m[2])
            hi, lo = max(a, b), min(a, b)
            if hi - lo == 1 and lo >= 6:
                out.append(SetScore(a, b, True))
            elif hi >= 6 and hi - lo >= 2 and (hi == 6 or hi - lo == 2):
                out.append(SetScore(a, b, False))
            else:
                return None
            continue
        m = MTB_RE.match(t)
        if m and allow_match_tiebreak:
            a, b = int(m[1]), int(m[2])
            if max(a, b) >= 10 and abs(a - b) >= 2:
                # represented as a one-game "set" won by the winner of the match tiebreak
                out.append(SetScore(1 if a > b else 0, 1 if b > a else 0, True, True))
                continue
        return None
    if not out or out[-1].w < out[-1].l:
        return None
    return out


def regular_games(sets) -> int:
    """Number of service (non-tiebreak) games in the match. ``sets`` are :class:`SetScore` or
    plain ``(w, l, tiebreak)`` tuples."""
    return int(sum(s[0] + s[1] - (1 if s[2] else 0) for s in sets))


def serve_plan(sets, first_is_w: bool) -> list[tuple[bool, int, int]]:
    """Per set: (match winner serves first in this set, regular games served by W, by L),
    given whether the match winner served the first game of the match.  ``sets`` are
    :class:`SetScore` or plain ``(w, l, tiebreak)`` tuples."""
    w_first = first_is_w
    plan = []
    for s in sets:
        a, b, tb = s[0], s[1], s[2]
        n_reg = a + b - (1 if tb else 0)
        n_first, n_second = (n_reg + 1) // 2, n_reg // 2
        sw, sl = (n_first, n_second) if w_first else (n_second, n_first)
        plan.append((w_first, sw, sl))
        if (a + b) % 2 == 1:              # odd number of games (tiebreak = 1 game) -> other player opens next set
            w_first = not w_first
    return plan


def service_games(sets, first_is_w: bool | None = None) -> tuple[float, float]:
    """Service games of (match winner, match loser) from the score.

    If ``first_is_w`` is unknown (``None``), returns the average of the two hypotheses, which is
    exactly half of :func:`regular_games` each; the true split differs from it by at most a few
    games and is unbiased when the first server is a coin toss.  Return games of one player =
    service games of the other.
    """
    if first_is_w is None:
        n = regular_games(sets) / 2
        return n, n
    plan = serve_plan(sets, first_is_w)
    return float(sum(p[1] for p in plan)), float(sum(p[2] for p in plan))


def score_game_counts(scores: pd.Series, allow_match_tiebreak: bool = True) -> pd.DataFrame:
    """Vectorised helper: for each score string, ``valid``, ``n_sets``, ``games`` (incl. tiebreak
    games), ``tiebreaks`` and ``service_games`` (regular games, both players together).
    Invalid / incomplete scores give ``valid=False`` and NaN counts."""
    rows = []
    for s in scores:
        sets = parse_score(s, allow_match_tiebreak=allow_match_tiebreak)
        if sets is None:
            rows.append((False, np.nan, np.nan, np.nan, np.nan))
        else:
            rows.append((True, len(sets), sum(x.w + x.l for x in sets if not x.match_tiebreak)
                         + sum(1 for x in sets if x.match_tiebreak),
                         sum(1 for x in sets if x.tiebreak), regular_games(sets)))
    return pd.DataFrame(rows, columns=["valid", "n_sets", "games", "tiebreaks", "service_games"],
                        index=scores.index)
