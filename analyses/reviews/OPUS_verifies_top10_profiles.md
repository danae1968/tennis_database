# OPUS verification of SONNET's fixes: `analyses/top10_profiles/`

**Rerun.** `make top10_profiles` exits 0. `pytest tests/top10_profiles` passes 12 tests, up from 9.

| My required point | Status | Evidence |
|---|---|---|
| 1. Hold/break "trade-off" is selection | ✔ Fixed | See point 1 below |
| 2. Pressure gaps vs the tour gap, with multiplicity | ✔ Fixed | See point 2 below |
| 3. Level filter (WTA Prague Open) | ✔ Fixed | See point 3 below |
| 4. Secondary figures to an appendix; no process notes | ✔ Fixed | See point 4 below |

**1. Hold/break selection.**
- `results/selection_check.csv` reproduces my numbers exactly:

| Tour | All regulars | Top 10 | Best 10 by hold + break |
|---|---|---|---|
| WTA | −0.11 (−0.33 to 0.12) | −0.77 | −0.86 |
| ATP | −0.27 | 0.02 | −0.25 |

- The README now explains Berkson's paradox in plain words.
- It says the ATP correlation is not meaningful with 10 players (−0.38 → 0.02 when Sinner was added).
- The main figure title is "different routes to the top". The new appendix figure A1 shows all regular players with the top 10 highlighted, and it makes the point at a glance.

**2. Pressure points.**
- `results/pressure_tests_holm.csv` compares each gap with the tour gap, with one Holm correction across all 130 comparisons.
- Uncorrected p < 0.05 in 10 tests (about 6.5 expected by chance); **0 survive Holm.**
- Tiafoe +5.4 (Holm p 0.62), Svitolina +5.7 (0.90; now mentioned), Zverev −5.9 (1.0).
- The README conclusion is now "about as their normal level predicts; no player stands out reliably". Correct.

**3. Level filter.**
- `TOUR_LEVELS` now includes "A", with the United Cup, Laver Cup and Next Gen Finals excluded by name, and a test covers it.
- I checked that this changes no numbers. The level-"A" Prague Open (2025-07-21) lies before the WTA window, which starts on 2025-11-04. The 2026 edition is recorded as "Prague", level 250, and was always included.

**4. Figures.**
- The by-surface and charted key-point figures are now appendix figures A2 and A3.
- The process notes have moved from titles and legends to captions.
- The key-point title no longer claims a pattern ("…mostly within the noise").

## The partial decline: charted tests only for players with ≥ 10 charted matches

**Reasonable, and I agree with it.**
- With 2–6 charted matches, a match bootstrap has almost no distinct resamples. Its SD collapses, so any z-test gives spurious tiny p-values; SONNET found p ≈ 1e-11 for Shelton with 2 matches.
- Leaving those players untested is the conservative choice.
- Their points are still shown, flagged with * as fewer than 5 matches, and the threshold is documented in the README.

**One alternative, if wanted later:** treat the per-player key-point numbers for under-charted players as purely descriptive. That is effectively what the README now does.

## Spot-check against the reader rules

| Figure | Verdict |
|---|---|
| `hold_vs_break.png` | Takeaway title; WTA first; Okabe-Ito colours with marker shapes; nothing clipped. Minor leftover: the "F. Auger-Aliassime" label still sits on the ATP tour-average line. |
| `hold_vs_break_all_players.png` | New and clear; makes the selection point in 5 seconds. |
| `winners_vs_unforced.png` | The title still says "more winners tends to come with more unforced errors for the men", while the README now says the correlation (0.46, CI −0.24 to 0.85) is not distinguishable from zero. A softer title would match the text, e.g. "Winners and errors vary widely; no clear link with ten players". Optional. |
| `charted_key_points.png` (appendix) | Still dense, but acceptable as an appendix figure with an honest title. |

## Verdict: **ACCEPT**

All required points are fixed, the partial decline is justified, and the headline numbers are unchanged where they should be. Optional cosmetic items:
1. Soften the winners/unforced-errors figure title to match the README.
2. Nudge the Auger-Aliassime label off the reference line.
