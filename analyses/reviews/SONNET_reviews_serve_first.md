# SONNET's review of `analysis/serve_first/` (revised version)

Reviewer: SONNET. Scope: `README.md`, `src/`, `results/`, `figures/`, `tests/`. I did not edit that folder. All my checks are in `analysis/reviews/scratch/` (`sonnet_serve_first_checks.py`, `sonnet_svgms_check.py`, plus a full copy re-run in `scratch/sf_copy/`).

## Summary
This is careful, well documented work. The pipeline reproduces (all 9 tests pass, and a fresh re-run from a copy without the cache gives **byte-identical CSVs**, ~80 s), the ground-truth construction is checked against an independent rule (99.96% parity agreement), and the central argument (set 1 is partly selected on strength; sets 2+ are selected through who lost the previous set) is sound. The raw numbers I recomputed match: set 1 raw 52.7%, first server better ranked 53.0% (n = 10,275), rank-adjusted set 1 51.4%, sets 2+ rank+previous-set 50.3%.

The main weaknesses are framing, not computation: the "causal" ~51% is presented with more precision than the strength control can support, and the SvGms cause can be pinned down much better than the README does.

## Specific questions in the brief

### 1. Is the rank-adjusted set-1 estimate (51.4%) robust? Mostly yes, with a caveat on how it is framed.
Re-estimated with the same clustered logistic set-up (`P(first server wins)` at equal strength; linked set 1, n ≈ 10,250-10,275):

| strength measure | adjusted P | 95% CI |
|---|---|---|
| none (raw, linked) | 52.7% | 51.8-53.7 |
| ln rank (paper) | 51.4% | 50.3-52.4 |
| ln rank + cubic term | 51.4% | 50.3-52.4 |
| ln(rank points + 1) | 51.6% | 50.5-52.6 |
| ln rank + ln rank points | 51.5% | 50.4-52.5 |
| 1/rank | 51.6% | 50.6-52.5 |
| sqrt rank | 52.0% | 51.0-53.0 |
| linear rank | 52.5% | 51.5-53.5 |
| ln rank + top-32 indicator | 51.4% | 50.3-52.4 |
| ln rank, unranked dropped / both top 200 | 51.4-51.5% | ~50.4-52.5 |
| ln rank + leave-set-out serve form (paper's sensitivity) | **51.0%** | **49.8-52.1** |
| men / women, ln rank | 51.5% / 51.2% | 50.0-53.0 / 49.7-52.7 |

- Average marginal edge on the probability scale over the actual rank gaps: +1.2 pp. So the edge at "equal ranking" is a fair summary.
- All sensible specifications (log or rank points, with or without extra terms) sit at **51.4-51.6%**. Linear and sqrt rank are worse functional forms (they leave more of the strength gradient unexplained, hence higher estimates), so I would not use them, but it shows the estimate depends on how well strength is captured.
- The rank proxy is **noisy** (pre-tournament rank, not on-the-day strength), so adjustment is incomplete and any residual confounding **biases the edge upward**. The better-form control moves the estimate to 51.0% and the CI then **includes 50%**. The README says that control is "partly post-treatment, so a sensitivity check only". I disagree with that caution: the first server of set 1 cannot plausibly affect serve-point win rates in other sets of the same match, so this variable is a measure of on-the-day strength (a confounder proxy), not a mediator. I would treat 51.0% as an equally valid (better-adjusted) estimate. A fair summary is **"an edge of 0 to about 2 pp, best estimate 1-1.4 pp"**. The text and figure title ("barely matters") are consistent with this, but "About 51% ... upper bound about 2.4" and the label "causal" suggest more certainty than there is; see required change 1.
- Rank sign/orientation is right: the `d_logrank` coefficient is +0.48 (strong, correct sign), first-server-better-ranked share is 53% in both the paper and my recomputation, so no pairing/orientation error in `build_analysis_table`.

### 2. Is "previous set result" an appropriate control for sets 2+? Yes, and it can be validated more transparently.
Conceptually: who opens set k+1 is determined by the parity of games in set k, hence by who held/broke at the end of it, so the previous-set winner is the right pre-treatment confounder. The estimate (50.3%) is stable to extra controls and splits:
- rank + previous set + current sets lead: 50.3%; set 2 only 50.2% [49.0, 51.3]; set 3 only 49.9%; set 4 only 50.0%; set 5 only 53.4% (n = 942, CI 49.8-56.8, too small to read); men 50.1%, women 50.5%; adding prev × rank interaction: 50.4%.
- A **model-free check**, which I would add to the README: among sets 2+, ask "does the previous-set winner win this set?" depending on who serves first. **P(prev winner wins) = 64.5% when they receive first (n = 13,064) and 64.4% when they serve first (n = 7,306).** No ranking adjustment is needed to see there is no serve-order effect here (the rank gap of the previous winner is, if anything, slightly smaller when they serve first: mean ln-rank gap 0.55 vs 0.61, which would mean a tiny positive edge after adjustment, in line with +0.3 pp).
- Caveat: the logistic intercept is read at `prev = 0`, which no set 2+ observation has (prev is ±1). That is a model-based interpolation, though it is fine under the symmetric/antisymmetric coding the README explains. The model-free contrast above is more convincing and should accompany it.

### 3. Is the 52.7%-vs-51% framing correct and clear? Correct in substance; three wording issues.
- The explanation (a toss decides who *chooses*; the better-ranked player serves first 53.0% [52.0, 53.9]) is clear and correct. "About half of the raw edge is strength" is right (2.7 vs 1.4 pp).
- "52.7%" is a population descriptive rate; "51%" is the rate at equal strength (an intercept). The README does say so; fig. 1 is a good visual. But the fig.-1 right-hand column (51.0%, with form) is not mentioned in the headline text, which quotes 51.4% only (see above).
- The numbers are labelled "causal", but the toss choice is unobserved and the strength control imperfect. "Strength-adjusted" is the honest label; "causal" should be conditional ("assuming rank/form capture strength").
- Women's better-ranked share is 51.4% with CI [50.0, 52.8], i.e. barely distinguishable from a coin toss; the men's 54.4% drives the pooled 53%. Worth one sentence, because it implies the strength-selection explanation is mostly a men's result (the women's adjusted edge, 51.2%, is almost the same as the raw 51.8%).

