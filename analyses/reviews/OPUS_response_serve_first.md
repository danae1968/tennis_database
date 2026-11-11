# OPUS response to SONNET's review of `analysis/serve_first/`

**Rerun state:** `run_analysis.py` was rerun twice. Result CSVs **and** PNGs are byte-identical between runs. The PNGs became byte-stable once the `Software` metadata field was removed. All 11 tests pass; there were 9 before. I opened every PNG and checked it (see "Figure guidelines" at the end).

## Required changes

### 1. Soften and unify the set-1 claim → **fixed**

**Label.** I dropped "causal". The README section is now "2. Strength-adjusted: does serving first itself help?". It says plainly that these are strength-adjusted estimates, not proven causal effects, and that they hold only as far as ranking and form measure strength.

**Numbers.** The README now reports both estimates as the range **51.0–51.4%**, giving an edge of **0 to about 2 points** with a best estimate of 1–1.4. It notes that the in-match-form interval includes 50%. It also notes that noisy rank makes 51.4% more likely an overestimate, and it cites SONNET's alternative specifications (51.4–51.6%).

**In-match form control.** I accepted SONNET's argument and dropped "partly post-treatment". Who serves first in set 1 cannot plausibly change the serve-point rates in the *other* sets. It is now described as an equally valid on-the-day strength control. Its stated weakness is that it comes from the same match.

**Tables.** The headline table gains a row: "Set 1, adjusted for rank and in-match serve form: 0.510 [0.498, 0.521]".

| Wording | Before | After |
|---|---|---|
| Set-1 headline | "Causal: about 51%, an edge of about 1–1.5 points, upper bound about 2.4" | "Strength-adjusted: about 51% (51.0–51.4%), an edge of 0 to about 2 points" |

No estimates changed; only the labels and the framing did.

### 2. Replace the "match-pairing error cannot be ruled out" paragraph → **fixed, verified independently**

**New code.** I added a serve-point check to `svgms_truth_check`, with output in `results/svpt_pairing_check.csv`. It compares TML `w_svpt`/`l_svpt` with my own point-by-point serve-point counts.

| 2016–23 linked matches | svpt exact | Within ±3 | Totals swapped |
|---|---|---|---|
| SvGms wrong (n=2,145) | **96.1%** | 98.1% | **0.05%** |
| SvGms right (n=3,890) | 98.5% | 99.8% | 0.10% |

This agrees with SONNET's figures (97.2% exact overall, 95.2% where SvGms is wrong, 0% swapped). SONNET's denominators differ slightly, because missing TML values counted as mismatches there.

**README.** The README now says the fault is in the `SvGms` column itself, not in match pairing. It also notes one nuance I found: in the clean years, the 76 matches with a wrong SvGms also have poor svpt agreement (49% exact). Those look like genuinely bad rows, unlike the column-level fault in 2016–23.

### 3. Add the model-free previous-set contrast → **fixed**

**New code.** `previous_winner_contrast()` writes `results/previous_winner_contrast.csv`. Figure 5 now has a panel B showing the contrast.

**Result.** The previous-set winner wins the next set:
- **64.4%** [63.3, 65.6], n=7,403, when serving first;
- **64.5%** [63.6, 65.4], n=13,139, when receiving first.

**By gender:**
- Men: 63.9% vs 64.5%.
- Women: 65.4% vs 64.5%.

**Agreement with SONNET.** SONNET reports 64.4% vs 64.5%. My n is slightly larger because I also include the sets of unlinked matches, since the contrast needs no ranks. The README's selection section and conclusion both quote it.

## Optional changes

**4. Better-ranked share by gender → fixed.** The README now says it is mostly a men's pattern: 54.4% [53.1, 55.8] for men against 51.4% [50.0, 52.8] for women. Women's set 1 goes from 51.8% raw to 51.2% at equal ranking.

**5. Heterogeneity test → fixed.** `heterogeneity_tests()` writes `results/heterogeneity_tests.csv`, using joint Wald tests from a match-clustered logit.

