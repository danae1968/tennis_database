# P(win set | serves first game of the set) - SONNET

Data: tml-data/1991-2026.csv main tour (also 1990, serve stats sparse), completed standard matches with SvGms: 100,035 -> 97,662 used (rank available). Script: `analysis.py`, raw numbers: `results.json`.

## Serve-order inference
* Serve alternates every game; a tiebreak counts as ONE game for alternation (next set is started by the player who did not start the tiebreak).
* Validation: in `w_SvGms`/`l_SvGms` the tiebreak is **not counted** (for 1/2/3 tiebreaks S - (a+b with tb set=13) = -1/-2/-3 in ~98% of matches). With that rule, one of the two "who served first" hypotheses reproduces both observed SvGms exactly in 98.2% of matches (98.5% in tiebreak matches), so the rule is right.
* First server uniquely identified only in 46,527 matches (47%; roughly odd game totals, and some even ones with tiebreaks). In 52% both hypotheses fit (no information).
* **Selection trap:** identifiability depends on the score parity, which depends on the set outcomes. Naive analysis of identified matches is badly biased: set 1 first server "wins" 61.3% (n=46,527, CI 60.9-61.8), match first server wins the match 63.6%. A simulation (Markov hold model, truth 50.0%) reproduces this bias (naive 60.6-60.9%), so it is purely an artefact.
* **Fix:** missingness of the first server is a function of the observed score sequence (MAR). I fit a latent-variable EM: players labelled A (better ranked)/B, 5 rank-gap bins x best_of x set index x (who serves first) -> categorical distribution of set score; first server F in {A,B} has prior 1/2 (coin toss), known when identified, posterior (from set-score likelihood) when not. Estimates use all 97,662 matches. Bootstrap CIs (30 reps, matches resampled) reflect sampling only, not model misspecification. On simulated data the estimator recovers set-1 truth (50.2% vs EM 50.0%) and is ~1 pt low for later sets (model ignores within-match correlation).

## Results (EM estimator)
| Subset | P(win set / served first) | 95% CI | n sets |
|---|---|---|---|
| Set 1 (coin toss, cleanest) | **0.506** | 0.503-0.510 | 97,662 |
| Sets 2+ | 0.444 | 0.441-0.447 | 154,053 |
| All sets pooled | 0.468 | 0.466-0.471 | 251,715 |
| set 2 / 3 / 4 / 5 | 0.428 / 0.473 / 0.462 / 0.492 | | 97,662 / 45,057 / 8,228 / 3,106 |
| Set 1 Hard / Clay / Grass / Carpet | 0.510 / 0.501 / 0.517 / 0.503 | | 50,480 / 31,703 / 9,820 / 5,614 matches |
| Sets 2+ Hard/Clay/Grass/Carpet | 0.441 / 0.453 / 0.439 / 0.441 | | |
| Set 1 bo3 / bo5 | 0.502 / 0.527 | | 81,356 / 16,306 |

Naive (biased) identified-only values: set 1 0.613, sets 2+ 0.502, overall 0.544 - do not use.

## Markov model
Point-level model (equal players, serve-point win 0.60-0.66, avg 0.627 -> hold 0.789): P(first server wins set) = **0.500** (essentially exact; the first-game advantage cancels with the last-game/tiebreak disadvantage). Simulation with random strength differences: set 1 0.502, sets 2+ ~0.487, all ~0.493. For unequal players (+/-2 pts serve-point prob) stronger-serves-first 0.63, weaker 0.37 - i.e. strength dominates; serve order is nearly irrelevant for set 1.

## Interpretation
* Set 1: first server wins ~50.6% (empirical), vs 50.0% Markov; a ~0.5 pt advantage, significant but tiny. Surfaces differ by <1.5 pts.
* Sets 2+: below 50% is a **selection effect**, not a serve-order effect: who serves first in set k is determined by parity of games so far, which correlates with who has been winning (set 2 first server is more often the set-1 loser). The Markov/simulation with heterogeneity reproduces the direction (0.487) but real heterogeneity/momentum is larger (0.444). A strength-controlled logistic on log rank ratio (naive sample, biased) was not trusted.

## Caveats
Model-based debiasing assumes set scores independent given rank-gap bin and role; strength within a bin and within-match form are unmodelled, so later-set numbers lean on the model. bo5 set-1 0.527 is higher than bo3 and not understood (possibly model misspecification; deciding-set/no-tiebreak rules at some events). Excluded: RET/W/O/DEF, super-tiebreak, non-standard set scores, missing ranks. ATP main tour only; no WTA. Pre-1991 has no serve stats.
