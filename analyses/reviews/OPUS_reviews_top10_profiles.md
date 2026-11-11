# OPUS review of `analyses/top10_profiles/` (SONNET)

**Scope.** I read the README and all of the code, ran `make top10_profiles` twice and the tests, and looked at all six figures. My checks are in `analyses/reviews/scratch/check_top10.py` (run from the repo root with `.venv/bin/python -I`). I did not edit the folder under review.

## 1. Correctness

### Headline numbers reproduced independently

I wrote my own code: TML 2025–26 files, the same levels, the 364-day window, the score-based half-each service games, and breaks = opponent's `bpFaced − bpSaved`. Every number I checked matches to 0.1:

| Quantity | SONNET | Mine |
|---|---|---|
| WTA tour hold | 66.0% | 66.0% |
| ATP tour hold | 81.1% | 81.1% |
| Rybakina hold / break | 82.8 / 32.1 | 82.8 / 32.1 |
| Gauff hold / break | 70.8 / 42.3 | 70.8 / 42.3 |
| Zverev BP saved vs serve points won | 62.9 vs 71.3 | 62.9 vs 71.3 |
| Tiafoe BP converted vs return points won | 43.6 vs 35.8 | 43.6 vs 35.8 |

### Specific items

**Sinner override and staleness rule: correct and well documented.**
- The override is limited to one named player, and a test checks this (`test_force_include_overrides_staleness_only_for_named_player`).
- His partial window (to July 2026) is flagged everywhere, and the player who dropped out (Jodar) is named.
- The 84-day staleness rule is a reasonable, transparent heuristic.
- One wording point: "placed ahead of Zverev, also rank 1, on rank points" compares a July ranking with a November one. Say that the order of the top two is not meaningful.

**The half-each service-game expectation: fine, and I checked how big its error is.**
- On 10,114 complete Slam matches with the *observed* serve order (`analyses/serve_first`), the true number of service games differs from half the regular games by 0.27 games per player-match on average.
- Match winners serve slightly more than half: true / half = 1.007, because stronger players more often serve first.
- For a 90% holder that shifts reported hold by −0.07 points, and for a 70% holder by −0.2 points. Both are negligible next to the ±3.5-point CIs.
- A test checks that SvGms is never used.

**Name matching between charting and TML: correct for all 20 players.**
- My surname search finds the same charted-match counts. Sabalenka really does have only 3 charted matches in the window, and Shelton 2.
- `norm_name` strips all non-letters, so "Felix Auger-Aliassime" and "Alex De Minaur" match. My own hyphen-sensitive search missed Auger-Aliassime; theirs didn't.

**Level filter: one small bug.**
- The included levels are `{G, M, 1000, 500, 250, F}`, and level `A` is excluded as "team events".
- In the 2025–26 WTA file, level `A` also contains the **Prague Open**, a regular WTA 250, besides the United Cup.
- So a regular tour event is silently dropped. The effect is small (one 32-draw event), but either exclude `A` by event name, or include `A` minus the United Cup, Laver Cup and Next Gen Finals.

**Bootstrap resample count.**
- `boot_ci` uses 2,000 resamples, but **only 200 when a group has 300 or more matches**, which in practice means the tour-wide references.
- The README says 2,000. Either use 2,000 everywhere or document the switch.
- Separately, the CI is clamped so it always contains the estimate (`min(lo, est)`), which can hide a skewed bootstrap. That is harmless here, but worth one line.

## 2. Statistics

### 2a. The hold-vs-break "trade-off" is largely a selection artefact (required)

**The claim.** The README leads with "Serving and returning trade off … correlation −0.77 for the WTA".

**Why that's misleading.** The top 10 are, roughly, the players with the highest hold + break. Conditioning on a high *sum* creates a negative correlation between the two parts even when there is none in the population.

**Evidence** (players with at least 30 tour matches in the same window):

| Tour | corr(hold, break), all regulars | corr among the 10 with the highest hold + break |
|---|---|---|
| WTA (75 players) | **−0.11** | **−0.86** |
| ATP (71 players) | −0.27 | −0.25 |

**The WTA −0.77 is about what selection alone produces.** Its 95% CI is also wide: −0.94 to −0.28 with n = 10; the ATP's 0.02 has a CI of −0.62 to 0.64.

**Fix.** Present the scatter as "different routes to the top: big servers vs big returners", not as a trade-off. Add the selection caveat, and remove the headline correlation, or put it next to the tour-wide value.

### 2b. Pressure points: compare with the tour gap, and correct for multiplicity (required)

