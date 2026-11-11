"""TennisMyLife match frame for the ace and break trends (WTA, ATP, Challenger; 2016-2026).

One row per completed match with both players' serve stats.  Service games come from the score
(:mod:`tennis.scores`; tiebreaks are not service games), never from ``w_SvGms``/``l_SvGms``, which
are wrong in about 26% of Grand Slam matches 2016-23.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from tennis.load import load_tml_years
from tennis.scores import score_game_counts

YEARS = range(2016, 2027)
PARTIAL_YEAR = 2026                 # season still running when the data were downloaded
TOURS = ("WTA", "ATP", "Challenger")          # display order: WTA first
SURFACES = ("Hard", "Clay", "Grass", "Carpet")
TEAM_LEVELS = {"D"}                 # Davis Cup / Billie Jean King Cup: excluded

COLS = ["tourney_id", "tourney_name", "tourney_date", "tourney_level", "surface", "score", "round",
        "best_of", "winner_rank", "loser_rank", "w_ace", "l_ace", "w_svpt", "l_svpt",
        "w_bpFaced", "w_bpSaved", "l_bpFaced", "l_bpSaved"]


def build_match_frame(raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Clean TML rows into the analysis frame; returns (frame, cleaning log).

    Steps: drop team events; keep completed matches (score parses; match tiebreaks allowed);
    require serve stats; drop internally inconsistent rows (aces > serve points, saved > faced,
    breaks > service games).  Derived per match (both players together): ``aces``, ``svpt``,
    ``breaks`` (= sum of bpFaced - bpSaved), ``bp_faced``, ``service_games`` (from the score).
    """
    log = [("match rows (ATP, WTA, Challenger files)", len(raw))]
    d = raw[~raw["tourney_level"].isin(TEAM_LEVELS)].copy()
    log.append(("  removed: team events (Davis Cup, BJK Cup)", len(raw) - len(d)))
    g = score_game_counts(d["score"], allow_match_tiebreak=True)
    d = pd.concat([d, g], axis=1)
    n0 = len(d)
    d = d[d["valid"]].copy()
    log.append(("  removed: retirement / walkover / unparseable score", n0 - len(d)))
    stat_cols = ["w_ace", "l_ace", "w_svpt", "l_svpt", "w_bpFaced", "w_bpSaved", "l_bpFaced", "l_bpSaved"]
    n0 = len(d)
    d = d[d[stat_cols].notna().all(axis=1) & (d["w_svpt"] > 0) & (d["l_svpt"] > 0)].copy()
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


def load_matches(years=YEARS) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load and clean the TML match files for ``years`` (see :func:`build_match_frame`)."""
    raw = load_tml_years(years, kinds=("ATP", "WTA", "Challenger"), usecols=COLS, text=False)
    return build_match_frame(raw)
