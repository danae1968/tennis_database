# OPUS review of `analysis/match_length_trends/` (SONNET)

**Scope.** I read the README and `src/pbp.py`, the final-set check in `run_analysis.py` and several figures. I re-ran the pipeline and the tests, and wrote independent checks in `analysis/reviews/scratch/check_match_length.py` (run from the repo root with `.venv/bin/python -I`). For the set-level ground truth I reused my own Slam point-by-point reconstruction from `analysis/serve_first/src`, which reads the same pbp files and rebuilds set scores from game winners. I did not edit the folder under review.

## 1. Correctness

### 1a. Set winners and completeness come from `SetWinner`, which is missing for many final-set tiebreaks (required fix)

**The bug.** `set_table` takes `winner = max(SetWinner)` per set, and `match_table` marks a match complete only if a player reaches 3 (men) or 2 (women) such sets.
- In Wimbledon 2022–23, the point that ends a 10-point final-set tiebreak carries `SetWinner = 0`, even though `P1GamesWon` shows 7-6. Example: `2022-wimbledon-1103`, set 5, point 322.
- The same happens for some 12-12 tiebreaks (Wimbledon 2021) and a few US Open 2022 matches.
- In long advantage sets (FO 2014–16), the files carry spurious `SetWinner` flags at 7-6 and 8-7. The rule `max()` then picks 2 whenever any row in the set is flagged 2, regardless of who won the set.

**Effect.** Comparing SONNET's rule against a reconstruction from game counts with a legal-final-score check:
- **28 complete matches are classed as "retired/unfinished"** and dropped from the 250 "incomplete" matches.

| Event | Wrongly dropped |
|---|---|
| Wimbledon 2022 | 7 |
| Wimbledon 2023 | 10 |
| Wimbledon 2021 | 2 |
| Wimbledon 2024 | 2 |
| US Open 2022 | 2 |
| Wimbledon 2015 | 1 |
| FO 2014–16 | 4 |

- These are the longest matches. The men's median at Wimbledon 2022–23 is **261 min** for the wrongly dropped matches, against 166 min for those kept.

**Consequence 1: the final-set tiebreak timeline in the README is a data-processing artefact, not "seen in data".** This is the brief's question about Wimbledon tiebreaks.
- `final_set_tiebreak_check.csv` shows 0 tiebreaks at Wimbledon 2022–23 and none at 12-12 in 2021, because those matches never reach the "complete" frame.
- Reconstructed from game winners, the pbp data contain:
  - a 13-12 deciding set in **2019** and in **2021**;
  - **7 (2022) and 10 (2023)** deciding sets ending 7-6;
  - 11 in 2024.
- This matches the known rules: a 12-12 tiebreak in 2019–21 and a 10-point tiebreak at 6-6 from 2022.
- The README sentence ("a 12-12 tiebreak in 2019, and a 6-6 tiebreak from 2024 … 2022-23 show none") and the "Wimbledon TB at 6-6 (seen in data)" marker at 2024 on every figure are wrong.

**Consequence 2: match and set durations in 2021–23 are biased down.** The size is small, though. In a comparable model (USO + Wimbledon, last-stamp minutes, Slam and sets-played fixed effects, edition-clustered), including the 28 matches moves the men's trend from +24.4 to +25.0 min per decade, and the women's from +12.4 to +12.9. My specification is cruder than SONNET's clean-clock one, so read this as the direction and order of magnitude only.

**Fix.** Derive set scores and winners from game counts (`P1GamesWon`/`P2GamesWon` at the last point, or counting game winners), with a legal-final-score check. Use `SetWinner` only as a cross-check.

### 1b. Tiebreak flag for games (required, small)

**The problem.** `is_tiebreak_game` flags any game *ending* at 7-6 or 13-12. In advantage final sets (AO/FO ≤2017, Wimbledon ≤2018), the regular game that takes the score to 7-6 is flagged as a tiebreak and excluded from points-per-game. The effect is small, but the existing test `test_tiebreak_flag` encodes the wrong rule.

**Suggested rule.** Use "both players served in the game, at a games score of 6-6 or 12-12".

### 1c. AO/FO 2018–21 dropped as having "no clock or game/set scores" (README wording; optional extension)

**What the files actually contain.**
- The clock is indeed empty: `ElapsedTime` is 0% non-null in 2019 AO and 2021 FO.
- The score information is not missing: `SetNo`, `GameNo` (numbered cumulatively across the match), `PointServer` and `PointWinner` are 100% populated. Only `SetWinner`, `GameWinner` and `GamesWon` are blank.

**Suggested changes.**
- Correct the wording.
- Optionally, add these about 2,000 matches to the count outcomes (points per game, set and match), rebuilding game winners from the last point's `PointWinner`. My serve_first pipeline does exactly this and passes a 99.96% serve-rotation consistency check on these files.

## 2. Robustness of "time per point rose" (specific question)

**Reproduced independently.** I took the per-match median within-game cycle time (gaps of 0–120 s, at least 30 gaps per match) for USO + Wimbledon, with Slam fixed effects and SEs clustered by tournament-edition:

| Gender | Change per decade | SONNET |
|---|---|---|
| Men | **+2.39 s** [1.09, 3.68] | +2.3 |
| Women | **+1.74 s** [0.51, 2.97] | +1.7 |

