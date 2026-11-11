"""Point-by-point (Slam) processing: clock parsing, per-point/game/set/match tables.

Conventions (see README): ``ElapsedTime`` is the match clock at the *start* of the recorded
point (the first point of a match is stamped 0:00:00). Differences between consecutive
stamps are therefore "point cycle times" (the point itself plus the pause before the next one).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np
import pandas as pd

from tennis.load import gender_from_match_id as _gender_code
from tennis.load import read_slam_points, slam_points_path

# --- thresholds (all documented in the README) ---
MAX_POINT_CYCLE_S = 120      # consecutive-point gap above this is not a normal point cycle
MAX_GAME_S = 900             # start-to-start game duration cap (15 min)
INTERRUPTION_S = 600         # any consecutive-stamp gap above this marks a game/set/match as interrupted
CLOCK_RE = r"^(\d+):(\d{2}):(\d{2})$"


def parse_clock(s: pd.Series) -> pd.Series:
    """Parse ``H:MM:SS`` to seconds (float); malformed/missing values (e.g. '0', '1:55:4') become NaN."""
    p = s.astype("string").str.strip().str.extract(CLOCK_RE).astype(float)
    sec = p[0] * 3600 + p[1] * 60 + p[2]
    return sec.where((p[1] < 60) & (p[2] < 60))


def gender_from_match_id(match_id: pd.Series) -> pd.Series:
    """'men' / 'women' from match ids such as ``2023-usopen-1101`` (shared rule in :mod:`tennis.load`)."""
    return _gender_code(match_id).map({"M": "men", "W": "women"})


def is_tiebreak_game(n_servers, g1, g2) -> pd.Series:
    """A tiebreak is a game in which *both* players served, ending at 7-6 or 13-12 in games.

    (A regular game that happens to finish a set 7-6 or 13-12 has a single server, so it is
    not flagged; this matters for advantage final sets.)
    """
    tot = g1 + g2
    return (n_servers == 2) & ((tot == 13) | (tot == 25))


def legal_set_score(g1, g2) -> pd.Series:
    """Whether (g1, g2) is a legal *final* set score: 6-0..6-4, 7-5, 7-6, 13-12 (12-12 tiebreak) or an advantage set (>=8, lead of 2)."""
    hi = np.maximum(g1, g2); lo = np.minimum(g1, g2)
    return ((hi == 6) & (lo <= 4)) | ((hi == 7) & ((lo == 5) | (lo == 6))) | ((hi >= 8) & (hi - lo == 2)) | ((hi == 13) & (lo == 12))


def read_points(path) -> pd.DataFrame:
    """Read one ``*-points.csv`` keeping real points only (drops ``0X``/``0Y`` placeholder rows)."""
    cols = ["match_id", "ElapsedTime", "SetNo", "GameNo", "PointNumber", "SetWinner", "P1GamesWon", "P2GamesWon", "PointServer"]
    d = read_slam_points(path, usecols=cols)
    n_raw = len(d)
    d = d[d["PointNumber"].str.fullmatch(r"\d+").fillna(False)].copy()
    d["sec"] = parse_clock(d["ElapsedTime"])
    for c in ("SetNo", "GameNo", "SetWinner", "P1GamesWon", "P2GamesWon", "PointServer"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d.dropna(subset=["SetNo", "GameNo"]).drop(columns=["ElapsedTime", "PointNumber"]).reset_index(drop=True)
    d.attrs["n_raw"] = n_raw
    return d


def add_point_cycle(d: pd.DataFrame) -> pd.DataFrame:
    """Add game id, raw gap to the previous point, and cleaned within-game cycle time ``dt``.

    ``dt`` is NaN for the first point of a game, when a clock value is missing, or when the gap is
    <= 0 s (clock did not tick) or > ``MAX_POINT_CYCLE_S``.
    """
    d = d.copy()
    key = d["match_id"] + "|" + d["SetNo"].astype(int).astype(str) + "|" + d["GameNo"].astype(int).astype(str)
    d["gid"] = (key != key.shift()).cumsum()
    d["raw_gap"] = d["sec"].diff().where(d["match_id"] == d["match_id"].shift())
    same_game = d["gid"] == d["gid"].shift()
    d["dt"] = d["raw_gap"].where(same_game)
    d["dt_status"] = np.select([d["dt"].isna(), d["dt"] <= 0, d["dt"] > MAX_POINT_CYCLE_S], ["na", "zero_or_neg", "too_long"], "ok")
    d.loc[d["dt_status"] != "ok", "dt"] = np.nan
    return d


def game_table(d: pd.DataFrame) -> pd.DataFrame:
    """One row per game: points, tiebreak flag, start-to-next-start duration (no-changeover games only)."""
    g = d.groupby("gid", sort=False)
    t = g.agg(match_id=("match_id", "first"), set_no=("SetNo", "first"), game_no=("GameNo", "first"),
              n_points=("sec", "size"), first_sec=("sec", "first"), g1=("P1GamesWon", "last"), g2=("P2GamesWon", "last"),
              n_servers=("PointServer", "nunique"), max_gap=("raw_gap", "max")).reset_index()
    nxt_sec = d["sec"].shift(-1).groupby(d["gid"]).last()        # stamp of the point after the game's last point
    nxt_set = d["SetNo"].shift(-1).groupby(d["gid"]).last()
    nxt_match = d["match_id"].shift(-1).groupby(d["gid"]).last()
    t["next_sec"] = t["gid"].map(nxt_sec)
    same_set = (t["gid"].map(nxt_set) == t["set_no"]) & (t["gid"].map(nxt_match) == t["match_id"])
    games_done = t["g1"] + t["g2"]
    t["is_tiebreak"] = is_tiebreak_game(t["n_servers"], t["g1"], t["g2"])
    # no changeover follows a game after which an even number of games have been played in the set
    t["clean_for_duration"] = same_set & (games_done % 2 == 0) & ~t["is_tiebreak"]
    t["duration"] = (t["next_sec"] - t["first_sec"]).where(t["clean_for_duration"])
    bad = (t["duration"] <= 0) | (t["duration"] > MAX_GAME_S) | (t["max_gap"] > INTERRUPTION_S)
    t.loc[bad.fillna(False), "duration"] = np.nan
    return t


def set_table(d: pd.DataFrame) -> pd.DataFrame:
    """One row per set: points, games, duration first-to-last point stamp, interruption flag."""
    g = d.groupby(["match_id", "SetNo"], sort=False)
    t = g.agg(n_points=("sec", "size"), first_sec=("sec", "first"), last_sec=("sec", "last"),
              g1=("P1GamesWon", "last"), g2=("P2GamesWon", "last"), file_set_winner=("SetWinner", "max"),
              max_gap=("raw_gap", "max"), n_nan=("sec", lambda s: int(s.isna().sum()))).reset_index()
    t["n_games"] = t["g1"] + t["g2"]
    t["legal"] = legal_set_score(t["g1"], t["g2"])
    # winner from the games count (SetWinner is missing at the end of many final-set tiebreaks and
    # carries spurious flags in long advantage sets); an illegal final score = unfinished set
    t["winner"] = np.where(t["legal"], np.where(t["g1"] > t["g2"], 1, 2), 0)
    t["duration"] = t["last_sec"] - t["first_sec"]
    t.loc[(t["n_nan"] > 0) | (t["max_gap"] > INTERRUPTION_S) | (t["duration"] <= 0), "duration"] = np.nan
    return t.rename(columns={"SetNo": "set_no"})


def match_table(d: pd.DataFrame, sets: pd.DataFrame) -> pd.DataFrame:
    """One row per match: gender, points, sets, completeness, clock duration (if clean)."""
    g = d.groupby("match_id", sort=False)
    m = g.agg(n_points=("sec", "size"), last_sec=("sec", "max"), max_gap=("raw_gap", "max"),
              n_nan=("sec", lambda s: int(s.isna().sum()))).reset_index()
    m["gender"] = gender_from_match_id(m["match_id"])
    m["round_no"] = pd.to_numeric(m["match_id"].str.rsplit("-", n=1).str[-1].str[1], errors="coerce")   # 2nd digit of the match number = round
    wins = sets.groupby("match_id")["winner"].agg(s1=lambda w: int((w == 1).sum()), s2=lambda w: int((w == 2).sum()))
    m = m.join(wins, on="match_id")
    m["n_sets"] = m["match_id"].map(sets.groupby("match_id").size())
    need = np.where(m["gender"] == "men", 3, 2)               # Slam singles: men best of 5, women best of 3
    m["best_of"] = np.where(m["gender"] == "men", 5, 3)
    m["complete"] = np.maximum(m["s1"], m["s2"]) >= need
    ok_clock = (m["n_nan"] == 0) & (m["max_gap"] <= INTERRUPTION_S) & (m["last_sec"] > 0)
    m["duration"] = m["last_sec"].where(ok_clock)
    return m


@dataclass
class Slam:
    """Processed tables for all singles files."""
    points: pd.DataFrame
    games: pd.DataFrame
    sets: pd.DataFrame
    matches: pd.DataFrame
    coverage: pd.DataFrame


def process_slam_files(years: range, slams=("ausopen", "frenchopen", "wimbledon", "usopen")) -> Slam:
    """Process every singles points file in ``years`` and concatenate the per-level tables."""
    P, G, S, M, cov = [], [], [], [], []
    for y in years:
        for s in slams:
            f = slam_points_path(y, s)
            if not f.exists():
                continue
            raw = read_points(f)
            usable = bool(raw["sec"].notna().mean() > 0.5 and raw["SetWinner"].notna().any() and raw["P1GamesWon"].notna().any())
            cov.append({"year": y, "slam": s, "matches": raw["match_id"].nunique(), "points": len(raw),
                        "raw_rows": raw.attrs["n_raw"], "clock_share": round(float(raw["sec"].notna().mean()), 3), "used": usable})
            if not usable:       # AO/FO 2018-21 (Infosys feed): no clock, no GamesWon/SetWinner columns
                continue
            d = add_point_cycle(raw)
            sets, games = set_table(d), game_table(d)
            mt = match_table(d, sets)
            keep = d[["match_id", "dt", "dt_status"]].copy()
            for t in (keep, games, sets, mt):
                t["year"] = y; t["slam"] = s
            keep["gender"] = gender_from_match_id(keep["match_id"])
            for t in (games, sets):
                t["gender"] = gender_from_match_id(t["match_id"])
            P.append(keep); G.append(games); S.append(sets); M.append(mt)
    return Slam(pd.concat(P, ignore_index=True), pd.concat(G, ignore_index=True),
                pd.concat(S, ignore_index=True), pd.concat(M, ignore_index=True), pd.DataFrame(cov))
