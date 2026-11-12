# Methods: have aces, breaks of serve and winners changed over the years?

This is the technical companion to the [reader summary](README.md). It holds the data coverage, cleaning steps, models, sensitivity checks, full results tables, caveats and appendix figures.

**Question.** How have aces, breaks of serve and winners changed on the WTA, ATP and Challenger tours, and does it differ by surface?

**Answer in plain words.**
- **Aces: a long rise, then a plateau.**
  - ATP: comparing each tournament with itself, 4.8 aces per 100 serve points in 1991, 6.9 in 1997 and about 8 by 2014–15, flat since. The slope was +0.9 per decade up to 2016 and −0.5 after (change −1.45, 95% CI −1.96 to −0.94).
  - WTA: 3.3 in 2009, 4.0 in 2015, about 4 since; +1.0 per decade before 2016, +0.1 after (change −0.86, CI −1.40 to −0.33).
  - Challenger: flat since 2010, about 6.
- **Breaks of serve: a slow, long decline.**
  - ATP: 25.4 breaks per 100 return games in 1991, 21.1 in 2016, 19.6 in 2025; −1.4 per decade over 1991–2025 with tournament fixed effects. It slowed from −1.6 to −0.4 per decade after 2016 (change +1.2, CI +0.3 to +2.1). Before 2016 it fell on every surface; since then only hard courts are still falling.
  - WTA: 36.8 in 2009, 33.9 in 2025; −1.6 per decade, at the same pace before and after 2016 (change p = 0.57). It is a hard-court decline (−2.9 per decade with tournament fixed effects); clay and grass show none.
  - Challenger: flat.
- **Winners (excluding aces) at the Slams: no clear change, then edging down.**
  - About a quarter of Slam points end in a winner: 26.5% for women and 25.1% for men (2011–24).
  - 2011–15 shows no clear change (women +0.3, men +0.5 per decade, with CIs of about ±3); 2016–24 falls (women −1.6, men −1.1). Over 2011–24: women −0.75 (CI −1.46 to −0.04), men −1.10 (−1.59 to −0.60). By Slam, the decline is clearest at Wimbledon (women and men) and, for men, at the Australian Open (whose data changed provider in 2018, so part of that decline may reflect how winners were recorded); for women it is mainly a Wimbledon change (table in Results).
- **One apparent change is not real.** The Match Charting Project seems to show men's winners rising sharply after 2021. That comes from **one prolific volunteer charter**: without that person's matches, the rate is flat.

**How large are the changes?** All of them are small next to the gaps between surfaces and between tours. For example, an ATP grass-court match has 1.8 times the aces of a clay-court match.

## Data

