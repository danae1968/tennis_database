# tennis_database

Questions about women's and men's professional tennis, answered from public match and point-by-point data.

**Read it as a website: <https://danae1968.github.io/tennis_database/>**

The analyses were carried out by AI agents (Claude) under my direction, with independent cross-review;
see [How this was built](#how-this-was-built).

## The questions

| Question | Short answer |
|---|---|
| [Does serving first in a set help you win it?](analyses/serve_first/README.md) | Yes, slightly. The player who serves first wins 52.7% of first sets. Against an equally ranked opponent it is about 51%, an edge of roughly 1 percentage point (somewhere between 0 and 2). |
| [Are tennis players born earlier in the year than chance would predict?](analyses/birth_months/README.md) | Yes. Among the 8,073 players who have played a tour-level match, births in January to April are 10–19% more common than an even spread over the year would give, and births in October to December are 11–16% less common. |
| [Are tennis matches getting longer, and why?](analyses/match_length_trends/README.md) | Points per game, per set and per match have not changed since 2014, but each point takes longer. |
| [Have aces, breaks of serve and winners changed over the years?](analyses/serve_return_trends/README.md) | Aces have not changed: about 4 per 100 serve points for women and 8 for men. Breaks of serve have become slightly rarer on hard courts, by about 2 per 100 return games per decade, with no clear change on clay or grass. |
| [Can height alone predict who wins a tennis match?](analyses/height_predicts_winner/README.md) | A little. Knowing only the two players' heights, you would pick the winner 53.6% of the time in women's matches and 54.3% in men's, against 50% for a coin flip. |
| [How do the current top-10 women and men win their matches?](analyses/top10_profiles/README.md) | The current top 10 get there by different routes: some win mainly through their serve, others through their return. On break points, none of them does reliably better or worse than their normal level predicts. |

Each folder has a short `README.md` for readers and a `METHODS.md` with the full method, tables and checks.

## Reproduce

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install -e .        # the shared package `tennis` (src/tennis), editable
make data                         # download raw data (idempotent; see "Data sources")
make all                          # rebuild every analysis from raw data
make test                         # run all tests
make site                         # build the website into _site/ (needs Quarto; no data or Python needed)
```

`make <name>` rebuilds one analysis (e.g. `make serve_first`). Outputs in `results/` and `figures/` are
deterministic. Set `TENNIS_DATA_ROOT` to read the raw data from another folder.

## Layout

```
analyses/<name>/          run.py and modules, results/ (CSV/JSON), figures/ (PNG), README.md, METHODS.md
src/tennis/               shared code: paths, loaders, score parsing, statistics, plotting style
tests/                    tests for the shared code and each analysis
scripts/download_data.sh  data download (versions pinned)
archive/                  earlier exploratory serve-order work, kept for reference
_quarto.yml, index.qmd, about/, site/   the website; .github/workflows/publish.yml deploys it
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
`charting-{m,w}-stats-KeyPointsReturn.csv` and its README. Loader: `tennis.load.load_charting`.

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

An orchestrating Claude session split the work between two Claude agents, Opus (serve order, serve/return
trends, height) and Sonnet (birth months, match length, top 10), who worked independently. Each then reviewed
the other's analysis, re-running the code and checking the headline numbers with their own code. The author fixed
or answered each point, and the reviewer verified the fixes. This review → fix → verify cycle repeated until both
agreed.