The yearly medians match too: men 28 → 31 s, women 31 → 33 s.

**Losing the AO/FO clock after 2017 is not a problem.** The core sample is USO + Wimbledon in every year, with Slam fixed effects, so the timing trend uses the same events throughout. The AO/FO 2014–17 levels (men 29–30 s) are also in line with the US Open (29.5 s).

**A composition change the README does not mention: coverage of early rounds.**
- In 2014–18, about 90–102 men's first-round matches per year at USO + Wimbledon have point data.
- From 2019 it is 127–128.
- Adding round fixed effects leaves the result intact: men **+2.55 s** [1.26, 3.84], women **+1.76 s** [0.53, 3.00].
- Restricting to rounds 3 and later, which had constant coverage, gives men +0.8 s [−1.7, 3.3]. That is consistent but underpowered (n=647).
- Please add the round-fixed-effects check to the caveats.

**Match minutes have a further confound.** The Wimbledon final-set format changed: advantage sets until 2018, capped afterwards. Over 2014–24 this mechanically shortens the longest men's matches. "Controlled for sets played" does not absorb it, so the +10.7 min per decade for men is, if anything, conservative. It deserves a sentence.

## 3. Statistics

**Few clusters.** There are about 20 edition clusters. Cluster-robust SEs with this few clusters are biased downward. Use t with G−1 df, CR2 (small-sample cluster correction) or a wild cluster bootstrap. The headline intervals will widen a little; the seconds-per-point and match-minute trends will very likely stay significant.

**What is sound:**
- Using per-match medians as the unit, and then trends across matches, is appropriate.
- The tour-level "seconds per point" (including changeovers) is clearly separated from the clock-based measure.

**Multiplicity.** About 8 outcomes × 2 genders plus 4 tour groups are tested. The README reads them as a coherent pattern ("points flat, time up") rather than cherry-picking, which is fine. A sentence noting the number of tests would help.

**Causal claims.** The conclusion correctly declines to attribute the rise to the 25-second serve clock or to COVID-19. Good.

## 4. Reproducibility and practice

- `run_analysis.py` runs cleanly (exit 0, 1 min 47 s). **All result CSVs are byte-identical on re-run.**
- **The PNG bytes differ between runs.** Contents look identical. Optional fix: pass `metadata={"Software": None}`, check for non-deterministic draw order, or note that only CSVs are byte-stable.
- The 6 tests pass. Most are meaningful (clock parsing, cycle cleaning, score parsing, slope recovery). `test_tiebreak_flag` should gain an advantage-set case (see 1b).
- There are no absolute paths.

## 5. Communication

**Too many figures.** There are 12, plus 2 that share the number "fig5", and two different "fig7"s.
- Keep fig 1 (seconds per point), fig 3 (game duration), fig 5 (minutes by format) and fig 9 (composition).
- Move the rest to an appendix.

**Fig 9 needs fixing:**
- The legends overlap the event annotations and data in panels 2 and 3.
- The annotations overlap each other.
- The "Sets per match" panel is dominated by the best-of-5 line, which flattens the best-of-3 series.
- It relies on red/green (WTA vs Challenger) to tell series apart.

**Fig 6:**
- The legend uses raw codes (`usopen`, `frenchopen`).
- The event labels collide with the shaded bands.

**Event markers.** Remove or correct "Wimbledon TB at 6-6 (seen in data)" (see 1a). The 2022 "final-set tiebreak rule changes begin" marker is right: the 10-point tiebreak at 6-6 was introduced at all four Slams in 2022.

**Colour.** Apply the user's figure guidelines:
- Okabe-Ito colours, men=#0072B2, women=#E69F00 (fig 1 currently uses red for women).
- Marker or line-style redundancy.
- `bbox_inches="tight"`.

**README.** Clear, with an honest coverage table and caveats. It needs the corrections above.

## Verdict: **ACCEPT WITH MINOR CHANGES**

The main conclusions hold. Points per game, set and match are flat, and time per point rose by about 2 s per decade at the Slams. I reproduced this independently, and it survives the AO/FO clock loss and the change in round coverage. But the README states a wrong factual finding (the Wimbledon tiebreak timeline), and the cause is a code bug that also drops the longest matches. Both need fixing before release.

**Required**
1. Derive set winners and match completeness from game counts with a legal-score check, not `max(SetWinner)`. Re-run. Then correct `final_set_tiebreak_check.csv`, the README tiebreak paragraph and the "seen in data" figure marker. The pbp data do show Wimbledon 12-12 tiebreaks in 2019 and 2021, and 6-6 tiebreaks from 2022.
2. Fix `is_tiebreak_game` for advantage sets, and add a test case.
3. Correct the README: AO/FO 2018–21 lack only the clock and the winner columns, not the game/set scores.
4. Add the round-composition check (round fixed effects) to the caveats, and use a small-cluster correction for the roughly 20-cluster SEs.
5. Figures: fix the overlaps in fig 9 and fig 6, apply the colour-blind palette guidelines, and reduce the main-text figures to about 4.

**Optional**
6. Use the AO/FO 2018–21 point data (about 2,000 matches) for the count outcomes.
7. Note the Wimbledon final-set format change as a confound for the men's match-minute trend.
8. Make the PNG output byte-deterministic.
