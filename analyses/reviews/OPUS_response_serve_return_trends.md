# OPUS response to SONNET's review of `analyses/serve_return_trends/`

**Rerun state.** `make serve_return_trends` and `make test` (86 passed) both run cleanly, and I re-opened every changed figure.

| # | Review point | Action | Before → after |
|---|---|---|---|
| R1 | Charting jump: name the single-charter driver, cluster charting by charter, retitle fig 4 | **Fixed** | See the charting section below |
| R2 | "Clustered by tournament" was really tournament-edition; add tournament-cluster and tournament-FE sensitivity; state that the ATP tour-wide trend is not robust | **Fixed** | See the clustering section below |
| R3 | Soften "almost entirely from hard courts" | **Fixed, with a test** | See the hard-court section below |
| O4 | "±0.3" ace wording | **Fixed** | "about ±0.3 per 100 serve points per decade or smaller" (Challenger −0.32) |
| O5 | Fade the non-hard bands in fig 2 | **Fixed** | Hard is emphasised, clay and grass are muted; title "…mainly on hard courts" |
| O6 | `ratio_ci` docstring note about few clusters | **Fixed** | `src/tennis/stats.py` |

## R1: charting jump

**Results files:** `results/charting_charter_check.csv`, `trends_charting_by_charter_cluster.csv` and `yearly_charting_nonslam_by_charter_sample.csv`.

**What the data show** (I reproduced your finding):
- The most prolific charter, identified from the data and not named in the outputs, charted 31% of men's non-Slam matches since 2022 and no women's matches.
- That charter's own rate is 32.3 → 40.9 winners per 100 points.
- **Without that charter, the rate is flat: 23.8 → 24.0.**

**Charting trends are now clustered by charter:**

| Men's charting trend (per decade) | Before | After |
|---|---|---|
| All charted matches | +5.1 (+3.8, +6.4), clustered by tournament-year | +5.1 (−3.4, +13.6), clustered by charter |
| Without the most prolific charter | – | **+0.1 (−1.7, +1.8)** |

**Figures:**
- The old fig 4 ("winners jump after 2021") is replaced by appendix figure A4, "The jump in charted men's winners comes from one charter's matches". It has a single ATP panel, because the charter recorded no women's matches.
- The yearly charting CIs (figure A3) are also clustered by charter now.

**README:** it now says "one person's coding", not "which matches are charted".

## R2: clustering

**Clustering.** I added a `tournament` key: the same event across years, matched by name. There are 137 WTA, 117 ATP and 504 Challenger tournaments. All tour trends now cluster on it.

**Tournament fixed effects** are a new sensitivity, in rows "…tournament fixed effects" of `trends_tml.csv`.

**A design bug, found and fixed.** Surface is constant within a tournament, so `C(surface) + C(tournament)` was rank-deficient. That produced invalid standard errors and the absurdly wide WTA interval (−4.7, +1.9) in my interim run. The fixed-effects model now uses `C(tournament)` alone, which absorbs surface.

**Break trends, per decade:**

| Tour | Clustered by edition (before) | Clustered by tournament (now) | Tournament fixed effects (now) |
|---|---|---|---|
| WTA, all surfaces | −1.24 (−2.12, −0.37) | −1.24 (−2.35, −0.13) | **−1.31 (−2.56, −0.07)** |
| ATP, all surfaces | −0.99 (−1.85, −0.12) | −0.99 (−1.70, −0.28) | **−0.69 (−1.42, +0.03), not significant** |
| WTA, hard | – | −2.06 (−3.45, −0.67) | **−2.99 (−4.47, −1.51)** |
| ATP, hard | – | −1.79 (−2.82, −0.77) | **−1.28 (−2.35, −0.22)** |

The README states plainly that the ATP all-surface decline is not robust to tournament fixed effects, while the hard-court declines are.

## R3: "concentrated on hard courts"

**New test:** a year × surface interaction (`break_trend_surface_differences.csv`).

| Tour | Clay minus hard slope | Grass minus hard slope |
|---|---|---|
| WTA | +2.5 points per decade (p = 0.02) | +1.6 (p = 0.16) |
| ATP | +2.1 (p = 0.005) | +1.4 (p = 0.07) |

**Wording:**
- Before: "comes almost entirely from hard courts".
- After: "concentrated on hard courts… clearly different from clay, but not clearly different from grass". The README also says that "no change on clay or grass" means not detected, not shown to be zero.

## Figures and the reader rules

**Main text** (4 figures): aces by surface, breaks by surface, Slam winners, and the source comparison.

**Appendix** (A1–A5): aces by tour, breaks by tour, charting by surface, the one-charter figure, and unforced errors.

The run deletes stale PNGs before redrawing. Every changed PNG was re-opened, with no clipping and no internal notes.

## Headline changes

- **Breaks:** "slightly rarer, mainly on hard courts". The ATP all-surface decline is now flagged as calendar-sensitive.
- **Men's charting trend:** "+5 per decade, selection" became "+5 per decade, one charter; flat without that charter".
