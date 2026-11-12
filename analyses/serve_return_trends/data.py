"""TennisMyLife match frame for the ace and break trends (WTA 2009-, ATP 1991-, Challenger 2010-; to 2026).

One row per completed match with both players' serve stats.  Each tour starts in its first season with
near-complete serve statistics (see :func:`coverage_table`): WTA files have stats only for the Slams before
2006 and for 77-80% of matches, selectively the higher-ranked ones, in 2007-08; Challenger files have none
before 2010.  Service games come from the score
(:mod:`tennis.scores`; tiebreaks are not service games), never from ``w_SvGms``/``l_SvGms``, which
are wrong in about 26% of Grand Slam matches 2016-23.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from tennis.load import load_tml_years
from tennis.scores import score_game_counts

YEARS = range(1991, 2027)
START = {"WTA": 2009, "ATP": 1991, "Challenger": 2010}   # first season used, per tour
RECENT = (2016, 2025)               # "the last ten full seasons", reported next to the whole period
PARTIAL_YEAR = 2026                 # season still running when the data were downloaded
TOURS = ("WTA", "ATP", "Challenger")          # display order
SURFACES = ("Hard", "Clay", "Grass", "Carpet")
TEAM_LEVELS = {"D"}                 # Davis Cup / Billie Jean King Cup: excluded

COLS = ["tourney_id", "tourney_name", "tourney_date", "tourney_level", "surface", "score", "round",
        "best_of", "winner_rank", "loser_rank", "w_ace", "l_ace", "w_svpt", "l_svpt",
        "w_bpFaced", "w_bpSaved", "l_bpFaced", "l_bpSaved"]


STAT_COLS = ["w_ace", "l_ace", "w_svpt", "l_svpt", "w_bpFaced", "w_bpSaved", "l_bpFaced", "l_bpSaved"]


def completed_matches(raw: pd.DataFrame, log: list | None = None) -> pd.DataFrame:
    """Non-team, completed matches (score parses; match tiebreaks allowed) with the score's game counts
    and ``has_stats`` (all serve statistics present, serve points > 0).  Appends steps to ``log``."""
    d = raw[~raw["tourney_level"].isin(TEAM_LEVELS)].copy()
    if log is not None:
        log.append(("  removed: team events (Davis Cup, BJK Cup)", len(raw) - len(d)))
    g = score_game_counts(d["score"], allow_match_tiebreak=True)
    d = pd.concat([d, g], axis=1)
    n0 = len(d)
    d = d[d["valid"]].copy()
    if log is not None:
        log.append(("  removed: retirement / walkover / unparseable score", n0 - len(d)))
    d["has_stats"] = d[STAT_COLS].notna().all(axis=1) & (d["w_svpt"] > 0) & (d["l_svpt"] > 0)
    return d


def coverage_table(raw: pd.DataFrame) -> pd.DataFrame:
    """Share of completed tour-level matches with serve statistics, per tour and year, plus the median
    better-ranked player's rank in covered and uncovered matches (is missingness selective?)."""
    d = completed_matches(raw)
    d["better_rank"] = d[["winner_rank", "loser_rank"]].min(axis=1)
    g = d.groupby(["tour", "year"])
    out = g.agg(matches=("has_stats", "size"), with_stats=("has_stats", "sum")).reset_index()
    out["share"] = out["with_stats"] / out["matches"]
    med = d.groupby(["tour", "year", "has_stats"])["better_rank"].median().unstack()
    med = med.reindex(columns=[True, False]).rename(columns={True: "median_rank_covered", False: "median_rank_missing"})
    out = out.merge(med.reset_index(), on=["tour", "year"], how="left")
    out["used"] = out["year"] >= out["tour"].map(START)
    return out


def build_match_frame(raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Clean TML rows into the analysis frame; returns (frame, cleaning log).

    Steps: drop seasons before each tour's start (:data:`START`); drop team events; keep completed matches (score parses; match tiebreaks allowed);
    require serve stats; drop internally inconsistent rows (aces > serve points, saved > faced,
    breaks > service games).  Derived per match (both players together): ``aces``, ``svpt``,
    ``breaks`` (= sum of bpFaced - bpSaved), ``bp_faced``, ``service_games`` (from the score).
    """
    log = [("match rows (ATP, WTA, Challenger files)", len(raw))]
    first = raw["tour"].map(START).fillna(0)
    early = raw["year"] < first
    log.append(("  removed: seasons before reliable serve stats (WTA < 2009, Challenger < 2010)", int(early.sum())))
    d = completed_matches(raw[~early], log)
    n0 = len(d)
    d = d[d["has_stats"]].copy()
    log.append(("  removed: serve statistics missing", n0 - len(d)))
    d["aces"] = d["w_ace"] + d["l_ace"]
    d["svpt"] = d["w_svpt"] + d["l_svpt"]
    d["breaks"] = (d["w_bpFaced"] - d["w_bpSaved"]) + (d["l_bpFaced"] - d["l_bpSaved"])
    d["bp_faced"] = d["w_bpFaced"] + d["l_bpFaced"]
    bad = ((d["aces"] > d["svpt"]) | (d["w_bpSaved"] > d["w_bpFaced"]) | (d["l_bpSaved"] > d["l_bpFaced"])
           | (d["breaks"] > d["service_games"]) | (d["service_games"] <= 0))
    log.append(("  removed: inconsistent stats (aces > points, saved > faced, breaks > games)", int(bad.sum())))
    d = d[~bad].copy()
    log.append(("matches used", len(d)))
    d["partial_year"] = d["year"] == PARTIAL_YEAR
    d["surface"] = d["surface"].where(d["surface"].isin(SURFACES))
    for num, den, rate in (("aces", "svpt", "ace_rate"), ("breaks", "service_games", "break_rate"),
                           ("breaks", "bp_faced", "bp_conversion")):
        d[rate] = np.where(d[den] > 0, d[num] / d[den], np.nan)
    d["edition"] = d["tourney_id"].astype(str)                       # one tournament in one year
    # the same tournament across years (name-based; ids change between years on some tours)
    d["tournament"] = d["tour"] + "|" + d["tourney_name"].astype(str).str.lower().str.replace(r"[^a-z0-9]", "", regex=True)
    return d.reset_index(drop=True), pd.DataFrame(log, columns=["step", "count"])


def load_raw(years=YEARS) -> pd.DataFrame:
    """The raw TML ATP, WTA and Challenger rows for ``years`` (analysis columns only)."""
    return load_tml_years(years, kinds=("ATP", "WTA", "Challenger"), usecols=COLS, text=False)


def load_matches(years=YEARS) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load and clean the TML match files for ``years`` (see :func:`build_match_frame`)."""
    return build_match_frame(load_raw(years))
