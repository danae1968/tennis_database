"""From points to games to sets: who served first in each set, who won it, and data-quality flags.

Tennis serve-order rules used throughout
---------------------------------------
* Serve alternates every game, also across set boundaries.
* A tiebreak counts as ONE game for this alternation: the player who served the first point of the
  tiebreak is the player whose turn it was, and the player who *received* first in the tiebreak
  serves the first game of the next set.  Hence, within a set, the first server of the set serves
  every odd-numbered game (including the tiebreak at 6-6 = game 13, or 12-12 = game 25), and the
  first server of set k+1 equals the first server of set k iff set k had an even number of games
  (tiebreak counted as one game, i.e. games = winner's games + loser's games as in the score).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def is_valid_set_score(w: int, l: int, tiebreak: bool) -> bool:
    """True if (winner games ``w``, loser games ``l``) is a legal completed-set score.

    Covers 6-x, 7-5, tiebreak sets 7-6 (TB at 6-6) and 13-12 (TB at 12-12, Wimbledon final sets
    2019-21), and advantage sets (8-6, 10-8, 70-68 ...).
    """
    if w <= l:
        return False
    if tiebreak:
        return w - l == 1 and w in (7, 13)
    if w == 6:
        return l <= 4
    return w >= 7 and w - l == 2


def next_set_first_server(first_server: int, winner_games: int, loser_games: int) -> int:
    """First server (1 or 2) of the next set given this set's first server and final score.

    The tiebreak is already counted once in the score (7-6), so parity of the total decides.
    """
    return first_server if (winner_games + loser_games) % 2 == 0 else 3 - first_server


def renumber_games(P: pd.DataFrame) -> pd.DataFrame:
    """Add ``game_in_set`` (1-based game number within the set).

    Most files number games within each set.  The Infosys-sourced files (AO and FO 2018-21) number
    games cumulatively over the match (set 2 starts at game 10 after a 6-3 set).  A match is treated
    as cumulatively numbered when the majority of its sets after set 1 start above game 1; the offset
    of set k is then the last game number recorded in set k-1.
    """
    keys = ["match_id", "SetNo"]
    rng = P.groupby(keys).GameNo.agg(["min", "max"]).reset_index()
    rng["prev_max"] = rng.groupby("match_id")["max"].shift(1)
    later = rng[rng.SetNo > 1]
    cum = (later.assign(c=later["min"] > 1).groupby("match_id").c.mean() > 0.5)
    rng["cumulative"] = rng.match_id.map(cum).fillna(False).astype(bool)
    rng["offset"] = np.where(rng.cumulative & (rng.SetNo > 1), rng.prev_max.fillna(0), 0).astype(int)
    P = P.merge(rng[keys + ["offset", "cumulative"]], on=keys, how="left")
    P["game_in_set"] = P.GameNo - P.offset
    return P.drop(columns=["offset"])


def build_games(P: pd.DataFrame) -> pd.DataFrame:
    """One row per (match, set, game) with server, winner, games score before it and tiebreak flag.

    The game winner is ``GameWinner`` where the file records it, otherwise the ``PointWinner`` of
    the game's last point (Infosys files have no GameWinner/SetWinner/GamesWon columns filled).
    The score before each game is rebuilt by counting game winners, so all files are treated alike.
    """
    if "game_in_set" not in P.columns:
        P = renumber_games(P)
    keys = ["match_id", "SetNo", "game_in_set"]
    g = P.groupby(keys, sort=True)
    G = g.agg(first_server=("PointServer", "first"), n_servers=("PointServer", "nunique"),
              n_points=("PointNumber", "size"), last_point_winner=("PointWinner", "last"),
              cumulative=("cumulative", "first")).reset_index()
    gw = P[P.GameWinner.isin([1, 2])].groupby(keys).GameWinner.last()
    G = G.merge(gw.rename("gw_col").reset_index(), how="left", on=keys)
    G["game_winner"] = np.where(G.gw_col.notna(), G.gw_col.fillna(0),
                                np.where(G.last_point_winner.isin([1, 2]), G.last_point_winner, 0)).astype(int)
    G["GameNo"] = G.game_in_set
    G["w1"] = (G.game_winner == 1).astype(int)
    G["w2"] = (G.game_winner == 2).astype(int)
    G["wu"] = (G.game_winner == 0).astype(int)
    s = G.groupby(["match_id", "SetNo"])
    G["p1_before"] = s.w1.cumsum() - G.w1
    G["p2_before"] = s.w2.cumsum() - G.w2
    tied_late = (G.p1_before == G.p2_before) & (G.p1_before >= 6)
    # Tiebreak: both players serve within the game, at a tied score of 6-6 or more.  (In advantage
    # final sets, games at 6-6, 7-7, ... are ordinary single-server games.)
    G["is_tb"] = (G.n_servers > 1) & tied_late
    # A regular game with two different servers (not at a tiebreak score) is a data error.
    G["server_error"] = (G.n_servers > 1) & ~tied_late
    G["short_game"] = (~G.is_tb) & (G.n_points < 4)
    return G.drop(columns=["gw_col"])


def _set_first_server_parity(G: pd.DataFrame) -> pd.DataFrame:
    """Implied first server of each set from every game: odd games are served by the set's first server."""
    implied = np.where(G.GameNo % 2 == 1, G.first_server, 3 - G.first_server)
    T = G.assign(implied=implied)
    T = T[~T.server_error]
    agg = T.assign(v1=(T.implied == 1).astype(int)).groupby(["match_id", "SetNo"]).agg(
        n_votes=("v1", "size"), n_votes_1=("v1", "sum"))
    agg["fs_parity"] = np.where(agg.n_votes_1 * 2 > agg.n_votes, 1, np.where(agg.n_votes_1 * 2 < agg.n_votes, 2, 0))
    agg["parity_conflicts"] = np.minimum(agg.n_votes_1, agg.n_votes - agg.n_votes_1)
    return agg.reset_index()


