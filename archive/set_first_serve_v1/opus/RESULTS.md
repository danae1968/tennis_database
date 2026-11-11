# P(win set | served the first game of the set): ATP main tour, 1991–2026 (OPUS)

Files: `analysis.py` (runs in about 20 s with `python3 -P analysis.py`), `results_table.csv` (all breakdowns, estimators A/B/C),
`selection_corrected.csv`, `results.json` (validation numbers), `run_log.txt`.

## Headline
| Sets | Estimate | 95% CI (match-clustered) | n sets / matches |
|---|---|---|---|
| **All sets pooled** | **0.481** | 0.480–0.483 | 253,125 / 98,243 |
| **Set 1** (serve order set by coin toss) | **0.508** | 0.506–0.511 | 98,243 |
| Sets 2+ | 0.465 | 0.463–0.467 | 154,882 |

The estimator here is the posterior estimate (A), described below. A selection-corrected check (B*) agrees closely: all sets 0.478 [0.475, 0.481], set 1 0.505 [0.500, 0.510], sets 2+ 0.462.

**Interpretation.** Serving first in a set gives essentially no advantage. In set 1, where the coin toss decides who serves, the first server wins 50.5–51% of sets. Pooled over all sets the figure is *below* 50% (about 48%). That is a strength and selection effect, not a serving penalty. The first server of set k+1 is fixed by the parity of set k's game count. Odd-length sets such as 6-3 and 6-1 are won disproportionately by their first server, so the *loser* of the set more often serves first in the next one. In later sets, then, the first server is more often the weaker player. The iid Markov null with the same players' serve-point rates predicts 0.473 for all sets (0.443 for set 2). The observed values are about 0.5–1 pp above that.

## Method
1. **Data.** `tml-data/YYYY.csv` (201,085 matches). I kept completed matches only: no RET/W/O/DEF/ABD, no match-tiebreak or Fast4 sets, and every set had to be a valid final score (194,686). Serve stats were also required, which in practice means 1991+ (100,008 matches).
2. **Serve-order rules.** Serve alternates every game, across set boundaries. A tiebreak counts as one game for alternation: the player who received first in the tiebreak serves first in the next set. So set k+1's first server switches iff set k had an odd number of games (7-6 = 13 games).
3. **How SvGms counts tiebreaks (validated).** `w_SvGms + l_SvGms` equals the number of *regular* games (tiebreaks excluded) in 98.4% of matches, and in 97.1% of matches that contain a tiebreak. Counting tiebreaks as service games matches only 1.8%. So SvGms **excludes** tiebreaks.
4. **Identification.** For each hypothesis (the winner served first, or the loser did), compute each player's implied regular service games and compare them with (w_SvGms, l_SvGms).
   - Exactly one hypothesis fits in 46,526 matches.
   - Both fit (the counts are tied) in 51,717 matches.
   - Neither fits in 1,765 matches. These are data errors and were dropped.
5. **Breaks as extra information.** Breaks made by each player = opponent's bpFaced − bpSaved. Given the serve order, the net breaks in each set are fixed by the score, so the total break counts can rule out a hypothesis.
   - Validation on SvGms-identified matches: the true hypothesis is break-feasible 99.86% of the time, and the false one is ruled out 26.8% of the time.
   - Estimator C adds the 1,519 tied matches that the breaks resolve.
6. **Posterior (estimator A, uses all 98,243 matches).** P(order | set scores, break total) comes from an iid game-level Markov model. Hold probabilities are derived from each player's in-match serve-point win rate, which does not depend on serve order. The prior is 50/50 (coin toss), and SvGms-identified matches get a posterior of 0 or 1.
   - Validation: on identified matches, with the SvGms information hidden, the posterior has Brier 0.119 and is 83% accurate.
   - It is somewhat *under*-confident (for example, predicted 0.75 vs observed 0.81) but has no directional bias.
7. **Selection correction (B\*).** Restricting to SvGms-identified matches (unequal service-game counts) is strongly biased. Identification depends on score parity, which correlates with the first server winning. For set 1 the naive identified-only estimate is **0.613**, but the iid null simulation under the *same* selection gives **0.608**.
   - The null was simulated four times per match, with a random first server, point-level tiebreaks and each match's serve-point rates.
   - B\* = observed_identified − null_identified + null_all.
8. **Markov prediction.** Under the iid model, the probability of winning a set does not depend on who serves first. My DP confirms this (max |difference| = 2e-16 over a grid of serve-point rates). The model therefore predicts 0.500 for set 1 and, with selection, 0.473 for all sets pooled.

## Breakdowns (estimator A; "Markov" = model expectation given both players' serve-point rates)
| Subset | P(first server wins) | 95% CI | Markov | n sets |
|---|---|---|---|---|
| Set 1 | 0.508 | .506–.511 | 0.507 | 98,243 |
| Set 2 | 0.456 | .454–.459 | 0.434 | 98,243 |
| Set 3 | 0.479 | .475–.483 | 0.479 | 45,262 |
| Set 4 | 0.475 | .465–.484 | 0.481 | 8,260 |
| Set 5 | 0.502 | .487–.518 | 0.500 | 3,117 |
| Deciding set | 0.497 | .493–.502 | 0.502 | 31,986 |
| Hard (all / set 1) | 0.481 / 0.510 | | 0.473 / 0.510 | 130,481 / 50,787 |
| Clay | 0.484 / 0.504 | | 0.474 / 0.501 | 80,607 / 31,853 |
| Grass | 0.478 / 0.517 | | 0.468 / 0.513 | 28,350 / 9,879 |
| Carpet | 0.480 / 0.502 | | 0.470 / 0.504 | 13,454 / 5,654 |
| Best of 3 / Best of 5 | 0.483 / 0.477 | | 0.474 / 0.469 | |
| Tiebreak sets / other sets | 0.491 / 0.480 | | 0.479 / 0.471 | |

The results are stable by decade: all-sets values are 0.480–0.484 in each of 1991–99, 2000–09, 2010–19 and 2020–26.

## Strength-adjusted excess over the iid model
- Set 1: +0.1 pp (posterior). The selection-corrected B\* gives +0.5 pp [−0.03, +1.0].
- All sets: +0.5 pp [+0.2, +0.8] (B\*), or +0.9 pp (A).
- Set 2: about +1.4–2.2 pp. This plausibly reflects the iid model, not serving first: the model does not capture loser-of-previous-set rebound or momentum.

## Caveats
- Serve order is inferred, not observed. In tied matches the posterior depends on the model. The model is under-confident, which would attenuate any real first-server effect slightly toward the model's prediction. The model-free B\* gives very similar numbers.
- Hold probabilities come from the same match (they are endogenous). They are adequate as a strength control, but they are not ex-ante strength.
- Coin-toss winners may choose to receive, and that choice could correlate with player type. I treat the set-1 serve order as random.
- Retired/walkover matches and pre-1991 matches (no serve stats) are excluded. Old advantage final sets are modelled with tiebreak rules in the baseline (minor).
- The null model uses tiebreaks at 6-6 for every set.
