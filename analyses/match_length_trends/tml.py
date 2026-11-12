"""Tour-level match files (TennisMyLife): score parsing and per-match derived quantities."""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from tennis.load import load_tml_years

SET_RE = re.compile(r"(\d+)-(\d+)(?:\((\d+)\))?")
BAD_SCORE = re.compile(r"RET|W/O|WO|DEF|ABD|UNP|Default|Walkover|Unfinished|Interrupted|Suspended|ABN|NA", re.I)


def parse_score(score: str | None) -> dict:
    """Parse a score such as ``6-4 3-6 7-6(5)`` into sets, games and tiebreak counts.

    Returns ``valid=False`` for retirements, walkovers, empty strings and match tiebreaks
    written in brackets. A ``7-6``/``6-7`` set counts as 13 games (12 + the tiebreak game).
    """
    out = {"valid": False, "n_sets": np.nan, "n_games": np.nan, "n_tiebreaks": np.nan,
           "sets_w": np.nan, "sets_l": np.nan}
    if not isinstance(score, str) or not score.strip() or BAD_SCORE.search(score) or "[" in score:
        return out
    sets = SET_RE.findall(score)
    if not sets or SET_RE.sub("", score).replace(" ", "") != "":
        return out
    gw = [int(a) for a, b, _ in sets]; gl = [int(b) for a, b, _ in sets]
    n_tb = sum(1 for a, b in zip(gw, gl) if {a, b} == {7, 6} or {a, b} == {13, 12})
    out.update(valid=True, n_sets=len(sets), n_games=sum(gw) + sum(gl),
               n_tiebreaks=n_tb, sets_w=sum(a > b for a, b in zip(gw, gl)), sets_l=sum(a < b for a, b in zip(gw, gl)))
    return out


def level_group(kind: str, level: str) -> str:
    """Map tournament level codes to 'Slam' / 'Challenger' / 'Tour (other)' / 'Team' (excluded)."""
    if kind == "challenger":
        return "Challenger"
    if level == "G":
        return "Slam"
    if level in ("D", "O", "F", "W", "CC", "CH"):       # Davis/Fed Cup, Olympics, tour finals etc.
        return "Other/team"
    return "Tour (other)"


def load_tml(years: range) -> pd.DataFrame:
    """Load ATP, WTA and Challenger match rows for ``years`` with derived per-match quantities.

    Derived: ``points`` (= w_svpt + l_svpt), ``games``/``sets`` from the score, ``minutes`` and
    format (best of 3/5). Matches without a complete, parseable score or without minutes/points
    keep NaN so that each metric can drop its own missing values.
    """
    cols = ["tourney_id", "tourney_level", "surface", "best_of", "score", "minutes", "w_svpt", "l_svpt", "tourney_name"]
    d = load_tml_years(years, kinds=("ATP", "WTA", "Challenger"), usecols=cols, text=True)
    for c in ("best_of", "minutes", "w_svpt", "l_svpt"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d["level_group"] = [level_group("challenger" if t == "Challenger" else "tour", l) for t, l in zip(d["tour"], d["tourney_level"])]
    sc = pd.DataFrame([parse_score(s) for s in d["score"]])
    d = pd.concat([d.reset_index(drop=True), sc], axis=1)
    d["points"] = d["w_svpt"] + d["l_svpt"]
    d["edition"] = d["year"].astype(str) + "|" + d["tourney_id"].astype(str)
    return d


# ---- reliable-period rules for the tour files (see METHODS) -------------------------------------
GROUP_START = {"ATP bo3": 1995, "ATP bo5": 2000, "Challenger": 2010, "WTA": 2009}
RULE_STEP_YEAR = 2013      # tour-level match times are about 7 minutes shorter from this year on (ATP enforces the 25-second rule more strictly)


def restrict_to_reliable(d: pd.DataFrame) -> pd.DataFrame:
    """Keep each group only from the first year in which its match files are usable (:data:`GROUP_START`)."""
    first = d["group"].map(GROUP_START)
    return d[d["year"] >= first].copy()


def blank_low_coverage(d: pd.DataFrame, cols: list[str], by: list[str], min_share: float = 0.5) -> pd.DataFrame:
    """Set ``cols`` to NaN in every ``by`` cell (e.g. group x year) where fewer than ``min_share`` of matches
    have a recorded ``minutes`` value, so a partly recorded year is not read as the whole year."""
    d = d.copy()
    share = d.groupby(by)["minutes"].transform(lambda s: s.notna().mean())
    d.loc[share < min_share, cols] = np.nan
    return d
