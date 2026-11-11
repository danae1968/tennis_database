"""Data loaders shared by the analyses.

* TennisMyLife match files (``tml-data/YYYY.csv`` ATP, ``YYYY_wta.csv`` WTA, ``YYYY_challenger.csv``).
* Grand Slam point-by-point files (Sackmann ``tennis_slam_pointbypoint``): singles match lists and points.
* Match Charting Project (Sackmann ``tennis_MatchChartingProject``): match list and aggregate stats.
* Player tables: ATP (TennisMyLife ``ATP_Database.csv``) and WTA (``players.csv``, tennis_wta format).

Loaders return raw-ish frames; analysis-specific cleaning stays with each analysis.
"""
from __future__ import annotations

import pickle
import re
from pathlib import Path

import numpy as np
import pandas as pd

from .paths import ATP_PLAYERS_CSV, CHARTING_DIR, PBP_SLAM_DIR, SLAM_SURFACE, TML_DIR, WTA_MATCHES_CSV, WTA_PLAYERS_CSV

# --------------------------------------------------------------------------- generic CSV
TML_KINDS = {"ATP": "{y}.csv", "WTA": "{y}_wta.csv", "Challenger": "{y}_challenger.csv"}


def read_text_csv(path: Path, **kw) -> pd.DataFrame:
    """Read a CSV with every column as text (latin-1), so IDs and dates are never re-typed."""
    return pd.read_csv(path, dtype=str, encoding="latin-1", **kw)


# --------------------------------------------------------------------------- TennisMyLife match files
def tml_path(year: int, kind: str = "ATP", tml_dir: Path = TML_DIR) -> Path:
    """Path of a yearly TML match file; ``kind`` is 'ATP', 'WTA' or 'Challenger'."""
    return tml_dir / TML_KINDS[kind].format(y=year)


def tml_year_files(kind: str = "ATP", tml_dir: Path = TML_DIR) -> list[tuple[int, Path]]:
    """All (year, path) yearly files of one kind, sorted by year."""
    pat = {"ATP": r"^(\d{4})\.csv$", "WTA": r"^(\d{4})_wta\.csv$", "Challenger": r"^(\d{4})_challenger\.csv$"}[kind]
    out = []
    for p in tml_dir.glob("*.csv"):
        m = re.match(pat, p.name)
        if m:
            out.append((int(m[1]), p))
    return sorted(out)


def load_tml_years(years, kinds=("ATP", "WTA", "Challenger"), usecols: list[str] | None = None,
                   text: bool = True, tml_dir: Path = TML_DIR) -> pd.DataFrame:
    """Concatenate yearly TML files (year-major, then ``kinds`` order) with ``year`` and ``tour`` columns.

    ``text=True`` reads every column as text (latin-1); ``text=False`` lets pandas infer dtypes.
    Missing files are skipped.
    """
    frames = []
    for y in years:
        for kind in kinds:
            f = tml_path(y, kind, tml_dir)
            if not f.exists():
                continue
            d = read_text_csv(f, usecols=usecols) if text else pd.read_csv(f, usecols=usecols, low_memory=False)
            d["year"] = y
            d["tour"] = kind
            frames.append(d)
    return pd.concat(frames, ignore_index=True)


# --------------------------------------------------------------------------- Grand Slam point-by-point
SINGLES_RE = re.compile(r"^(\d{4})-(ausopen|frenchopen|wimbledon|usopen)-matches\.csv$")
POINT_COLS = ["match_id", "SetNo", "GameNo", "PointNumber", "PointServer", "PointWinner",
              "GameWinner", "SetWinner", "P1GamesWon", "P2GamesWon"]


def gender_from_match_num(match_num: object) -> str | None:
    """'M' / 'W' from a Slam match number: men's singles start with '1' (or 'MS' in 2021 AO),
    women's with '2' (or 'WS'). Anything else (e.g. doubles) gives None."""
    s = str(match_num).strip().upper()
    if s.startswith("1") or s.startswith("MS"):
        return "M"
    if s.startswith("2") or s.startswith("WS"):
        return "W"
    return None


def gender_from_match_id(match_id: pd.Series) -> pd.Series:
    """Vectorised :func:`gender_from_match_num` on match ids such as ``2023-usopen-1101``."""
    return match_id.astype(str).str.rsplit("-", n=1).str[-1].map(gender_from_match_num)


def slam_singles_files(pbp_dir: Path = PBP_SLAM_DIR) -> list[tuple[int, str, Path, Path]]:
    """(year, slam, matches_path, points_path) for every singles event with both files.
    Doubles and mixed files (``-doubles`` / ``-mixed`` suffix) are never returned."""
    out = []
    for f in sorted(pbp_dir.glob("*-matches.csv")):
        m = SINGLES_RE.match(f.name)
        if not m:
            continue
        pts = f.with_name(f.name.replace("-matches.csv", "-points.csv"))
        if pts.exists():
            out.append((int(m[1]), m[2], f, pts))
    return out


def slam_points_path(year: int, slam: str, pbp_dir: Path = PBP_SLAM_DIR) -> Path:
    return pbp_dir / f"{year}-{slam}-points.csv"


def read_slam_points(path: Path, usecols: list[str] | None = None) -> pd.DataFrame:
    """Read one Slam points file as text (no cleaning)."""
    return pd.read_csv(path, usecols=usecols, dtype=str)


def load_slam_matches(pbp_dir: Path = PBP_SLAM_DIR) -> pd.DataFrame:
    """All singles matches with year, slam, surface, gender ('M'/'W') and best_of."""
    frames = []
    for year, slam, mf, _ in slam_singles_files(pbp_dir):
        m = pd.read_csv(mf, dtype=str)
        m = m[["match_id", "match_num", "player1", "player2"] +
              [c for c in ("status", "event_name", "round") if c in m.columns]].copy()
        m["year"] = year
        m["slam"] = slam
        frames.append(m)
    M = pd.concat(frames, ignore_index=True)
    M["surface"] = M.slam.map(SLAM_SURFACE)
    M["gender"] = M.match_num.map(gender_from_match_num)
    M["best_of"] = np.where(M.gender == "M", 5, 3)
    return M