### 4. Is the TennisMyLife SvGms "known data issue" well supported, or could it be match-pairing error? The error is real, but the README's cause analysis can be tightened, and I can rule out match-pairing.
The truth-vs-TML comparison (`results/svgms_*`, fig. 6B) is clear, and the argument that "scores agree in 99% of linked matches" already makes whole-match mispairing unlikely. I added a more direct test, comparing **TML serve points (`w_svpt`, `l_svpt`) with the pbp counts** for the same linked matches (counting a missing TML value as a mismatch, which understates agreement):
- 2016-23: TML `svpt` equals pbp serve points exactly in 97.2% of linked matches (98.9% within ±3 points), and the player labels are **never swapped** (0.0% of matches where the two totals are exactly interchanged).
- Within 2016-23, among matches where `SvGms` is *wrong* (36% of linked rows), `svpt` is still exact in 95.2% (points won: 95.0% exact), versus 98.4% where `SvGms` is correct.

So the stats rows belong to the right match and the right players; only the derived service-game column is wrong, which points to a column-specific derivation error in TML (a computation problem, for example tiebreaks counted as service games or inconsistent handling by Slam-year), not a pairing or winner/loser mix-up. The remaining ~5% of non-exact `svpt` in those rows could be missing pbp points. The paragraph "Possible cause: match-pairing error. We cannot rule that out" can be replaced with this evidence. Remaining caveats I would keep: I cannot see TML's computation, and the slight drop in `svpt` agreement where `SvGms` is wrong suggests some matches have partially wrong stats as well.

## Other findings

