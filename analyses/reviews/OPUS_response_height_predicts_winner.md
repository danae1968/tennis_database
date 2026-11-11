# OPUS response to SONNET's review of `analyses/height_predicts_winner/`

**Rerun state.** `make height_predicts_winner` and `make test` (86 passed) both run cleanly. I re-opened figures 1–3 and A1.

| # | Review point | Action | Before → after |
|---|---|---|---|
| R1 | Soften "statistically reliable" for the WTA | **Fixed** | See below |
| R2 | "Works through the serve" → an association, with a CI on the share explained and the return-skill placebo | **Fixed** | See below |
| O3 | Drop the intercept in the antisymmetric logits | **Fixed** | See below |
| O4 | Height × surface interaction test | **Fixed** | See below |
| O5 | WTA sensitivity on high-coverage years; label the mechanism sample | **Fixed** | See below |
| O6 | Put the 63–64% ranking benchmark next to the 54% headline; end the fig 1 line at the data range | **Fixed** | The first table in the README now has a "Ranking only" column; the fitted line ends at the 99th percentile of the gap |

## R1: WTA gain

**Before:** "statistically reliable but tiny".

**After:**
- **WTA:** "borderline" (AUC gain CI 0.0000–0.0035).
- **ATP:** "small but clear" in log-loss and AUC (CIs 0.0003–0.0017 and 0.0006–0.0027).
- **Both:** "no gain in correct picks". The accuracy gain CIs are −0.5 to +0.5 (WTA) and −0.4 to +0.2 points (ATP).

The README also notes that the match bootstrap is somewhat optimistic, because matches of the same player are correlated.

## R2: association with the serve

**Changes:**
- Added the previous season's return points won (`rpw`), with at least 300 serve and 300 return points required.
- Added a 200-replicate tournament bootstrap for the share of the height log-odds accounted for.
- Labelled the sample as **established players** (14,453 WTA and 19,742 ATP matches).

**Share of the height effect accounted for (bootstrap 95% CI):**

| Control added | WTA | ATP |
|---|---|---|
| Serve points won | 48% (31–73%) | 69% (43–97%) |
| Ace rate | 60% (38–89%) | 7% (−27 to 42%) |
| Return points won (placebo) | −15% (−26 to −7%) | −66% (−110 to −40%), i.e. the height effect gets larger |
| Serve and return points won together | 30% | 8% |

**New finding: holding both serve and return records fixed leaves most of the height effect in place.** So the README now says height's edge "goes hand in hand with a better serve (and a slightly weaker return)… these data cannot separate cause from correlation". "Works through the serve" was dropped.

## O3: intercept

The models no longer have an intercept: by symmetry, P = 0.5 at zero differences.

| Model | Before | After |
|---|---|---|
| Height only | WTA 53.7%, ATP 54.3% | 53.6%, 54.3% |
| Ranking + height | 63.0%, 64.0% | 63.0%, 63.9% |
| Ranking only | 62.8%, 64.0% | 63.0%, 64.0% |

## O4: height × surface interaction

`results/height_by_surface_interaction.csv`, a joint Wald test given ranking:
- **WTA:** p = 0.61, with no surface difference.
- **ATP:** p < 0.001, with OR per 10 cm of 1.11 on hard, 1.00 on clay and 1.24 on grass.

The README now limits the surface claim to the ATP.

## O5: sensitivity

**High-coverage WTA test** (`results/wta_high_coverage_sensitivity.csv`): testing on WTA 2025 only, when 92% of heights are known, gives the same picture.

| Model | Accuracy |
|---|---|
| Height only | 53.7% |
| Ranking only | 61.1% |
| Ranking + height | 62.0% |

The mechanism sample is now labelled "established players" (see R2).

## Figures and the reader rules

- **Main text:** figures 1–3. **Appendix:** height coverage (A1).
- The titles are unchanged, because they already state the takeaway.
- The fig 1 curve now stops at the data range.
- No clipping.
