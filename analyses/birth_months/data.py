"""Loading, parsing, de-duplicating and cleaning the player tables."""
from __future__ import annotations

import re
import unicodedata
import numpy as np
import pandas as pd
from scipy import stats

from tennis.load import load_wta_matches_2000_2017, read_text_csv, tml_year_files

MIN_YEAR, MAX_YEAR = 1900, 2015   # plausible birth years for a tour player


def parse_birthdate(s: pd.Series) -> pd.Series:
    """Parse ``YYYYMMDD`` strings (or floats such as ``19930316.0``) to datetime.

    Anything that is missing, not 8 digits, or not a real calendar date becomes ``NaT``.
    """
    txt = s.astype("string").str.strip().str.replace(r"\.0$", "", regex=True)
    ok = txt.str.fullmatch(r"\d{8}").fillna(False)
    out = pd.to_datetime(txt.where(ok), format="%Y%m%d", errors="coerce")
    return out


def normalise_name(name: str | None) -> str:
    """Lower-case, strip accents/punctuation and sort tokens so word order is irrelevant."""
    if name is None or (isinstance(name, float) and np.isnan(name)) or pd.isna(name):
        return ""
    t = unicodedata.normalize("NFKD", str(name))
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    t = re.sub(r"[^a-z0-9 ]+", " ", t.replace("-", " "))
    return " ".join(sorted(t.split()))


def dedupe_by_id(df: pd.DataFrame, id_col: str = "player_id") -> pd.DataFrame:
    """Drop repeated IDs, keeping the first row."""
    return df.drop_duplicates(subset=id_col, keep="first")


def dedupe_by_name_birthdate(df: pd.DataFrame, n_matches_col: str = "n_matches") -> pd.DataFrame:
    """Collapse rows with the same normalised name and the same birthdate.

    The row with the most matches is kept (ties: lowest ID, so output is deterministic).
    Requires columns ``name_norm``, ``birthdate`` and ``player_id``.
    """
    d = df.sort_values([n_matches_col, "player_id"], ascending=[False, True], kind="stable")
    has = d["birthdate"].notna() & (d["name_norm"] != "")
    keep = d[~has].copy()
    dedup = d[has].drop_duplicates(subset=["name_norm", "birthdate"], keep="first")
    return pd.concat([keep, dedup]).sort_values("player_id", kind="stable")


def detect_placeholder_days(birthdates: pd.Series, alpha: float = 0.05) -> pd.DataFrame:
    """Find (month, day=1) cells that carry an implausible excess of births.

    Players whose exact date is unknown are often stored as the 1st of a month or 1 January.
    For each month we compare the count on day 1 with the mean count on days 2-28 of that
    month (one-sided Poisson test; family-wise error rate ``alpha`` = 5%, Bonferroni over the 12 months).
    A deliberately liberal level: a false alarm only removes one genuine day, a miss inflates January.
    Returns one row per month.
    """
    b = birthdates.dropna()
    rows = []
    for m in range(1, 13):
        bm = b[b.dt.month == m]
        base = bm[(bm.dt.day >= 2) & (bm.dt.day <= 28)].groupby(bm.dt.day).size().reindex(range(2, 29), fill_value=0).mean()
        obs = int((bm.dt.day == 1).sum())
        p = float(stats.poisson.sf(obs - 1, base)) if base > 0 else 1.0
        rows.append({"month": m, "day1_count": obs, "mean_day2_28": round(float(base), 2),
                     "ratio": round(obs / base, 2) if base > 0 else np.nan, "p": p,
                     "flagged": p < alpha / 12})
    return pd.DataFrame(rows)


