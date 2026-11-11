"""Linking Grand Slam point-by-point matches to TennisMyLife match rows (``tml-data/YYYY.csv`` for
men, ``tml-data/YYYY_wta.csv`` for women) by year, tournament and player names.

Player names in the pbp files come in three styles: full names ("Rafael Nadal"), initial + surname
with a dot ("A. Dolgopolov", 2018 AO) and without ("C Moutet", 2020-21 AO/FO).  A pbp name matches
a TML name if, after accent/punctuation normalisation, either the full names are equal, or the
initial agrees with the TML first name and the pbp surname tokens equal the trailing TML tokens.
If nothing matches, any TML name containing the pbp surname token is a candidate (the pair
constraint below makes false links very unlikely).  A pbp match is linked to a TML row of the same year, Slam and gender whose {winner, loser} pair
matches {player1, player2}; it is left unlinked when there is no unique such row.
"""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

import numpy as np
import pandas as pd

from tennis.load import tml_path
from tennis.paths import SLAM_NAMES

TML_COLS = ["tourney_name", "tourney_date", "match_num", "winner_name", "loser_name", "winner_rank",
            "loser_rank", "winner_rank_points", "loser_rank_points", "score", "best_of", "round",
            "w_svpt", "w_1stWon", "w_2ndWon", "w_SvGms", "w_bpSaved", "w_bpFaced",
            "l_svpt", "l_1stWon", "l_2ndWon", "l_SvGms", "l_bpSaved", "l_bpFaced"]


@lru_cache(maxsize=None)
def normalize_name(name: str) -> tuple[str, ...]:
    """Lower-case ASCII tokens; hyphens, dots and apostrophes become separators."""
    s = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode()
    s = re.sub(r"[-.'`,]", " ", s.lower())
    return tuple(t for t in s.split() if t)


def names_match(pbp_name: str, tml_name: str) -> bool:
    """Whether a pbp-style player name refers to the TML full name (see module docstring)."""
    p, t = normalize_name(pbp_name), normalize_name(tml_name)
    if not p or not t:
        return False
    if p == t:
        return True
    initials = []
    rest = list(p)
    while len(rest) > 1 and len(rest[0]) == 1:
        initials.append(rest.pop(0))
    if initials:
        n = len(rest)
        return len(t) > n and tuple(t[-n:]) == tuple(rest) and t[0][0] == initials[0]
    # full-name style but not identical (e.g. a middle name or compound surname): same first
    # initial and the pbp surname is the TML surname's last token, or vice versa
    return p[0][0] == t[0][0] and (p[-1] == t[-1]) and (p[0] == t[0] or len(p) != len(t))


def load_tml_slams(years: list[int]) -> pd.DataFrame:
    """Grand Slam main-draw rows from TML for the given years, both genders, with a ``slam`` code."""
    inv = {v: k for k, v in SLAM_NAMES.items()}
    frames = []
    for y in years:
        for gender, kind in (("M", "ATP"), ("W", "WTA")):
            f = tml_path(y, kind)
            if not f.exists():
                continue
            d = pd.read_csv(f, low_memory=False)
            d = d[d.tourney_name.isin(inv)][TML_COLS].copy()
            d["slam"] = d.tourney_name.map(inv)
            d["year"] = y
            d["gender"] = gender
            frames.append(d)
    T = pd.concat(frames, ignore_index=True)
    T["tml_row"] = np.arange(len(T))
    return T


def link_matches(M: pd.DataFrame, T: pd.DataFrame) -> pd.DataFrame:
    """For each pbp match return the linked TML row id and whether pbp player1 is the TML winner.

    Returns columns: match_id, tml_row (or -1), p1_is_tml_winner, link_status
    ('linked', 'no candidate', 'ambiguous').
    """
    out = []
    for (y, slam, g), mm in M.groupby(["year", "slam", "gender"]):
        tt = T[(T.year == y) & (T.slam == slam) & (T.gender == g)]
        tml_names = sorted(set(tt.winner_name.astype(str)) | set(tt.loser_name.astype(str)))
        cand: dict[str, set[str]] = {}
        for nm in set(mm.player1.astype(str)) | set(mm.player2.astype(str)):
            hits = {t for t in tml_names if names_match(nm, t)}
            if len(hits) > 1:      # prefer exact normalised equality if available
                exact = {t for t in hits if normalize_name(t) == normalize_name(nm)}
                hits = exact or hits
            if not hits:           # fallback: share the pbp surname token (first-name variants such as
                last = normalize_name(nm)[-1:] # Stan/Stanislas, Coco/Cori, reversed Chinese names)
                hits = {t for t in tml_names if last and last[0] in normalize_name(t) and len(last[0]) > 2}
            cand[nm] = hits
        pairs: dict[tuple[str, str], list[int]] = {}
        for r in tt.itertuples():
            pairs.setdefault((str(r.winner_name), str(r.loser_name)), []).append(r.tml_row)
        for r in mm.itertuples():
            found: list[tuple[int, bool]] = []
            for a in cand.get(str(r.player1), ()):
                for b in cand.get(str(r.player2), ()):
                    for row in pairs.get((a, b), []):
                        found.append((row, True))
                    for row in pairs.get((b, a), []):
                        found.append((row, False))
            found = list(dict.fromkeys(found))
            if len(found) == 1:
                out.append((r.match_id, found[0][0], found[0][1], "linked"))
            else:
                out.append((r.match_id, -1, False, "no candidate" if not found else "ambiguous"))
    return pd.DataFrame(out, columns=["match_id", "tml_row", "p1_is_tml_winner", "link_status"])
