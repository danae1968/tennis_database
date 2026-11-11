# OPUS review of `analysis/birth_months/` (SONNET)

**Scope.** I read all code, the README and the figures. I re-ran the pipeline and the tests, and wrote independent checks in `analysis/reviews/scratch/check_birth_months.py` (run from the repo root with `.venv/bin/python -I`). I did not edit the folder under review.

## 1. Correctness

**Headline numbers, reproduced independently** with my own parsing and joins (no shared code):

| Population | SONNET | My check |
|---|---|---|
| ATP+WTA played | n=8,087, χ²=97.2, p=6.3e-16, Q1/Q4=1.33 | n=8,087, χ²=97.2, p=6.3e-16, Q1/Q4=1.327 ✔ |
| ATP played | n=4,776, χ²=63 | n=4,776, χ²=62.6 ✔ |
| WTA played | n=3,311, χ²=42.5 | n=3,311, χ²=42.5 ✔ |
| ATP+WTA all | n=29,098, χ²=441 | n=29,102, χ²=440.8 ✔ (I skipped the name + birthdate dedup, which accounts for the 4 rows) |

**Joins and gender labels.**
- 99.9% of ATP match IDs are found in `ATP_Database.csv`.
- Men and women come from separate files, so there is no labelling risk.
- Dedup by ID and by name + birthdate is sensible and covered by tests.

**One factual error in the README.** The README says "WTA match data for 2018+ come from a source whose player IDs are mostly missing from `players.csv`, so WTA players who debuted after ~2017 are largely missing". This is not what the data show. The share of each year's WTA tour players who are in `players.csv` *with a birth date*:

| Year | Share present with birth date |
|---|---|
| 2018 | 93.7% |
| 2020 | 88.9% |
| 2022 | 81.4% |
| 2024 | 71.3% |

So coverage declines for recent debutants but is far from "mostly missing". The modest WTA "played" count (3,311) mainly reflects that the WTA tour-level files start in 1990: there are 3,646 distinct IDs in SONNET's sources, minus those without a birth date. Please correct the sentence.

## 2. Placeholder dates (specific question)

**ATP is handled correctly.**
- 1 January is 2.2× the uniform rate, and dropping all ATP 1-Jan dates is a reasonable, conservative choice.
- After that, 15th-of-month is not heaped (p=0.33).
- Day 1 pooled over months is mildly high (p=0.004), but almost all of the excess is 1 January.

**WTA has undetected heaping, but it is confined to the "all" population.**

| Check | WTA "all" | WTA "played" |
|---|---|---|
| 1-Jan, relative to 1/365.25 | 1.61× overall (1.83× for the 1990s birth cohort) | Too few to judge |
| Share of January births on days 1–10 | **35.3%** vs 32.3% expected, p=0.003 (about 60 surplus January births) | 32.5% vs 32.3%, p=0.91 |

- In "all", the most over-represented calendar days are 1-1, 1-5, 1-10 and 1-2, which points to rounded or placeholder dates among low-level players.
- The detector misses this for two reasons. It only tests day 1 against days 2–28 within each month, and its threshold (Bonferroni at α=0.001/12) is very strict for a check whose purpose is to *protect against bias*. A false alarm costs little, while a miss inflates January.
- **Impact on the headline:** negligible. Dropping WTA 1-Jan in "played" moves Q1/Q4 from 1.327 to 1.319, χ²=94.
- **Impact on "all":** it does contribute. The all-player January ratio is 1.18, against 0.98 for the elite group (fig. 5). The README table leads with "all".

## 3. General-population baseline (specific question)

**Yes, it should be added as a sensitivity analysis.** It does not need to replace the uniform baseline.

**How.** Weight monthly birth shares by each player's nationality and birth year. UN Demographic Yearbook monthly live births by country cover most player nations from the 1960s.