def _tally(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """Per-player match counts and best (lowest) ranking from winner/loser columns."""
    parts = []
    for f in frames:
        for side in ("winner", "loser"):
            parts.append(pd.DataFrame({"player_id": f[f"{side}_id"].astype(str),
                                       "rank": pd.to_numeric(f.get(f"{side}_rank"), errors="coerce")}))
    a = pd.concat(parts, ignore_index=True)
    g = a.groupby("player_id").agg(n_matches=("rank", "size"), best_rank=("rank", "min"))
    return g


def match_stats_atp() -> pd.DataFrame:
    """Main-tour matches per ATP player: ``tml-data/YYYY.csv`` (tour level incl. Slams, Davis Cup)."""
    cols = ["winner_id", "loser_id", "winner_rank", "loser_rank"]
    frames = [read_text_csv(p, usecols=cols) for _, p in tml_year_files("ATP")]
    return _tally(frames)


def match_stats_wta() -> pd.DataFrame:
    """Main-tour matches per WTA player.

    ``matches.csv`` (Sackmann, 2000-2017) is used for those years; ``tml-data/YYYY_wta.csv`` for
    all other years (1990-1999, 2018+). Years are never double counted.
    """
    cols = ["winner_id", "loser_id", "winner_rank", "loser_rank"]
    frames = [load_wta_matches_2000_2017(usecols=cols + ["year"])]
    frames[0] = frames[0].drop(columns="year")
    for y, p in tml_year_files("WTA"):
        if y < 2000 or y > 2017:
            frames.append(read_text_csv(p, usecols=cols))
    return _tally(frames)


def clean_players(players: pd.DataFrame, matches: pd.DataFrame, placeholder_months: set[int] | None = None):
    """Run the cleaning pipeline for one source.

    Returns ``(clean_df, log)`` where ``log`` is a list of ``(step, rows_removed)`` entries.
    Steps: duplicate ID -> missing/invalid date -> impossible year -> same person under two IDs
    -> placeholder dates (1 January / 1st of flagged months) which are excluded.
    ``clean_df`` also contains placeholder-flagged rows in column ``placeholder`` so a
    sensitivity analysis can include them; the log counts them as removed from the main table.
    """
    log = [("rows in", len(players))]
    d = dedupe_by_id(players)
    log.append(("duplicate player ID", len(players) - len(d)))
    d = d.copy()
    d["birthdate"] = parse_birthdate(d["birth_raw"])
    d = d.join(matches, on="player_id")
    d["n_matches"] = d["n_matches"].fillna(0).astype(int)
    d["name_norm"] = d["name"].map(normalise_name)
    n_missing = int(d["birth_raw"].isna().sum())
    n_invalid = int(d["birth_raw"].notna().sum() - d["birthdate"].notna().sum())
    d = d[d["birthdate"].notna()]
    log.append(("missing birth date", n_missing))
    log.append(("unparseable / invalid birth date", n_invalid))
    bad_year = ~d["birthdate"].dt.year.between(MIN_YEAR, MAX_YEAR)
    log.append((f"impossible birth year (outside {MIN_YEAR}-{MAX_YEAR})", int(bad_year.sum())))
    d = d[~bad_year]
    n1 = len(d)
    d = dedupe_by_name_birthdate(d)
    log.append(("same person under different ID (name + birthdate)", n1 - len(d)))
    ph = detect_placeholder_days(d["birthdate"])
    flagged = set(ph.loc[ph["flagged"], "month"]) if placeholder_months is None else placeholder_months
    d["placeholder"] = (d["birthdate"].dt.day == 1) & d["birthdate"].dt.month.isin(flagged)
    log.append(("placeholder date (1st of month with excess day-1 births)", int(d["placeholder"].sum())))
    log.append(("rows out", int((~d["placeholder"]).sum())))
    d["month"] = d["birthdate"].dt.month
    d["birth_year"] = d["birthdate"].dt.year
    return d.reset_index(drop=True), log, ph


def january_early_days_test(birthdates: pd.Series) -> dict:
    """Share of January births on days 1-10 against the 10/31 expected (one-sided binomial test).

    Complements the day-1 test: rounded dates (1st, 5th, 10th) also heap in early January.
    """
    b = birthdates.dropna(); jan = b[b.dt.month == 1]
    k, n = int((jan.dt.day <= 10).sum()), int(len(jan))
    return {"january_births": n, "on_days_1_10": k, "share": k / n if n else np.nan, "expected_share": 10 / 31,
            "p_one_sided": float(stats.binomtest(k, n, 10 / 31, alternative="greater").pvalue) if n else np.nan}


def wta_match_ids_by_year() -> pd.DataFrame:
    """(year, player_id) pairs for WTA tour-level players, same sources/years as ``match_stats_wta``."""
    rows = []
    m = load_wta_matches_2000_2017(usecols=["winner_id", "loser_id", "year"])
    m = m[m["year"].str.fullmatch(r"\d{4}").fillna(False)]              # a malformed trailing row has no year
    for side in ("winner_id", "loser_id"):
        rows.append(pd.DataFrame({"year": m["year"].astype(int), "player_id": m[side].astype(str)}))
    for y, p in tml_year_files("WTA"):
        if y < 2000 or y > 2017:
            f = read_text_csv(p, usecols=["winner_id", "loser_id"])
            for side in ("winner_id", "loser_id"):
                rows.append(pd.DataFrame({"year": y, "player_id": f[side].astype(str)}))
    return pd.concat(rows).drop_duplicates()


def wta_id_coverage(players: pd.DataFrame) -> pd.DataFrame:
    """Per year: share of WTA tour-level players (by ID) present in ``players.csv`` with a valid birth date."""
    ids = wta_match_ids_by_year()
    ok = set(players.loc[parse_birthdate(players["birth_raw"]).notna(), "player_id"])
    ids["has_birthdate"] = ids["player_id"].isin(ok)
    out = ids.groupby("year").agg(players=("player_id", "size"), with_birthdate=("has_birthdate", "sum")).reset_index()
    out["share"] = (out["with_birthdate"] / out["players"]).round(3)
    return out