**Wrong reference in the text.** The text reports Zverev −8.3 and Tiafoe +7.8 *against zero* (the player's own baseline). The figure rightly says the comparison should be with the tour-average gap (serve −2.4, return +2.4 on the ATP). Against that reference:

| Player | Gap vs the tour gap | z | p | Holm-adjusted p (40 tests) |
|---|---|---|---|---|
| Tiafoe, BP converted | **+5.4** | 2.8 | 0.005 | 0.22 |
| Svitolina, BP saved | **+5.7** | 2.7 | 0.007 | 0.27 |
| Zverev, BP saved | **−5.9** | −2.0 | 0.05 | 1.00 |

**Neither named outlier survives a correction for the 40 comparisons** (20 players × saved and converted). Zverev is only borderline even before correction. Svitolina is as notable as Tiafoe but isn't mentioned.

**Fix.**
- Report the gaps relative to the tour gap.
- State that with 40 comparisons, two or three uncorrected p < 0.05 results are expected by chance.
- Phrase Zverev and Tiafoe as "the largest deviations, not distinguishable from chance after correction".
- The figure's title ("most sit close to the tour average") is already right.

### 2c. Smaller statistical points

- **Winners–UE correlations** (0.46 ATP, 0.11 WTA) rest on n = 10, including players with 2–3 charted matches. Give CIs or drop the numbers; the figure alone makes the point.
- **Tiebreaks and deciding sets:** the title "most top players win more than half" is fair. Muchova's 10/10 and 14/16 are worth a "small sample" remark.
- **Surface splits per player** rest on 2–25 matches. The README says so, which is good.

## 3. Reproducibility

- `make top10_profiles` runs cleanly in about 2 min 15 s, and two consecutive runs give **byte-identical** CSVs and PNGs.
- The 9 tests pass. They test the meaningful parts: service games from the score, match tiebreaks, retirements dropped, the 52-week window, staleness, the override, bootstrap determinism, and name normalisation.
- **Missing tests:** a test for the level filter (it would have caught Prague), and a test that charting rows outside the window are excluded.

## 4. The user's rules and the figures

**What already follows the rules:**
- **WTA first** in every table, panel and section.
- **Okabe-Ito colours** (WTA orange, ATP blue) with different markers.
- **No clipped text.**
- **Surface results exist** (`hold_break_by_surface.csv`, `tourwide_by_surface.csv`).
- **The README leads with a plain-language answer,** but that answer contains the over-read trade-off (2a).

**Figure by figure:**

| Figure | Verdict |
|---|---|
| `hold_vs_break.png` | Clear and useful. Minor: in the ATP panel the "F. Auger-Aliassime" label sits on the tour-average line. Change the title as in 2a. |
| `hold_vs_break_by_surface.png` | **Does not help a newcomer.** Six dense panels, labels touching (Svitolina/Gauff on WTA hard, Medvedev/de Minaur on ATP clay), many points resting on 2–4 matches, and a process note in the title ("(matches in brackets)"). Move it to an appendix, or replace it with one compact panel of tour-wide hold and break by surface plus the per-player table. |
| `winners_vs_unforced.png` | Fine. The hollow markers for fewer than 5 charted matches are good. The footnote "label shows the number of charted matches" belongs in the caption (reader rule 1). |
| `pressure_vs_baseline.png` | Good: the CI is the message and it's shown lightly, and the reference lines are labelled directly. The README text should match it (2b). |
| `tiebreaks_deciding_sets.png` | Fine. |
| `charted_key_points.png` | **Hard to read.** Three point estimates per player with no CIs, players with 2–4 charted matches given equal weight, and differences that are mostly within ±5–10 points. The title states a pattern the eye can't verify. Make it an appendix figure, or show only the tour-wide charted reference (break, game and deuce points) with CIs and keep the per-player numbers in the table. |

## Verdict: **ACCEPT WITH MINOR CHANGES**

The data work is solid: I reproduced every number I checked, the override is transparent, and the half-each approximation is negligible. The changes are about interpretation.

**Required**
1. Reword the hold/break headline. The negative correlation among the top 10 is mostly selection on hold + break (WTA: −0.11 among all regulars against −0.86 for a top 10 selected that way). Present it as "different routes to the top", with the caveat.
2. Pressure points: report the gaps against the tour-average gap, not zero. Add a multiplicity statement: with 40 comparisons, Tiafoe +5.4, Svitolina +5.7 and Zverev −5.9 do not survive Holm correction. Mention Svitolina or none of them.
3. Level filter: the WTA Prague Open (level `A`) is wrongly excluded. Fix it by event name or document it.
4. Move `hold_vs_break_by_surface.png` and `charted_key_points.png` to an appendix, or simplify them, and take the process notes out of titles and legends.

**Optional**
5. Use 2,000 bootstrap resamples everywhere, or document the 200 used for tour-wide references.
6. Give CIs (or drop) the winners–UE correlations with n = 10.
7. Add tests for the level filter and the charting window.
8. Say explicitly that the order of Sinner and Zverev (both rank 1, at different dates) is not meaningful.
