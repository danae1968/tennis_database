"""Data preparation for the top-10 profiles: current top 10, 52-week match table, charting tables."""
from __future__ import annotations

import re
import unicodedata

import numpy as np
import pandas as pd

from tennis.scores import parse_score, service_games
from tennis.load import load_charting, load_tml_years

TOUR_LEVELS = {"G", "M", "1000", "500", "250", "F", "A"}   # Slams, Masters/WTA 1000, 500, 250, tour finals, other (see below)
# Level 'A' mixes regular events (e.g. the WTA Prague Open) with team / exhibition events, which are excluded by name.
EXCLUDED_EVENTS = {"United Cup", "Laver Cup", "Next Gen ATP Finals"}
# excluded: Davis Cup / BJK Cup ('D'), the events above, Challengers
TOUR_FILE = {"WTA": "WTA", "ATP": "ATP"}
WINDOW_DAYS = 364
MAX_STALE_DAYS = 84        # a ranking is "current" only if the player played within 12 weeks of the last match
NUM = ["svpt", "1stWon", "2ndWon", "bpSaved", "bpFaced", "SvGms", "ace", "df", "1stIn"]


def norm_name(s: str) -> str:
    """Accent-, case- and punctuation-insensitive player name key."""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]", "", s.lower())


def tour_level_mask(d: pd.DataFrame) -> pd.Series:
    """Rows that are regular tour-level events: an included level and not a team / exhibition event."""
    return d.tourney_level.isin(TOUR_LEVELS) & ~d.tourney_name.isin(EXCLUDED_EVENTS)


def window_mask(dates: pd.Series, asof: pd.Timestamp) -> pd.Series:
    """Dates inside the 52-week window ending at ``asof`` (start exclusive, end inclusive)."""
    return (dates > asof - pd.Timedelta(days=WINDOW_DAYS)) & (dates <= asof)


def load_tour(tour: str) -> pd.DataFrame:
    """Tour-level matches (2025-26 files) of one tour, with numeric columns and a datetime column."""
    d = load_tml_years([2025, 2026], kinds=(tour,))
    d = d[tour_level_mask(d)].copy()
    d["date"] = pd.to_datetime(d.tourney_date, format="%Y%m%d")
    d["match_num"] = pd.to_numeric(d.match_num)
    for p, q in (("w", "winner"), ("l", "loser")):
        for c in NUM:
            d[f"{p}_{c}"] = pd.to_numeric(d[f"{p}_{c}"], errors="coerce")
        d[f"{q}_rank"] = pd.to_numeric(d[f"{q}_rank"], errors="coerce")
        d[f"{q}_rank_points"] = pd.to_numeric(d[f"{q}_rank_points"], errors="coerce")
    return d


def current_top10(d: pd.DataFrame, force_include: dict[str, str] | None = None) -> tuple[pd.DataFrame, dict]:
    """Top 10 from the rank each player had at their latest match in the data.

    Only players whose latest match is within ``MAX_STALE_DAYS`` of the tour's last match date count (an
    injured player's old rank is not current).  Sorted by (rank, -rank points) since ranks recorded at
    different dates can tie.  Returns (top10 frame, info dict incl. as-of date and excluded stale players).
    """
    asof = d.date.max()
    rows = pd.concat([
        d[["date", "match_num", "winner_id", "winner_name", "winner_rank", "winner_rank_points"]]
        .set_axis(["date", "match_num", "id", "name", "rank", "points"], axis=1),
        d[["date", "match_num", "loser_id", "loser_name", "loser_rank", "loser_rank_points"]]
        .set_axis(["date", "match_num", "id", "name", "rank", "points"], axis=1)])
    last = rows.sort_values(["date", "match_num"], kind="stable").groupby("id").tail(1)
    last = last[(last.date.dt.year == asof.year) & last["rank"].notna()]
    force = force_include or {}
    active = last[((asof - last.date).dt.days <= MAX_STALE_DAYS) | last.name.isin(list(force))]
    stale_top = last[((asof - last.date).dt.days > MAX_STALE_DAYS) & ~last.name.isin(list(force))].sort_values("rank").head(3)
    ranked = active.sort_values(["rank", "points"], ascending=[True, False], kind="stable")
    top = ranked.head(10).copy()
    dropped = [f"{n} (rank {int(r)})" for n, r in zip(ranked.name.iloc[10:12], ranked["rank"].iloc[10:12])] if len(ranked) > 10 else []
    top["pos"] = np.arange(1, len(top) + 1)
    top["forced"] = top.name.isin(list(force))
    top["partial"] = (asof - top.date).dt.days > MAX_STALE_DAYS
    top = top.rename(columns={"date": "last_match", "rank": "rank_at_last_match"})
    info = {"as_of": str(asof.date()), "forced_include": {n: force[n] for n in top.name if n in force},
            "first_pushed_out": dropped[:1],
            "stale_excluded": [f"{r['name']} (rank {int(r['rank'])} on {r['date'].date()})" for _, r in stale_top.iterrows()
                               if r["rank"] <= 12]}
    return top.reset_index(drop=True), info


