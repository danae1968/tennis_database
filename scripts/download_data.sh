#!/usr/bin/env bash
# Download the raw data used by the analyses. Idempotent: existing files/folders are kept
# (set FORCE=1 to re-download). Run from anywhere; data goes to $TENNIS_DATA_ROOT (default: repo root).
#
#   tml-data/            TennisMyLife data API (all files it lists)
#   pbp-data/slam/       tennis_slam_pointbypoint, byshiny fork (the JeffSackmann original was deleted),
#                        pinned commit, shallow clone, .git removed
#   pbp-data/charting/   Sackmann tennis_MatchChartingProject, pinned commit, selected files only
#
# NOT downloaded: the WTA tables in the repo root (players.csv, matches.csv, qualifying_matches.csv,
# rankings.csv) and wta/. They follow Sackmann's tennis_wta format, but their exact intermediate source
# is not documented; supply them manually (see README "Data sources").
set -euo pipefail

ROOT="${TENNIS_DATA_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
FORCE="${FORCE:-0}"

SLAM_REPO="https://github.com/byshiny/tennis_slam_pointbypoint"
SLAM_SHA="6febb77dade9c9782bbd9120330d489e914eaf47"        # 2024-10-11
CHARTING_REPO="JeffSackmann/tennis_MatchChartingProject"
CHARTING_SHA="1813a1309b7ed7ebf1c7e884b32bf675d00e4edf"    # 2026-09-18
CHARTING_FILES=(README.md)
for g in m w; do
  for t in matches stats-Overview stats-KeyPointsServe stats-KeyPointsReturn; do
    CHARTING_FILES+=("charting-${g}-${t}.csv")
  done
done

need() { command -v "$1" >/dev/null || { echo "missing required tool: $1" >&2; exit 1; }; }
need curl; need python3; need git

# ---------------------------------------------------------------- TennisMyLife
echo "== TennisMyLife -> $ROOT/tml-data"
mkdir -p "$ROOT/tml-data"
curl -sS --fail 'https://stats.tennismylife.org/api/data-files' | python3 -c '
import json, sys
for f in json.load(sys.stdin)["files"]:
    print(f["url"] + "\t" + f["name"])' | while IFS=$'\t' read -r url name; do
  dest="$ROOT/tml-data/$name"
  if [[ -s "$dest" && "$FORCE" != 1 ]]; then continue; fi
  mkdir -p "$(dirname "$dest")"
  curl -sSL --fail "$url" -o "$dest.part" && mv "$dest.part" "$dest"
  echo "  $name"
done

# ---------------------------------------------------------------- Slam point-by-point (pinned fork)
SLAM_DIR="$ROOT/pbp-data/slam"
echo "== Slam point-by-point -> $SLAM_DIR ($SLAM_REPO @ ${SLAM_SHA:0:7})"
if [[ -d "$SLAM_DIR" && -n "$(ls -A "$SLAM_DIR" 2>/dev/null)" && "$FORCE" != 1 ]]; then
  echo "  exists, skipped"
else
  rm -rf "$SLAM_DIR.tmp" && mkdir -p "$SLAM_DIR.tmp"
  git -C "$SLAM_DIR.tmp" init -q
  git -C "$SLAM_DIR.tmp" remote add origin "$SLAM_REPO"
  git -C "$SLAM_DIR.tmp" fetch -q --depth 1 origin "$SLAM_SHA"
  git -C "$SLAM_DIR.tmp" checkout -q FETCH_HEAD
  rm -rf "$SLAM_DIR.tmp/.git" "$SLAM_DIR"
  mv "$SLAM_DIR.tmp" "$SLAM_DIR"
fi

# ---------------------------------------------------------------- Match Charting Project (pinned files)
CH_DIR="$ROOT/pbp-data/charting"
echo "== Match Charting Project -> $CH_DIR ($CHARTING_REPO @ ${CHARTING_SHA:0:7})"
mkdir -p "$CH_DIR"
for f in "${CHARTING_FILES[@]}"; do
  dest="$CH_DIR/$f"
  if [[ -s "$dest" && "$FORCE" != 1 ]]; then continue; fi
  curl -sSL --fail "https://raw.githubusercontent.com/$CHARTING_REPO/$CHARTING_SHA/$f" -o "$dest.part" && mv "$dest.part" "$dest"
  echo "  $f"
done

# ---------------------------------------------------------------- WTA tables (manual)
for f in players.csv matches.csv; do
  [[ -s "$ROOT/$f" ]] || echo "NOTE: $ROOT/$f is missing; the WTA tables must be supplied manually (see README)." >&2
done
echo "done."
