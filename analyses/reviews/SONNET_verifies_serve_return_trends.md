# SONNET verifies the fixes to `analyses/serve_return_trends/`

Read `OPUS_response_serve_return_trends.md`, re-ran `make serve_return_trends` and the tests, opened fig2, A4 and checked the README text. My scratch checks are in `scratch/sonnet_review_checks*.py`.

## Reproducibility
- `make serve_return_trends` runs cleanly; a second run gives **byte-identical** `results/` and `figures/` (md5 over every file). `pytest` for the whole repo: 86 passed.

## My required points

| # | Point | Verdict | Evidence |
|---|---|---|---|
| R1 | Name the single-charter driver; cluster charting by charter; retitle fig 4 | **Verified** | `charting_charter_check.csv`: non-Slam men's winners per 100 points 24.5 → 28.5 for all charted matches, **23.8 → 24.0 without the most prolific charter** (mine: 23.8 → 24.1 with a slightly different year window), and 32.3 → 40.9 for that charter alone, as I found. Charter-clustered trend: men's +5.1 (-3.4, +13.6) all, +0.1 (-1.7, +1.8) without. The charter is not named in the outputs. New appendix figure A4 shows exactly this in one panel; its title states the takeaway, no clipping, Okabe-Ito colours, the "(partial)" label is the only note. README now says "one person's coding". |
| R2 | Fix "clustered by tournament"; add tournament-cluster and tournament-FE sensitivity; say the ATP tour-wide trend is not robust | **Verified** | New tournament key (137 WTA, 117 ATP, 504 Challenger tournaments). Tournament-clustered CIs match mine (WTA all -1.24 (-2.35, -0.13); ATP all -0.99 (-1.70, -0.28)). With tournament fixed effects: ATP all **-0.69 (-1.42, +0.03)** (mine -0.74 (-1.81, +0.32)), WTA hard -2.99 (mine -2.82), ATP hard -1.28 (mine -1.26). The rank-deficiency bug they report (`C(surface) + C(tournament)`) is real, and I hit the same `SingularMatrixWarning` in my own check; using `C(tournament)` alone is correct. README states the ATP all-surface decline loses significance and the hard-court declines hold. |
| R3 | Soften "almost entirely from hard courts" | **Verified** | `break_trend_surface_differences.csv`: clay minus hard +2.5 (p = 0.022, WTA; identical to my number) and +2.1 (p = 0.005, ATP; my p = 0.05 was with edition clustering); grass minus hard +1.6 (p = 0.16) and +1.4 (p = 0.07). README now says "concentrated on hard courts... clearly different from clay, not clearly from grass" and that "no change" means not detected. |

Optional points O4 (ace wording), O5 (muted non-hard series in fig2: checked, hard is emphasised, clay and grass are faint and the title reads "...mainly on hard courts") and O6 (`ratio_ci` docstring) are done.

## Remaining small points (optional)
- README line 8 says hard-court breaks fell "by about 2 points per decade"; the estimates are -1.3 to -3.0 depending on the specification (ATP -1.28 with tournament FE). "About 1-3 points" (as in the conclusion) is more accurate.
- The README mentions "SONNET's review" in the charting paragraph; fine for a showcase repo, but a neutral "a review of the data found..." would read better for an outside reader.

## Reader rules
WTA first, takeaway titles, no internal notes in figures, appendix split (4 main figures, A1-A5): all met in what I opened (fig2, A4).

## Verdict: ACCEPT