| Source | Used for | Coverage | Citation / licence |
|---|---|---|---|
| `tml-data/YYYY.csv`, `YYYY_wta.csv`, `YYYY_challenger.csv` | Aces, breaks, break-point conversion | ATP 1991–2026, WTA 2009–2026, Challenger 2010–2026: 98,493 ATP, 39,627 WTA and 76,030 Challenger completed matches | [TennisMyLife](https://stats.tennismylife.org) (© TennisMyLife); the WTA part follows Sackmann's `tennis_wta` (CC BY-NC-SA 4.0) |
| `pbp-data/slam/` | Winners, unforced errors and aces per point at the four Slams | 2011–2024: 10,508 singles matches; Australian Open and Roland Garros only up to 2021 | Jeff Sackmann, `tennis_slam_pointbypoint` (via the [byshiny fork](https://github.com/byshiny/tennis_slam_pointbypoint), commit `6febb77`), CC BY-NC-SA 4.0 |
| `pbp-data/charting/` | Winners, unforced errors and aces per point in charted matches | 2016–2026: 3,236 women's and 4,620 men's matches | Jeff Sackmann, [Match Charting Project](https://github.com/JeffSackmann/tennis_MatchChartingProject) (commit `1813a13`), CC BY-NC-SA 4.0 |

**Why each tour starts when it does** (`results/coverage_serve_stats.csv`, figure A2). Each tour starts in its first season with near-complete serve statistics:
- **ATP:** 96–100% of completed tour-level matches have serve stats in every season from 1991.
- **WTA:** before 2006 only the Slams have stats (16–22% of all matches in 2003–05). In 2007–08 coverage is 77–80%, and the missing matches are clearly lower-ranked (median better-ranked player 44–55, against 23–27 in covered matches), so those seasons are left out. From 2009 coverage is 88–91% (78% in 2015) with a much smaller rank gap (31–42 vs 27–29), and from 2016 it is about 100%. Every trend is also estimated with tournament fixed effects, which compare each event only with itself. The remaining selection works against the 2009–15 ace rise rather than for it: covered matches lean to better players, who hit more aces, so the early level is if anything too high. The independent review also found the rise among matches with a top-50 player (3.2 → 4.1 per 100 serve points), where coverage matters least.
- **Challenger:** no serve stats before 2010; 95–100% from 2010.
- **Slam point-by-point:** 2011–2024. The 2011–13 files hold fewer matches (about 320–350 per gender instead of 420–500), but reweighting each year to the overall round mix changes the winner rate by at most 0.4 points (`results/slam_round_reweighting.csv`).

**2026 is a partial season,** with data to early November. It is plotted with open markers and left out of all trend estimates. The surfaces are Hard, Clay and Grass. Carpet (common on the ATP before 2009) is included in the all-surface results but not drawn as its own line. Challenger grass (about 90 matches a year) is in the tables but too thin to plot.

## How to run

```bash
make serve_return_trends      # or: .venv/bin/python analyses/serve_return_trends/run.py   (~9 min)
.venv/bin/python -m pytest tests/serve_return_trends
```

- Outputs go to `results/` (CSV/JSON) and `figures/`.
- The code is in `data.py` (TML match frame and coverage), `eras.py` (like-for-like yearly levels, slope change, step check), `winners.py` (Slam pbp and charting), `plots.py` and `run.py`.
- Shared helpers come from `tennis.scores` (service games from the score), `tennis.stats` (`ratio_ci`, `trend_per_decade`), `tennis.load` and `tennis.plotting`.

## Method

**Rates, not counts.** Every metric is a pooled rate: the sum of the numerator over the sum of the denominator across matches.
- Aces per serve point is `(w_ace + l_ace) / (w_svpt + l_svpt)`.
- Break % is `breaks / return games`. Breaks are each server's `bpFaced − bpSaved`, summed over both players.
- **Return games** come from the score, using `tennis.scores`: every non-tiebreak game is somebody's service game, so the return games of both players together equal the number of regular games.
  - TennisMyLife's `w_SvGms`/`l_SvGms` are never used, because they are wrong in about 26% of 2016–23 Slam matches (see `analyses/serve_first`).
  - A tiebreak, including a match tiebreak `[10-7]`, is not a service game.
- Break-point conversion is `breaks / break points faced`.

**Cleaning** (`results/cleaning_tml.csv`). From 357,352 match rows (1991–2026), the following were removed:
- 115,202 rows from seasons before each tour's start (WTA before 2009, Challenger before 2010);
- 14,507 team-event matches (Davis Cup and Billie Jean King Cup);
- 8,412 retirements, walkovers and unparseable scores;
- 5,077 matches without serve statistics;
- 4 internally inconsistent rows.

That leaves 214,150 matches.

**Winners excluding aces.** The data were checked for whether "winners" includes aces in each source, event by event (`results/slam_feed_check.csv`).
- **Slam point-by-point:**
  - In the IBM "Slamtracker" files (US Open and Wimbledon in every year, and Australian Open and Roland Garros up to 2017; 41 events), all 105,214 aces are *also* flagged as winners.
  - In the Infosys files (Australian Open and Roland Garros 2018–21; 8 events), none of the 22,291 aces is flagged as a winner.
  - A winner excluding aces is therefore "winner flag and not an ace", which is correct for both feeds.
- **Match Charting:** the Overview `winners` count includes aces: `winners ≥ aces + forehand + backhand winners` holds in all 23,624 player-match rows. So winners excluding aces = `winners − aces`, and points = both players' serve points added together.

**Uncertainty.** The 95% CIs on the yearly rates are linearised ratio CIs, clustered by:
- **tournament** for the tour files (the same event across years, matched by name);
- **match** for the Slam point-by-point data, where clay and grass have one event per year;
- **charter** (the volunteer who charted the match) for the charting data, because coding habits differ between charters.

**Trends** (`tennis.stats.trend_per_decade`).
- The fit is a weighted least-squares regression of the per-match rate on calendar year, weighted by the denominator, controlling for surface (tour data) or Slam (point-by-point data), with standard errors clustered as above.
- Trends are reported as **percentage points per decade**, for example "−1.4 breaks per 100 return games per decade".
- Each is estimated over the **whole period** (from each tour's first season to 2025) and over the **last ten full seasons, 2016–2025**.
- **Tournament fixed effects:** each tournament is compared only with itself over time, so changes in the calendar can't create a trend. These also absorb surface, because a tournament keeps its surface.
- **A year × surface interaction** tests whether the hard-court trend differs from clay and grass.

**Shape of the long-run trend** (`eras.py`).
- **Like-for-like yearly levels** (`results/like_for_like_index.csv`, figure A1): a regression of the per-match rate on year and tournament dummies (weighted, clustered by tournament), using tournaments seen in at least three seasons. The year effects are shifted so that 2025 equals its pooled rate.
- **Slope before and after 2016** (`results/slope_change_2016.csv`): a continuous piecewise-linear trend with one knot at 2016, with tournament fixed effects. The knot splits off the last ten full seasons; it was not chosen to fit the data. A data-driven breakpoint for ATP aces would fall around 2014–15.
- **Step check** (`results/step_check.csv`): year-on-year changes in the like-for-like levels, relative to the median change. A switch of data source would show up as one large, lasting step.

**Comparing the two winner sources.**
- 1,102 charted Slam matches were linked to the same matches in the point-by-point data, by year, Slam, gender and player names using `tennis.names`.
- That separates two things:
  - **Measurement:** do both sources count the same winners on the same match?
  - **Selection:** are charted matches typical of the Slam draw?

## Results

### Aces and breaks (TennisMyLife; percentage points per decade, 95% CI)

| Tour | Aces per 100 serve points: level | Ace trend, whole period (FE) | Ace trend, 2016–25 (FE) | Breaks per 100 return games: level | Break trend, whole period (FE) | Break trend, 2016–25 (FE) |
|---|---|---|---|---|---|---|
| **WTA** (from 2009) | 3.2 → 3.7 → 4.1 | **+0.45 (+0.23, +0.67)** | +0.13 (−0.19, +0.46) | 36.8 → 35.7 → 33.9 | **−1.59 (−2.38, −0.80)** | **−1.31 (−2.56, −0.07)** |
| **ATP** (from 1991) | 5.0 → 7.9 → 8.2 | **+0.67 (+0.49, +0.84)** | −0.31 (−0.76, +0.15) | 25.4 → 21.1 → 19.6 | **−1.40 (−1.66, −1.13)** | −0.69 (−1.42, +0.03) |
| **Challenger** (from 2010) | 6.2 → 6.1 → 5.8 | −0.05 (−0.26, +0.17) | +0.23 (−0.07, +0.52) | 24.3 → 24.7 → 25.4 | −0.01 (−0.53, +0.51) | −0.33 (−1.10, +0.43) |

Levels are pooled rates in the first season, 2016 and 2025. FE = tournament fixed effects. The trends with surface controls instead of fixed effects are in `results/trends_tml.csv`. Break-point conversion fell by about 0.8 points per decade on both tours over the whole period (FE: WTA −0.79, ATP −0.73) and did not change on the Challenger tour.

**Slope before and after 2016** (tournament fixed effects; per decade):

| Tour | Metric | Before 2016 | After 2016 | Change (95% CI) |
|---|---|---|---|---|
| WTA | Aces | +0.96 | +0.10 | **−0.86 (−1.40, −0.33)** |
| WTA | Breaks | −1.91 | −1.38 | +0.53 (−1.29, +2.36) |
| ATP | Aces | +0.93 | −0.52 | **−1.45 (−1.96, −0.94)** |
| ATP | Breaks | −1.62 | −0.41 | **+1.21 (+0.29, +2.13)** |
| Challenger | Aces | −0.56 | +0.23 | +0.78 (+0.14, +1.43) |
| Challenger | Breaks | +0.96 | −0.54 | −1.50 (−3.06, +0.06) |

The ATP ace plateau holds on every surface (changes −1.4 to −2.7). The ATP break slowdown comes from clay (+2.6) and grass (+2.5); on hard courts the change is +0.7 (−0.4, +1.7), and breaks there are still falling (−0.8 per decade after 2016). The Challenger slopes rest on six seasons before the knot and are fragile.

**Breaks by surface** (tournament fixed effects; `results/trends_tml.csv`, `break_trend_surface_differences.csv`):

| Tour | Window | Hard | Clay | Grass | Clay minus hard slope | Grass minus hard slope |
|---|---|---|---|---|---|---|
| WTA | 2009–2025 | **−2.9 (−3.5, −2.4)** | +0.3 (−0.6, +1.3) | +0.2 (−1.2, +1.7) | +1.8, p = 0.01 | +2.4, p = 0.001 |
| WTA | 2016–2025 | **−3.0 (−4.5, −1.5)** | +1.2 (−0.7, +3.0) | +0.2 (−1.3, +1.6) | +2.5, p = 0.02 | +1.6, p = 0.16 |
| ATP | 1991–2025 | **−1.4 (−1.8, −0.9)** | **−1.6 (−2.0, −1.2)** | **−1.3 (−2.0, −0.6)** | −0.5, p = 0.13 | +0.1, p = 0.71 |
| ATP | 2016–2025 | **−1.3 (−2.3, −0.2)** | +0.3 (−0.6, +1.2) | −0.5 (−2.1, +1.0) | +2.1, p = 0.01 | +1.4, p = 0.07 |

(The surface-difference columns come from a surface-controlled model, not fixed effects.)

- **WTA:** the decline is a hard-court decline throughout.
- **ATP:** over three decades breaks fell on every surface at a similar pace; in the last ten seasons only the hard-court decline continues.

**Ace rates** (aces per 100 serve points, all seasons pooled):

| Tour | Hard | Clay | Grass |
|---|---|---|---|
| WTA | 3.9 | 2.9 | 4.7 |
| ATP | 8.1 | 5.0 | 8.9 |
| Challenger | 7.4 | 4.3 | 8.6 |

**Data-source switches.** No like-for-like series shows a large, lasting step. The largest year-on-year moves are about three times the typical change: ATP breaks in 2011 (+1.3 points, reversed the next season) and Challenger breaks in 2013 (+1.3). The WTA ace level rose by about 0.4 in 2013–14 and stayed there, which may be real or a recording change; it does not affect the conclusion that WTA aces have been level since 2015.

One known source issue affects early ATP Slam aces (`results/sensitivity_atp_early_slams.csv`). In 1991–99 the ATP Slam files record 6.98 serve points per service game, against 6.38 from 2000 and 6.48 at other ATP events in the 1990s, so the Slam serve-point counts before 2000 look about 9% too high. That understates Slam ace rates before 2000 (the denominator is too large); break rates are not affected, because service games come from the score. Refitting the ATP without the pre-2000 Slams changes little: the whole-period ace trend becomes +0.55 per decade (+0.39 to +0.71) instead of +0.67, the plateau is unchanged (slope change at 2016 −1.22, −1.72 to −0.71, against −1.45), and the break trend is −1.45 (−1.73 to −1.17) instead of −1.40. Without any Slams the results are similar (aces +0.59, breaks −1.53).

### Winners (excluding aces) and unforced errors per point

| Source | Women: winners per 100 points | Trend per decade | Men: winners per 100 points | Trend per decade |
|---|---|---|---|---|
| Slam point-by-point, 2011–24 | 26.5 | **−0.75 (−1.46, −0.04)** | 25.1 | **−1.10 (−1.59, −0.60)** |
| Same, 2011–15 | – | +0.25 (−2.94, +3.45) | – | +0.52 (−2.03, +3.07) |
| Same, 2016–24 | – | **−1.56 (−2.69, −0.42)** | – | **−1.09 (−1.91, −0.27)** |
| US Open + Wimbledon only (one data feed), 2011–24 | – | **−0.98 (−1.72, −0.25)** | – | **−1.01 (−1.58, −0.44)** |
| Match Charting, 2016–25 (clustered by charter) | about 25 | −0.8 (−2.4, +0.8) | about 25 | +5.1 (−3.4, +13.6); **+0.1 (−1.7, +1.8) without one charter** |

By surface (2011–24), the decline is clearest on grass (women −1.6, men −1.3) and on men's hard courts (−1.1); clay shows no clear trend.

**By Slam** (2011–24, or to 2021 for the Australian and French Opens; per decade, 95% CI clustered by edition; `results/trends_winners_by_slam.csv`):

| Slam | Women: level | Women: trend | Men: level | Men: trend |
|---|---|---|---|---|
| Australian Open (2011–21) | 26.5 | −0.9 (−3.4, +1.6) | 25.0 | **−2.0 (−3.2, −0.7)** |
| Roland Garros (2011–21) | 28.2 | +0.2 (−1.8, +2.3) | 26.8 | −0.6 (−2.0, +0.7) |
| US Open | 25.4 | −0.4 (−1.4, +0.6) | 24.2 | −0.7 (−1.5, +0.1) |
| Wimbledon | 26.0 | **−1.6 (−2.6, −0.6)** | 24.8 | **−1.3 (−2.2, −0.4)** |

- **Women:** the pooled decline is mainly a Wimbledon decline; the other three Slams show no clear change.
- **Men:** it is clearest at Wimbledon and the Australian Open. The Australian Open's data changed provider in 2018 (Infosys in 2018–21), so part of its decline may reflect how winners were recorded rather than play.
- **Coding change?** Wimbledon uses one data feed throughout. Its unforced-error rate steps up by about 4–5 points between 2013 and 2014 (figure A5), but its winner rate shows no step then (women 27.2 → 27.6, men 26.8 → 26.3), so a change in winner coding is not apparent.
- **The US Open + Wimbledon check** in the table above is largely carried by Wimbledon.