**Expected magnitude.** Typical national seasonal amplitudes are about ±5–10%, well below the observed Q1/Q4 gap of about 30%. The direction varies: several Western European countries historically peaked in spring, while the US and others peak in late summer. So I expect a baseline to change the size of the effect a little, not its existence. This is from general knowledge, not computed here, so the README's caveat is appropriately worded.

**A cheap internal check.** The relative age effect (RAE) predicts the same Jan→Dec gradient in both hemispheres, because tennis age groups use a 1 January cut-off everywhere. Birth seasonality is roughly reversed between hemispheres. So a pooled ATP+WTA southern-hemisphere Q1/Q4 with a CI would be informative. The current ATP-only southern split (n=808, p=0.27) is underpowered and is described too weakly to support either reading.

## 4. Statistics

**Trend test p-value is anti-conservative.**
- `trend_test` fits a quasi-Poisson model with `scale="X2"`. On 12 monthly counts the estimated scale is **0.61**, which is below 1, and that shrinks the standard error.
- Reported: SE 0.0025, p = 1.8e-34.
- With scale fixed at 1: SE 0.0032, p = 1.4e-21.
- Use `max(scale, 1)`, or report the Poisson SE. The conclusion is unchanged, but "p < 1e-30" overstates it.

**Other points:**
- The χ² test with df=11, the Clopper-Pearson month intervals and the Holm correction across months are all appropriate.
- Many population splits (decades, hemispheres, elite definitions) are tested without multiplicity control. Present them as descriptive, which the README mostly does already.
- The independence assumption (country cohorts) is acknowledged.
- Cramér's V of 0.03–0.04 is reported honestly as a small effect.

## 5. Reproducibility and practice

- `run_analysis.py` runs cleanly in about 50 s, and the outputs are **byte-identical** on re-run: all results and figures matched my checksums.
- The 7 tests pass. They test meaningful things: date parsing edge cases, dedup, the placeholder detector and expected counts.
- There are no absolute paths.
- **Fresh-state caveat:** I re-ran over the existing outputs; I did not delete them first. The code has no cache, so this should be equivalent.

## 6. Communication

**Fig 1** has several problems:
- The title is clipped on the right.
- The bars start at 0, which visually hides 15–20% differences.
- The legend sits on top of the January–May bars.
- The "naive average N/12" line adds confusion next to the days-adjusted expectation.

**Suggestions:**
- Make fig 2 (the ratio with CIs) the lead figure. It is the clearest chart in the project.
- Drop fig 1, or redraw it as observed − expected.

**Colour.** The user's new figure guidelines apply: Okabe-Ito colours, ATP=#0072B2 and WTA=#E69F00 consistently, `bbox_inches="tight"`, and fonts of at least 10/11 pt.

**README:**
- The results table leads with "ATP+WTA, all", which is the population most affected by placeholder heaping. Lead with "played", as the figures do.
- The interpretation and caveats are otherwise clear and honest.

## Verdict: **ACCEPT WITH MINOR CHANGES**

The core finding is robust: early-year births are over-represented by about 33% Q1 vs Q4 among players with tour matches, consistent with the relative age effect. I reproduced it exactly.

**Required**
1. Correct the README claim that 2018+ WTA player IDs are "mostly missing". Coverage is 94% falling to 71%.
2. Fix the trend-test SE: use scale ≥ 1, giving p ≈ 1e-21 rather than 1e-34.
3. Lead the results table and the text with the "played" population. Note in the README that WTA "all" has early-January heaping (35.3% of January births on days 1–10, p=0.003) that inflates January in that population.
4. Fix fig 1: the clipped title, the legend over the data, and the zero-based bars. Apply the colour-blind palette guidelines to all figures.

**Optional**
5. Make the placeholder detector less strict. For example: α=0.05 per month, an additional test of days 1–10 of January, and a sensitivity run that drops WTA 1-Jan.
6. Add a general-population birth-seasonality baseline (UN monthly births weighted by nationality and birth year), or at least a pooled southern-hemisphere Q1/Q4 with a CI.
7. Label the decade and hemisphere splits as exploratory.
