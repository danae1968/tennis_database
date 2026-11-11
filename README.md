# tennis_database

Three questions about professional tennis, answered from public match and point-by-point data.
Each analysis has its own README with method, results, figures and caveats.

| Question | Short answer | Details |
|---|---|---|
| **Does serving first in a set help you win it?** | Barely. The first server wins 52.7% of first sets, but about half of that is stronger players choosing to serve; at equal strength it is about 51% (an edge of 0–2 points). The 45.9% in later sets is selection: the player who just lost a set usually serves first next, and at equal ranking and previous-set result it is 50%. | [analyses/serve_first](analyses/serve_first/README.md) |
| **Are tennis players' birth months unevenly distributed?** | Yes. January–April births are over-represented and October–December under-represented (about 1.3× as many Q1 as Q4 births among players with a tour-level match), far beyond chance and consistent with the relative age effect. | [analyses/birth_months](analyses/birth_months/README.md) |
| **Have points played and match duration changed over the last decade?** | Points per game, set and match are flat; each point takes longer (about +2 s per decade at the Slams, 28 → 31 s for men), so games, sets and matches are longer (best-of-3 matches +10–15 min per decade). | [analyses/match_length_trends](analyses/match_length_trends/README.md) |

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install -e .        # installs the shared package `tennis` (src/tennis) in editable mode
make data                         # download raw data (idempotent; see "Data sources")
make all                          # rebuild every analysis from raw data (~4 min)
make test                         # run all tests
```

`make serve_first`, `make birth_months` and `make match_length_trends` rebuild one analysis; each is also
runnable on its own, e.g. `.venv/bin/python analyses/serve_first/run.py`. Outputs (`results/`, `figures/`)
are deterministic. Set `TENNIS_DATA_ROOT` to read the raw data from another folder.

## Layout

```
pyproject.toml            package "tennis" (src layout), pinned dependencies, pytest config
Makefile                  make data | test | all | <analysis> | clean
scripts/download_data.sh  TennisMyLife API + pinned Slam point-by-point and Match Charting downloads
src/tennis/               shared code: paths, loaders, statistics helpers, plotting house style
analyses/<name>/          run.py + analysis-specific modules, results/ (CSV/JSON), figures/ (PNG), README.md
analyses/reviews/         cross-reviews, fix responses and verifications between the two agents
tests/                    tests for the shared code (tests/shared) and for each analysis
archive/set_first_serve_v1/  earlier serve-order work based on inferred serve order (kept for reference)
```

Raw data folders (`tml-data/`, `pbp-data/`, `wta/`, root CSVs) are read-only inputs and are not committed.

## Data sources

### TennisMyLife (`tml-data/`)

ATP match data (yearly files 1967 onwards, Challenger and qualifying files, WTA yearly files and the
ATP player database `ATP_Database.csv`) from [TennisMyLife](https://stats.tennismylife.org)
(© TennisMyLife), downloaded via its data API: <https://stats.tennismylife.org/api/data-files>
(`make data`). No explicit licence is stated on the site; please credit TennisMyLife when using this data.

### Grand Slam point-by-point (`pbp-data/slam/`)

Jeff Sackmann's `tennis_slam_pointbypoint` (Grand Slam singles, and some doubles, 2011–2024). The original
repository was deleted; the copy used here is a shallow clone of the fork
<https://github.com/byshiny/tennis_slam_pointbypoint> at commit
`6febb77dade9c9782bbd9120330d489e914eaf47` (2024-10-11), pinned in `scripts/download_data.sh`.

### Match Charting Project (`pbp-data/charting/`)

Selected files of Jeff Sackmann's [tennis_MatchChartingProject](https://github.com/JeffSackmann/tennis_MatchChartingProject)
at commit `1813a1309b7ed7ebf1c7e884b32bf675d00e4edf` (2026-09-18): `charting-{m,w}-matches.csv`,
`charting-{m,w}-stats-Overview.csv`, `charting-{m,w}-stats-KeyPointsServe.csv`,
`charting-{m,w}-stats-KeyPointsReturn.csv` and its README. Loader: `tennis.load.load_charting`
(not yet used by an analysis).

### WTA data (`wta/`, and `matches.csv`, `players.csv`, `qualifying_matches.csv`, `rankings.csv` in the root)

WTA matches, qualifying matches, players and rankings. The columns and player IDs follow the format of
Jeff Sackmann's [tennis_wta](https://github.com/JeffSackmann/tennis_wta) dataset, which this data appears
to be derived from (a combined/reformatted version; the exact intermediate source is not documented, so
`make data` cannot fetch it).

### Licence of the Sackmann data

Tennis databases, files, and algorithms by [Jeff Sackmann / Tennis Abstract](http://www.tennisabstract.com/)
are licensed under a
[Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License](http://creativecommons.org/licenses/by-nc-sa/4.0/).
Based on a work at <https://github.com/JeffSackmann>. The Match Charting Project data is "Crowdsourced
shot-by-shot professional tennis data" by the Tennis Abstract Match Charting Project, under the same licence.
Attribution is required; non-commercial use only.

## How this was built

An orchestrating Claude session split the work between two Claude agents, **Opus** (serve order) and
**Sonnet** (birth months, match length), who worked independently. Each then reviewed the other's
analysis (re-running the code and checking headline numbers with their own code), fixed the points
raised in the review of their own work, and verified the other's fixes. All reviews, responses and
verifications are in [analyses/reviews/](analyses/reviews/). The code was finally refactored into this
single project with the shared `tennis` package; every result table was checked to be unchanged.
