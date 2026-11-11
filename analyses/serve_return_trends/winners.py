"""Winners (excluding aces) and unforced errors per point from two sources.

(a) Grand Slam point-by-point (``pbp-data/slam``), 2016-2024: every point of the covered matches.
    Point flags ``P1Winner``/``P2Winner`` INCLUDE aces in the IBM "Slamtracker" files (every ace is
    also flagged as a winner) but EXCLUDE them in the Infosys files (AO and RG 2018-21: an ace is
    never also a winner).  "Winner excluding aces" = winner flag AND NOT ace flag is correct for both.
(b) Match Charting Project (``pbp-data/charting``), 2016-2026: Overview ``winners`` INCLUDES aces
    (winners >= aces + forehand + backhand winners in every one of 23,624 player-match rows), so
    winners excluding aces = ``winners - aces``.  Points = sum of both players' ``serve_pts``.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from tennis.load import gender_from_match_id, load_charting, read_slam_points, slam_singles_files
from tennis.names import names_match
from tennis.paths import SLAM_SURFACE

PBP_YEARS = range(2016, 2025)
CHART_YEARS = range(2016, 2027)
SLAM_ROUND = {1: "R128", 2: "R64", 3: "R32", 4: "R16", 5: "QF", 6: "SF", 7: "F"}
CHART_SLAMS = {"Australian Open": "ausopen", "Roland Garros": "frenchopen", "Wimbledon": "wimbledon",
               "US Open": "usopen"}
PBP_COLS = ["match_id", "PointNumber", "P1Ace", "P2Ace", "P1Winner", "P2Winner", "P1UnfErr", "P2UnfErr"]


def provider(year: int, slam: str) -> str:
    """'Infosys' for the AO/RG 2018-21 feeds, else 'IBM' (Slamtracker)."""
    return "Infosys" if slam in ("ausopen", "frenchopen") and 2018 <= year <= 2021 else "IBM"


def pbp_point_flags(p: pd.DataFrame) -> pd.DataFrame:
    """Per-point 0/1 flags ``ace``, ``winner_ex_ace`` and ``ue`` from raw (text) point rows.
    Placeholder rows (non-numeric or zero PointNumber) are dropped."""
    pn = pd.to_numeric(p["PointNumber"], errors="coerce")
    p = p[pn > 0].copy()
    num = {c: pd.to_numeric(p[c], errors="coerce").fillna(0) for c in PBP_COLS[2:]}
    ace = (num["P1Ace"] == 1) | (num["P2Ace"] == 1)
    win = (num["P1Winner"] == 1) | (num["P2Winner"] == 1)
    ue = (num["P1UnfErr"] == 1) | (num["P2UnfErr"] == 1)
    return pd.DataFrame({"match_id": p["match_id"].values, "ace": ace.astype(int).values,
                         "winner_ex_ace": (win & ~ace).astype(int).values, "ue": ue.astype(int).values,
                         "winner_and_ace": (win & ace).astype(int).values})


def load_pbp_matches(years=PBP_YEARS) -> pd.DataFrame:
    """One row per Slam singles match: points, aces, winners excluding aces, unforced errors, plus
    year, slam, surface, gender ('W'/'M'), round, provider, and the player names."""
    frames = []
    for y, slam, mf, pf in slam_singles_files():
        if y not in years:
            continue
        flags = pbp_point_flags(read_slam_points(pf, usecols=PBP_COLS))
        agg = flags.groupby("match_id").agg(points=("ace", "size"), aces=("ace", "sum"),
                                            winners_ex=("winner_ex_ace", "sum"), ue=("ue", "sum"),
                                            winner_and_ace=("winner_and_ace", "sum")).reset_index()
        meta = pd.read_csv(mf, dtype=str)[["match_id", "match_num", "player1", "player2"]]
        agg = agg.merge(meta, on="match_id", how="left")
        agg["year"], agg["slam"], agg["provider"] = y, slam, provider(y, slam)
        frames.append(agg)
    d = pd.concat(frames, ignore_index=True)
    d["surface"] = d["slam"].map(SLAM_SURFACE)
    d["gender"] = gender_from_match_id(d["match_id"])
    rd = pd.to_numeric(d["match_num"].astype(str).str[1], errors="coerce")
    d["round"] = rd.map(SLAM_ROUND)
    d["event"] = d["year"].astype(str) + "-" + d["slam"]
    # matches whose winner/UE flags are all zero over many points are missing those annotations
    d["annotated"] = ~((d["winners_ex"] == 0) & (d["ue"] == 0) & (d["points"] >= 40))
    return d[d["gender"].notna()].reset_index(drop=True)


def _clean_tournament(s: pd.Series) -> pd.Series:
    return s.astype(str).str.replace("_", " ", regex=False).str.strip()


def charting_totals(overview: pd.DataFrame) -> pd.DataFrame:
    """Per charted match (both players together) from Overview rows: points (sum of serve points),
    aces, winners (incl. aces), winners_ex (= winners - aces) and ue.  Only 'Total' rows of matches
    with exactly two players are used."""
    o = overview[overview["set"] == "Total"].copy()
    for c in ("serve_pts", "aces", "winners", "unforced"):
        o[c] = pd.to_numeric(o[c], errors="coerce")
    agg = o.groupby("match_id").agg(points=("serve_pts", "sum"), aces=("aces", "sum"), winners=("winners", "sum"),
                                    ue=("unforced", "sum"), n_players=("player", "size")).reset_index()
    agg = agg[agg["n_players"] == 2].copy()
    agg["winners_ex"] = agg["winners"] - agg["aces"]
    return agg


def load_charting_matches(years=CHART_YEARS) -> pd.DataFrame:
    """One row per charted match: points, aces, winners excluding aces, unforced errors, with year,
    gender, surface, tournament, round, best_of and the volunteer who charted it (``charter``).  Juniors events and unknown surfaces are dropped."""
    agg = charting_totals(load_charting("stats-Overview"))
    m = load_charting("matches")
    m = m.rename(columns={"Player 1": "player1", "Player 2": "player2", "Surface": "surface",
                          "Tournament": "tournament", "Round": "round", "Best of": "best_of", "Charted by": "charter"})
    m["charter"] = m["charter"].fillna("unknown").astype(str).str.strip()
    m["year"] = pd.to_numeric(m["Date"].astype(str).str[:4], errors="coerce")
    m["tournament"] = _clean_tournament(m["tournament"])
    m["round"] = m["round"].astype(str).str.strip()
    d = agg.merge(m[["match_id", "gender", "year", "surface", "tournament", "round", "best_of", "player1", "player2", "charter"]],
                  on="match_id", how="inner")
    d = d[d["year"].notna()].copy()
    d["year"] = d["year"].astype(int)
    d = d[d["year"].isin(list(years)) & d["surface"].isin(["Hard", "Clay", "Grass", "Carpet"])
          & ~d["tournament"].str.contains("Junior", case=False) & (d["points"] > 0)]
    d["slam"] = d["tournament"].map(CHART_SLAMS)
    return d.reset_index(drop=True)


def link_charting_to_pbp(ch: pd.DataFrame, pbp: pd.DataFrame) -> pd.DataFrame:
    """Pairs (charting match, pbp match) for the same Slam, year, gender and pair of players."""
    out = []
    chs = ch[ch["slam"].notna() & ch["year"].isin(list(PBP_YEARS))]
    for (y, slam, g), cc in chs.groupby(["year", "slam", "gender"]):
        pp = pbp[(pbp["year"] == y) & (pbp["slam"] == slam) & (pbp["gender"] == g)]
        for r in cc.itertuples():
            hits = pp[[(names_match(a, r.player1) and names_match(b, r.player2)) or
                       (names_match(a, r.player2) and names_match(b, r.player1))
                       for a, b in zip(pp["player1"].astype(str), pp["player2"].astype(str))]]
            if len(hits) == 1:
                out.append((r.match_id, hits["match_id"].iloc[0]))
    return pd.DataFrame(out, columns=["chart_match_id", "pbp_match_id"])