def build_sets(P: pd.DataFrame, G: pd.DataFrame | None = None) -> pd.DataFrame:
    """One row per (match, set): first server, set winner, final score, and quality flags.

    Columns
    -------
    fs_direct       server of the first recorded point of game 1 of the set (0 if game 1 missing)
    fs_parity       first server implied by the servers of all recorded games (0 if tied vote)
    fs              final first-server call: fs_direct if available, else fs_parity
    g1, g2          final games of player 1 / player 2, counted from game winners
    set_winner      1/2 if the counted score is a legal completed set, else 0 (unfinished set)
    sw_disagree     the file's own SetWinner column contradicts the counted winner
    n_missing_games games implied by the score with no recorded points (gaps in game numbering)
    """
    if G is None:
        G = build_games(P)
    keys = ["match_id", "SetNo"]
    S = G.groupby(keys).agg(min_game=("GameNo", "min"), max_game=("GameNo", "max"), n_games_obs=("GameNo", "size"),
                            has_tb=("is_tb", "any"), n_server_errors=("server_error", "sum"),
                            n_short_games=("short_game", "sum"), n_points=("n_points", "sum"),
                            g1=("w1", "sum"), g2=("w2", "sum"), n_unknown_game_winner=("wu", "sum"),
                            cumulative=("cumulative", "first")).reset_index()
    g1 = G[G.GameNo == 1].set_index(keys).first_server.rename("fs_direct")
    S = S.merge(g1.reset_index(), how="left", on=keys)
    S["fs_direct"] = S.fs_direct.fillna(0).astype(int)
    S = S.merge(_set_first_server_parity(G), how="left", on=keys)
    S["fs_parity"] = S.fs_parity.fillna(0).astype(int)
    S["parity_conflicts"] = S.parity_conflicts.fillna(0).astype(int)
    S["fs"] = np.where(S.fs_direct > 0, S.fs_direct, S.fs_parity)

    hi, lo = np.maximum(S.g1, S.g2), np.minimum(S.g1, S.g2)
    S["legal_score"] = [is_valid_set_score(int(a), int(b), bool(t)) for a, b, t in zip(hi, lo, S.has_tb)]
    S["set_winner"] = np.where(S.legal_score, np.where(S.g1 > S.g2, 1, 2), 0)
    # Cross-check against the file's SetWinner column where it exists.
    sw = P[P.SetWinner.isin([1, 2])].groupby(keys).SetWinner.last().rename("sw_col")
    S = S.merge(sw.reset_index(), how="left", on=keys)
    S["has_sw_col"] = S.sw_col.notna()
    S["sw_disagree"] = S.has_sw_col & S.legal_score & (S.sw_col != S.set_winner)
    S["n_missing_games"] = (S.max_game - S.n_games_obs).clip(lower=0)
    return S.drop(columns=["sw_col", "n_votes", "n_votes_1"])