def clean_slam_points(p: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Drop placeholder rows and coerce types.

    Placeholder rows are the per-match header rows (PointNumber 0, '0X', '0Y') whose PointServer is 0.
    Returns the cleaned frame (sorted by match and point number) and counts of dropped rows.
    """
    p = p[POINT_COLS].copy()
    n0 = len(p)
    pn = pd.to_numeric(p.PointNumber, errors="coerce")
    for c in POINT_COLS[1:]:
        if c != "PointNumber":
            p[c] = pd.to_numeric(p[c], errors="coerce")
    p["PointNumber"] = pn
    placeholder = pn.isna() | (pn <= 0)
    bad_server = ~p.PointServer.isin([1, 2])
    drop = placeholder | bad_server | p.SetNo.isna() | p.GameNo.isna()
    info = {"rows_in": int(n0), "placeholder_rows": int(placeholder.sum()),
            "non_placeholder_rows_bad_server_or_index": int((drop & ~placeholder).sum())}
    p = p[~drop].copy()
    for c in ["SetNo", "GameNo", "PointNumber", "PointServer", "PointWinner", "GameWinner", "SetWinner",
              "P1GamesWon", "P2GamesWon"]:
        p[c] = p[c].fillna(0).astype(np.int64)
    p = p.sort_values(["match_id", "PointNumber"], kind="stable").reset_index(drop=True)
    return p, info


def load_slam_points(cache_dir: Path | None = None, pbp_dir: Path = PBP_SLAM_DIR) -> tuple[pd.DataFrame, dict]:
    """All singles points, cleaned with :func:`clean_slam_points`.

    If ``cache_dir`` is given the result is cached there as ``points_clean.pkl``, keyed on the input
    file names, sizes and modification times (the cache is a local artefact and is git-ignored).
    """
    files = slam_singles_files(pbp_dir)
    sig = [(str(pf.name), pf.stat().st_size, pf.stat().st_mtime_ns) for _, _, _, pf in files]
    cache = cache_dir / "points_clean.pkl" if cache_dir is not None else None
    if cache is not None and cache.exists():
        with open(cache, "rb") as fh:
            obj = pickle.load(fh)
        if obj.get("sig") == sig:
            return obj["points"], obj["info"]
    frames, info = [], {"rows_in": 0, "placeholder_rows": 0, "non_placeholder_rows_bad_server_or_index": 0}
    for _, _, _, pf in files:
        raw = pd.read_csv(pf, usecols=POINT_COLS, dtype=str, low_memory=False)
        p, i = clean_slam_points(raw)
        frames.append(p)
        for k in info:
            info[k] += i[k]
    P = pd.concat(frames, ignore_index=True)
    if cache is not None:
        cache.parent.mkdir(parents=True, exist_ok=True)
        with open(cache, "wb") as fh:
            pickle.dump({"sig": sig, "points": P, "info": info}, fh)
    return P, info


# --------------------------------------------------------------------------- player tables
def load_atp_players(path: Path = ATP_PLAYERS_CSV) -> pd.DataFrame:
    """ATP player database (TennisMyLife) with standard column names."""
    d = read_text_csv(path)
    return pd.DataFrame({"player_id": d["id"], "name": d["player"], "birth_raw": d["birthdate"],
                         "country": d["ioc"], "gender": "ATP"})


def load_wta_players(path: Path = WTA_PLAYERS_CSV) -> pd.DataFrame:
    """WTA player list (tennis_wta format) with standard column names."""
    d = read_text_csv(path)
    return pd.DataFrame({"player_id": d["player_id"], "name": d["first_name"].fillna("") + " " + d["last_name"].fillna(""),
                         "birth_raw": d["birth_date"], "country": d["country_code"], "gender": "WTA"})


def load_wta_matches_2000_2017(usecols: list[str] | None = None, path: Path = WTA_MATCHES_CSV) -> pd.DataFrame:
    """WTA tour-level matches 2000-2017 (``matches.csv``, tennis_wta format), as text."""
    return read_text_csv(path, usecols=usecols)


# --------------------------------------------------------------------------- Match Charting Project
CHARTING_TABLES = ("matches", "stats-Overview", "stats-KeyPointsServe", "stats-KeyPointsReturn")


def charting_path(gender: str, table: str = "matches", charting_dir: Path = CHARTING_DIR) -> Path:
    """Path of a Match Charting Project file; ``gender`` is 'm' or 'w', ``table`` one of
    :data:`CHARTING_TABLES` (e.g. ``charting-w-stats-Overview.csv``)."""
    g = gender.lower()[0]
    if g not in ("m", "w") or table not in CHARTING_TABLES:
        raise ValueError(f"unknown charting file: gender={gender!r}, table={table!r}")
    return charting_dir / f"charting-{g}-{table}.csv"


def load_charting(table: str = "matches", genders=("m", "w"), charting_dir: Path = CHARTING_DIR) -> pd.DataFrame:
    """One Match Charting Project table for the given genders, concatenated, as text, with a
    ``gender`` column ('M'/'W').  Undecodable bytes are replaced rather than failing."""
    frames = []
    for g in genders:
        d = pd.read_csv(charting_path(g, table, charting_dir), dtype=str, encoding="utf-8",
                        encoding_errors="replace", low_memory=False)
        d["gender"] = g.upper()[0]
        frames.append(d)
    return pd.concat(frames, ignore_index=True)
