"""Repository root and data locations, defined in ONE place.

Environment overrides:
  TENNIS_REPO_ROOT  repository root (default: found from this file, i.e. the folder with pyproject.toml)
  TENNIS_DATA_ROOT  folder holding the raw data (default: the repository root); it must contain
                    ``tml-data/``, ``pbp-data/slam/``, ``pbp-data/charting/`` and the WTA tables ``players.csv`` / ``matches.csv``.
"""
from __future__ import annotations

import os
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start, *start.parents]:
        if (p / "pyproject.toml").is_file() and (p / "src" / "tennis").is_dir():
            return p
    raise FileNotFoundError("repository root not found (folder with pyproject.toml and src/tennis); "
                            "set TENNIS_REPO_ROOT")


REPO_ROOT: Path = Path(os.environ["TENNIS_REPO_ROOT"]).resolve() if os.environ.get("TENNIS_REPO_ROOT") \
    else _find_repo_root(Path(__file__).resolve().parent)
DATA_ROOT: Path = Path(os.environ["TENNIS_DATA_ROOT"]).resolve() if os.environ.get("TENNIS_DATA_ROOT") else REPO_ROOT

# raw data (read-only)
TML_DIR: Path = DATA_ROOT / "tml-data"                 # TennisMyLife match files and ATP player database
PBP_SLAM_DIR: Path = DATA_ROOT / "pbp-data" / "slam"   # tennis_slam_pointbypoint (byshiny fork, pinned)
CHARTING_DIR: Path = DATA_ROOT / "pbp-data" / "charting"  # Sackmann tennis_MatchChartingProject (subset)
WTA_PLAYERS_CSV: Path = DATA_ROOT / "players.csv"      # WTA players (Sackmann tennis_wta format)
WTA_MATCHES_CSV: Path = DATA_ROOT / "matches.csv"      # WTA tour-level matches 2000-2017 (tennis_wta format)
ATP_PLAYERS_CSV: Path = TML_DIR / "ATP_Database.csv"   # ATP players (TennisMyLife)

# analysis outputs
ANALYSES_DIR: Path = REPO_ROOT / "analyses"

SLAM_NAMES = {"ausopen": "Australian Open", "frenchopen": "Roland Garros",
              "wimbledon": "Wimbledon", "usopen": "US Open"}          # TML tourney_name per pbp slam code
SLAM_LABEL = {"ausopen": "Australian Open", "frenchopen": "French Open",
              "wimbledon": "Wimbledon", "usopen": "US Open"}          # display names
SLAM_SURFACE = {"ausopen": "Hard", "frenchopen": "Clay", "wimbledon": "Grass", "usopen": "Hard"}
SLAM_ORDER = ["ausopen", "frenchopen", "wimbledon", "usopen"]


def analysis_dirs(name: str) -> tuple[Path, Path, Path]:
    """(results, figures, cache) folders of ``analyses/<name>``. Results and figures are created if
    missing; the cache folder is only created by code that writes to it."""
    base = ANALYSES_DIR / name
    for p in (base / "results", base / "figures"):
        p.mkdir(parents=True, exist_ok=True)
    return base / "results", base / "figures", base / "cache"