def add_match_context(S: pd.DataFrame, M: pd.DataFrame) -> pd.DataFrame:
    """Attach match metadata, set order, previous-set information and the cross-set parity check.

    Adds: set_no (1..n), prev_winner, prev_games (total games of the previous set), predicted_fs from the
    previous set (0 if not predictable), fs_won (first server won this set), complete_match, retired.
    """
    S = S.merge(M[["match_id", "year", "slam", "surface", "gender", "best_of", "player1", "player2"]],
                on="match_id", how="inner")
    S = S.sort_values(["match_id", "SetNo"]).reset_index(drop=True)
    S["set_no"] = S.SetNo
    grp = S.groupby("match_id")
    S["prev_fs"] = grp.fs.shift(1).fillna(0).astype(int)
    S["prev_winner"] = grp.set_winner.shift(1).fillna(0).astype(int)
    S["prev_games"] = (grp.g1.shift(1) + grp.g2.shift(1)).fillna(-1).astype(int)
    prev_ok = (S.prev_fs > 0) & (S.prev_winner > 0) & (S.SetNo == grp.SetNo.shift(1).fillna(-9) + 1)
    pred = np.where(S.prev_games % 2 == 0, S.prev_fs, 3 - S.prev_fs)
    S["predicted_fs"] = np.where(prev_ok, pred, 0)
    S["fs_won"] = (S.fs == S.set_winner) & (S.set_winner > 0)
    # match completion
    won1 = (S.set_winner == 1).groupby(S.match_id).transform("sum")
    won2 = (S.set_winner == 2).groupby(S.match_id).transform("sum")
    need = np.where(S.best_of == 5, 3, 2)
    S["complete_match"] = (np.maximum(won1, won2) == need) & (np.minimum(won1, won2) < need)
    S["match_winner"] = np.where(S.complete_match, np.where(won1 > won2, 1, 2), 0)
    S["n_sets_match"] = grp.SetNo.transform("max")
    S["is_final_set"] = S.SetNo == S.best_of
    return S


def flag_usable(S: pd.DataFrame) -> pd.DataFrame:
    """Decide which sets enter the analysis and record the reason for each exclusion.

    A set is usable if it was completed (known winner, legal score), its first server is known
    (game 1 recorded, or unambiguous from the other games' servers), and the direct and
    parity-based first-server calls do not contradict each other.
    """
    reason = pd.Series("ok", index=S.index, dtype=object)
    reason[S.n_server_errors > 0] = "server changes inside a regular game"
    reason[(S.fs_direct > 0) & (S.fs_parity > 0) & (S.fs_direct != S.fs_parity)] = "first-server conflict"
    reason[S.fs == 0] = "first server unknown"
    # NB: ``sw_disagree`` is *not* an exclusion: in long advantage final sets the files carry spurious
    # SetWinner flags at 7-6, 8-7, ... and none at the real end; the counted score is correct.
    reason[S.set_winner == 0] = "set not completed (retirement/truncated/missing games)"
    S = S.copy()
    S["exclude_reason"] = reason
    S["usable"] = reason == "ok"
    return S