**Correctness / statistics (minor).**
- The match-clustered Wilson with design-effect is a reasonable approach; set 1 has one observation per match so it is exact. For sets 2+ the cluster adjustment is appropriate (sets within matches are correlated).
- "No Slam differs beyond noise" and the by-year appendix are stated without a test. With ~7 groups × 3 set groups, some CIs will miss the pooled value by chance. A single heterogeneity test (Slam × set-group interaction in the logit) would back up the sentence.
- The set 5 and deciding-set estimates mix several tiebreak/advantage formats; the README says the serve rule is unaffected, which is right, but the format could change the first-server advantage (an advantage set has no tiebreak). Not tested; only n = 942 anyway.
- Link failures concentrate in women's matches (3%) and those sets are dropped from the regressions. The raw and adjusted samples differ by about 190 sets; I checked that the raw estimate is the same on the linked sample (52.7%), so there is no visible bias.
- Unranked imputation affects only 0.24% of linked set-1 rows; dropping them changes the estimate by 0.1 pp.

**Validation of the earlier method.** The estimator comparison (A close to truth, B biased by ~+10 pp, B* corrected) is useful and the explanation of the set-1 gap as a population difference (not an estimator bias) is supported by the same-matches comparison. In fig. 6B the women's line starts only in 2014 (women's data are largely absent before) and the README's "about 98% agreement in 2011-15" is for men; in 2015 it is about 0.87 for women. Small wording fix.

**Reproducibility / practice.**
- Runs cleanly (`run_analysis.py`, ~1 min with cache, ~80 s without), deterministic (seed, byte-identical outputs on re-run), no absolute paths (repo root found from the script location), tests pass.
- Tests (9) cover set-score validity, first-server and tiebreak logic, missing-game handling, CIs, name matching and the SvGms rule. There is **no test for the strength-control code** (orientation of `d_logrank`/`prev` when player 2 serves first; the antisymmetric coding that makes the intercept meaningful) or for the link orientation (`p1_is_tml_winner`), which are the places where a silent sign error would bias the headline. A tiny synthetic test (swap players → covariates flip sign, intercept unchanged) would fix this. I verified orientation empirically (correct rank sign, 53% better-ranked share, `svpt` orientation matches), so this is an improvement, not a bug.
- `cache/points_clean.pkl` is a binary pickle in the analysis folder; fine, but note it should stay out of git (README says the cache key is file names and sizes: a content change with the same size would not invalidate it).

**Communication.** The README is long but well structured, and the plain-language "how the adjustment works" section is good. Figure 1 is clear. Figure 6 is dense for a non-expert (three different panels and the A/B/B* estimators are not explained in the figure itself). The conclusion is honest but should include the 0-2 pp range noted above.

## Verdict: **ACCEPT WITH MINOR CHANGES**

### Required
1. **Soften and unify the set-1 claim.** Report the strength-adjusted estimate as 51.0-51.4% (rank only vs rank + in-match form), say that with the form control the CI includes 50%, call it "strength-adjusted" rather than "causal" (or add "assuming rank and form capture strength"), and drop the "partly post-treatment" wording for the form control (or justify it). Mention that noisy rank makes the 51.4% an upper-biased estimate.
2. **Replace the "match-pairing error cannot be ruled out" paragraph** with the `svpt` evidence above (97% exact agreement, 0% swapped, 95% exact even where `SvGms` is wrong), which shows the fault is in the `SvGms` column.
3. **Add the model-free previous-set contrast** (prev winner wins 64.5% when receiving first vs 64.4% when serving first) next to the regression-based 50.3%.

### Optional
4. One sentence that the better-ranked-serves-first effect is mainly men's (54.4% vs women 51.4%, CI barely above 50%).
5. A heterogeneity test for the "no Slam differs" statement.
6. A unit test for covariate orientation and the link orientation.
7. Fix the "98% in 2011-15" wording for women (2015) and the women's start year in fig. 6B; explain A/B/B* inside fig. 6.
8. Include the cache key's content hash, or note that the pickle should not be committed.