def long_table(d: pd.DataFrame, asof: pd.Timestamp) -> pd.DataFrame:
    """One row per player per match in the 52-week window ending at ``asof`` (player perspective).

    Columns: id, name, match_id, date, surface, best_of, won, completed, svpt/sv_won/bpFaced/bpSaved, service games
    ``svg`` (from the score: half of the regular games each, via ``tennis.scores``; retirements are dropped), opponent's equivalents (``o_*``), games-identity flag, tiebreaks won/played, deciding set.
    """
    d = d[window_mask(d.date, asof)].copy()
    recs = []
    for r in d.itertuples(index=False):
        sets = parse_score(r.score, allow_match_tiebreak=True)
        if sets is None:                              # retirement / walkover / default / malformed: excluded
            continue
        w_br = r.l_bpFaced - r.l_bpSaved            # breaks won by the winner
        l_br = r.w_bpFaced - r.w_bpSaved
        ok = bool(np.isfinite(w_br) and np.isfinite(l_br) and r.w_svpt > 0 and r.l_svpt > 0)
        # unknown first server -> expectation: half of the regular games each (unbiased when aggregated)
        sg_w, sg_l = service_games(sets) if ok else (np.nan, np.nan)
        tbw = sum(1 for x in sets if x.tiebreak and x.w > x.l)
        tbl = sum(1 for x in sets if x.tiebreak and x.w < x.l)
        bo = int(r.best_of)
        base = dict(match_id=f"{r.tourney_id}-{int(r.match_num)}", date=r.date, surface=r.surface, best_of=bo,
                    level=r.tourney_level, completed=True, flag="expected" if ok else "no_bp_stats",
                    deciding=len(sets) == bo)
        for side, oth, won, tbs, tbo, sg, osg in (("w", "l", 1, tbw, tbl, sg_w, sg_l), ("l", "w", 0, tbl, tbw, sg_l, sg_w)):
            g = lambda p, c: getattr(r, f"{p}_{c}")
            recs.append({**base, "id": getattr(r, "winner_id" if side == "w" else "loser_id"),
                         "name": getattr(r, "winner_name" if side == "w" else "loser_name"), "won": won,
                         "svpt": g(side, "svpt"), "sv_won": g(side, "1stWon") + g(side, "2ndWon"),
                         "bpF": g(side, "bpFaced"), "bpS": g(side, "bpSaved"), "svg": sg,
                         "o_svpt": g(oth, "svpt"), "o_sv_won": g(oth, "1stWon") + g(oth, "2ndWon"),
                         "o_bpF": g(oth, "bpFaced"), "o_bpS": g(oth, "bpSaved"), "o_svg": osg,
                         "tb_won": tbs, "tb_played": tbs + tbo})
    L = pd.DataFrame(recs)
    L["conceded"] = L.bpF - L.bpS                    # own service games broken (breaks conceded)
    L["breaks"] = L.o_bpF - L.o_bpS                  # breaks won on opponent's serve
    L["ret_won"] = L.o_svpt - L.o_sv_won             # points won on return
    L["ret_pts"] = L.o_svpt
    return L


def charting_window(tour: str, asof: pd.Timestamp, names: dict[str, str]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Charting Overview (``set == "Total"`` rows), KeyPointsServe and KeyPointsReturn for ALL charted
    players with a match in the 52-week window (the tour-wide rows give the reference lines).

    ``names`` maps player id -> TML name; matching to charting names uses :func:`norm_name`.  The ``id``
    column is that player id (NaN for players outside ``names``).  ``date`` is taken from the match id.
    """
    g = "w" if tour == "WTA" else "m"
    key = {norm_name(n): i for i, n in names.items()}
    out = []
    for t in ("stats-Overview", "stats-KeyPointsServe", "stats-KeyPointsReturn"):
        x = load_charting(t, genders=(g,))
        x["id"] = x.player.map(norm_name).map(key)
        x["date"] = pd.to_datetime(x.match_id.str[:8], format="%Y%m%d", errors="coerce")
        x = x[window_mask(x.date, asof)].copy()
        out.append(x)
    ov, ks, kr = out
    ov = ov[ov["set"] == "Total"].copy()
    for c in ov.columns:
        if c not in ("match_id", "player", "set", "gender", "id", "date"):
            ov[c] = pd.to_numeric(ov[c], errors="coerce")
    for x in (ks, kr):
        for c in ("pts", "pts_won"):
            x[c] = pd.to_numeric(x[c], errors="coerce")
    return ov, ks, kr
