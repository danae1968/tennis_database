"""Match table for "can height predict the winner?" (WTA and ATP tour level, 2016-2026).

Every match becomes one row with the two players in RANDOM order (fixed seed), so the label
``p1_won`` is 1 in about half the rows and the winner/loser columns cannot leak the answer.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from tennis.load import load_tml_years
from tennis.scores import score_game_counts

SEED = 20261111
YEARS = range(2016, 2027)
TRAIN_YEARS = range(2016, 2023)          # 2016-2022
TEST_YEARS = range(2023, 2027)           # 2023-2026 (2026 partial)
TOURS = ("WTA", "ATP")                   # display order: WTA first
SURFACES = ("Hard", "Clay", "Grass")
HEIGHT_RANGE = (150, 215)                # cm; values outside (e.g. a date typed as height) are treated as missing
TEAM_LEVELS = {"D"}
COLS = ["tourney_id", "tourney_date", "tourney_level", "surface", "score", "round", "match_num",
        "winner_id", "loser_id", "winner_ht", "loser_ht", "winner_rank", "loser_rank",
        "w_ace", "l_ace", "w_svpt", "l_svpt", "w_1stWon", "w_2ndWon", "l_1stWon", "l_2ndWon"]


def clean_height(h: pd.Series) -> pd.Series:
    """Height in cm, NaN when missing or outside :data:`HEIGHT_RANGE`."""
    h = pd.to_numeric(h, errors="coerce")
    return h.where(h.between(*HEIGHT_RANGE))


def load_raw(years=YEARS) -> pd.DataFrame:
    """WTA and ATP TML rows (pandas-inferred dtypes) with ``year`` and ``tour``."""
    return load_tml_years(years, kinds=("ATP", "WTA"), usecols=COLS, text=False)


def player_ace_rates(raw: pd.DataFrame, min_svpt: int = 300) -> pd.DataFrame:
    """Per (tour, player, year): aces per serve point (``ace_rate``) and serve points won
    (``spw``) over all that year's matches with stats.  Rates from fewer than ``min_svpt`` serve
    points are set to NaN."""
    parts = []
    for side, k, o in (("winner", "w", "l"), ("loser", "l", "w")):
        parts.append(pd.DataFrame({"tour": raw["tour"], "year": raw["year"], "player": raw[f"{side}_id"].astype(str),
                                   "aces": raw[f"{k}_ace"], "svpt": raw[f"{k}_svpt"],
                                   "won": raw[f"{k}_1stWon"] + raw[f"{k}_2ndWon"],
                                   "rpt": raw[f"{o}_svpt"], "rwon": raw[f"{o}_svpt"] - raw[f"{o}_1stWon"] - raw[f"{o}_2ndWon"]}))
    p = pd.concat(parts).dropna(subset=["aces", "svpt", "won", "rpt", "rwon"])
    g = p.groupby(["tour", "player", "year"])[["aces", "svpt", "won", "rpt", "rwon"]].sum().reset_index()
    enough = (g["svpt"] >= min_svpt) & (g["rpt"] >= min_svpt)
    g["ace_rate"] = np.where(enough, g["aces"] / g["svpt"], np.nan)
    g["spw"] = np.where(enough, g["won"] / g["svpt"], np.nan)
    g["rpw"] = np.where(enough, g["rwon"] / g["rpt"], np.nan)          # return points won (placebo: not serve)
    return g


def build_matches(raw: pd.DataFrame, seed: int = SEED, ace_rates: pd.DataFrame | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """One row per completed tour-level match with players in random order.

    Columns: tour, year, surface, p1_won (0/1), ht1, ht2, ht_diff (cm, p1 - p2), rank1, rank2,
    log_rank_ratio (= ln rank2 - ln rank1, positive when p1 is better ranked), split ('train'/'test'),
    and, if ``ace_rates`` is given, each player's ace rate and serve-points-won share in the PREVIOUS
    calendar year (ace1/ace2, spw1/spw2) and their differences ace_diff / spw_diff (percentage points).  Returns (frame, cleaning log).
    """
    log = [("match rows (WTA, ATP tour level)", len(raw))]
    d = raw[~raw["tourney_level"].isin(TEAM_LEVELS)].copy()
    log.append(("  removed: team events", len(raw) - len(d)))
    ok = score_game_counts(d["score"], allow_match_tiebreak=True)["valid"]
    log.append(("  removed: retirement / walkover / unparseable score", int((~ok).sum())))
    d = d[ok].reset_index(drop=True)
    log.append(("completed matches", len(d)))
    rng = np.random.default_rng(seed)
    swap = rng.random(len(d)) < 0.5                       # True: player 1 is the loser
    pick = lambda w, l: np.where(swap, d[l], d[w])        # noqa: E731
    out = pd.DataFrame({
        "tour": d["tour"].values, "year": d["year"].values, "surface": d["surface"].values,
        "tourney_id": d["tourney_id"].astype(str).values,
        "p1_won": (~swap).astype(int),
        "id1": pick("winner_id", "loser_id").astype(str), "id2": np.where(swap, d["winner_id"], d["loser_id"]).astype(str),
        "ht1": clean_height(pd.Series(pick("winner_ht", "loser_ht"))).values,
        "ht2": clean_height(pd.Series(np.where(swap, d["winner_ht"], d["loser_ht"]))).values,
        "rank1": pd.to_numeric(pd.Series(pick("winner_rank", "loser_rank")), errors="coerce").values,
        "rank2": pd.to_numeric(pd.Series(np.where(swap, d["winner_rank"], d["loser_rank"])), errors="coerce").values,
    })
    out["ht_diff"] = out["ht1"] - out["ht2"]
    out["log_rank_ratio"] = np.log(out["rank2"]) - np.log(out["rank1"])
    out["split"] = np.where(out["year"].isin(list(TRAIN_YEARS)), "train", "test")
    out["surface"] = out["surface"].where(out["surface"].isin(SURFACES))
    if ace_rates is not None:
        ar = ace_rates[["tour", "player", "year", "ace_rate", "spw", "rpw"]].copy()
        ar["year"] = ar["year"] + 1                       # previous season's rates, known before the match
        for k in ("1", "2"):
            out = out.merge(ar.rename(columns={"player": f"id{k}", "ace_rate": f"ace{k}", "spw": f"spw{k}", "rpw": f"rpw{k}"}),
                            on=["tour", f"id{k}", "year"], how="left")
        out["ace_diff"] = (out["ace1"] - out["ace2"]) * 100      # percentage points
        out["spw_diff"] = (out["spw1"] - out["spw2"]) * 100
        out["rpw_diff"] = (out["rpw1"] - out["rpw2"]) * 100
    log.append(("  with both heights", int(out["ht_diff"].notna().sum())))
    log.append(("  with both heights and both ranks", int((out["ht_diff"].notna() & out["log_rank_ratio"].notna()).sum())))
    return out, pd.DataFrame(log, columns=["step", "count"])


def height_coverage(m: pd.DataFrame) -> pd.DataFrame:
    """Share of matches with both heights (and with each player's height) by tour and year."""
    g = m.groupby(["tour", "year"])
    return pd.DataFrame({"matches": g.size(), "both_heights": g["ht_diff"].apply(lambda s: s.notna().mean()),
                         "player_heights": g.apply(lambda x: (x["ht1"].notna().mean() + x["ht2"].notna().mean()) / 2,
                                                   include_groups=False)}).reset_index()
