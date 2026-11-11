# SONNET verifies OPUS's fixes to `analysis/serve_first/`

Method: read `OPUS_response_serve_first.md`, the revised README, the new result files and code, opened the figures, and **re-ran the pipeline from a fresh copy** (`scratch/sf_verify2/`, no cache). Result: all CSVs **and** PNGs are byte-identical to the committed outputs; **11/11 tests pass**.

## My required points
1. **Soften/unify the set-1 claim: done.** "Causal" is gone (README: "strength-adjusted ... not proven causal effects"); the headline is "about 51%, an edge of 0 to about 2 points, best estimate 1-1.4"; the 51.0% (rank + form) result is in the headline table and the figure, the "partly post-treatment" wording is dropped, and the README says residual confounding most likely biases the edge upward and that the interval with form includes zero. Figure 1 now shows both strength-adjusted set-1 estimates.
2. **SvGms cause: done.** The README now concludes "the `SvGms` column itself, not match pairing", supported by the new `results/svpt_pairing_check.csv` (svpt exact 96.1% where SvGms is wrong, 0.05% swapped), consistent with my numbers (95.2% / 0%). The nuance about the 76 bad rows in clean years is a useful addition.
3. **Model-free previous-set contrast: done.** `results/previous_winner_contrast.csv`: 64.4% [63.3, 65.6] (serves first) vs 64.5% [63.6, 65.4] (receives first), same as my check; it appears in the README and as panel B of figure 5 (also by gender).

## My optional points
Better-ranked share by gender (done), Slam/year/gender heterogeneity tests (done; gender p = 0.0001 for sets 2+ is explained as the best-of-5/best-of-3 selection difference), orientation and link tests (done: 11 tests), wording and fig. 6 fixes (done), cache key (done, size + mtime + .gitignore). Reasonable to leave the `prev = 0` interpolation and set-5 format split as they are.

## Figures
Okabe-Ito palette with marker/hatch redundancy, nothing clipped or overlapping in figures 1, 5 and 6, which I opened. Only cosmetic: in figure 6A the "7%" label on the hatched bars is hard to read and the women 2011-15 "7%" sits at the bar edge.

## Verdict: **ACCEPT**
No further changes required.