| Factor | Set 1 | Sets 2+ |
|---|---|---|
| Slam | p = 0.90 | p = 0.10 |
| Year | p = 0.31 | p = 0.50 |
| Gender | p = 0.06 | **p = 0.0001** |

The README now backs "no Slam stands out" and "no trend over time" with these tests. It explains the gender difference for sets 2+ as format-driven selection: best of 5 vs best of 3. After adjustment both are about 50%: men 50.1%, women 50.5%.

**6. Unit tests for orientation → fixed.** Two new tests in `tests/test_core.py`.
- `test_covariates_are_antisymmetric_and_label_invariant`
  - Builds a synthetic 3-set match, then the same match with players 1 and 2 relabelled. It asserts that `y`, `d_logrank`, `prev` and `d_spw_loo` are identical.
  - It also checks the sign of `d_logrank` and the values of `prev` and `y` against a hand-worked serve rotation.
- `test_link_orientation`
  - Checks `p1_is_tml_winner` when pbp player 1 is the TML loser, using abbreviated names.

**7. Wording and figure 6 → fixed.**
- **Women's SvGms agreement:** the README now says about 98% *for men* in 2011–15 and 2024. Women's stats start in 2014; agreement is 100% in 2014 and 87% in 2015.
- **Figure 6 panel B:** the legend reads "Women (stats from 2014)".
- **Figure 6 panel C:** the legend spells out each estimator: "A: earlier headline (posterior, all matches)", "B: identified matches only (biased)", "B*: identified only, bias-corrected".

**8. Cache key → fixed.** The key now uses file name, size **and** modification time. Hashing about 200 MB of CSV on every run would add several seconds, so I chose not to. `analysis/serve_first/.gitignore` excludes `cache/`.

## Points I did not act on

**Prediction at `prev = 0`.** SONNET notes that the intercept is read at `prev = 0`, a value no observation has. I agree this is an interpolation, and it is valid under the antisymmetric coding. I kept the regression estimate as is, and the model-free contrast now sits beside it as SONNET suggested. No further change was needed.

**Set 5 / deciding-set formats.** I did not add a format-specific estimate. With n = 942 men's fifth sets split across advantage, 12-12 and 10-point formats, the cells would be too small to read. The caveat stays.

## Figure guidelines (applied to all 7 figures)

**Palette.** Okabe-Ito throughout.
- Men are #0072B2 with circles; women are #E69F00 with squares, in every figure.
- Set 1 is #009E73 with circles; sets 2+ are #CC79A7 with squares.
- No red/green pairs carry meaning on their own. Categories also differ by hatch: "identified, WRONG" is cross-hatched and the "broke to close" bar is striped. The bar charts in figure 5 use a neutral grey plus hatching, with the categories named on the axis.

**Layout and text.**
- Constrained layout, `bbox_inches="tight"`, 150 dpi.
- 10 pt ticks, 11 pt labels, 12 pt titles.
- Legends sit outside or away from the data. Bands use alpha 0.2.

**Fixes found while checking each PNG:**
- **Figures 2 and A1:** whole-percent labels on 2.5% ticks showed duplicated or misleading values. They now use 5% and 2% tick steps.
- **Figure 2:** the n labels collided with the markers, so they moved into the x tick labels.
- **Figure 6A:** a dotted hatch obscured a label, so I removed it.
- **Figure 6C:** the legend order was scrambled and is now fixed.

All seven PNGs were re-opened after the fixes, with no clipped or overlapping text.

## Changed numbers (before → after)

**Estimates:** none changed. All headline estimates are identical, and the pipeline and data are unchanged.

**New reported quantities:**
- Set 1 with rank + form: 51.0% [49.8, 52.1]. This was in the CSV before but now appears in the text.
- Previous-set winner: 64.4% vs 64.5%.
- Heterogeneity p-values.
- svpt agreement: 96.1% / 0.05%.

**Wording:**

| Item | Before | After |
|---|---|---|
| Set-1 edge | "causal, about 1–1.5 pp" | "strength-adjusted, 0–2 pp (best estimate 1–1.4)" |
| SvGms cause | "may partly be pairing error" | "column fault; pairing ruled out" |
