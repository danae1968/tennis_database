# Methods: can height alone predict who wins?

This is the technical companion to the [reader summary](README.md). It holds the cleaning steps, models, metrics, full tables, robustness checks and caveats.

**Question.** If you knew only the two players' heights, how often could you pick the winner of a tour-level match? And does height still help once you know their rankings?

**Answer in plain words.**

**Height alone picks the winner 54% of the time,** against 50% for a coin flip. Picking the better-ranked player instead gets 63–64% right (2023–26 test period).

| Tour | Height-only model | Taller player wins (when heights differ) | Ranking only |
|---|---|---|---|
| WTA | 53.6% | 53.9% | 63.0% |
| ATP | 54.3% | 54.9% | 64.0% |

The bigger the height gap, the bigger the edge: with a gap of 20 cm or more the taller player wins about 60–63%.

**Once rankings are known, height adds essentially nothing to the picks.**
- Accuracy: 63.0% → 63.0% (WTA) and 64.0% → 63.9% (ATP).
- The *probabilities* get very slightly better. For the ATP that gain is small but clear; for the WTA it is borderline, with the AUC gain's 95% CI reaching zero.

**Surface.** On the ATP, height matters most on grass and not at all on clay once ranking is known. The difference between surfaces is clear (p < 0.001). On the WTA, height's effect is about the same on every surface (p = 0.61).

**The serve link is an association, not a proven mechanism.**
- Taller players served better in the previous season, and that serve record accounts for about half of height's effect given ranking:

| Tour | Share of height's effect accounted for by the previous season's serve record | 95% CI |
|---|---|---|
| WTA | 48% | 31–73% |
| ATP | 69% | 43–97% |

- **Placebo check:** the previous season's *return* record does the opposite. It makes height's effect *larger*, because taller players tend to return worse.
- **Both together:** holding both serve and return records fixed, most of height's effect remains (only 30% and 8% accounted for).
- So taller players' edge goes hand in hand with a better serve, but their weaker return offsets part of it, and these data cannot separate cause from correlation.

![Taller player wins](figures/fig1_taller_player_wins.png)

*Share of matches won by the taller player, by height difference, 2016–2026 completed tour-level matches. The line is a logistic model on height difference alone, drawn over the range of the data; the thin lines are 95% CIs (typically ±1–4 points).*

## Data

- **Source:** TennisMyLife `YYYY_wta.csv` (WTA) and `tml-data/YYYY.csv` (ATP), 2016–2026 tour-level main draws ([TennisMyLife](https://stats.tennismylife.org), © TennisMyLife; the WTA part follows Sackmann's `tennis_wta`, CC BY-NC-SA 4.0). It provides heights (`winner_ht`, `loser_ht`), pre-tournament ranks and serve statistics.
- **Cleaning** (`results/cleaning.csv`):

| Step | Matches |
|---|---|
| Match rows | 58,908 |
| Team events (Davis Cup, Billie Jean King Cup) removed | −4,447 |
| Retirements, walkovers and unparseable scores removed | −2,108 |
| **Completed matches** | **52,353** |
| With both heights | 46,981 |
| With both heights and both ranks (used for all models) | 46,854 |

- **Height coverage** (report first):
  - **ATP:** 99.8% of matches have both heights.
  - **WTA:** 78.9% overall, and falling: about 94% in 2016–18, 75% in 2022, 54% in 2024 and 40% in 2026, though 92% in 2025 (figure A1).
- **Handling missing heights:**
  - Missing heights are not imputed; the models use complete cases only.
  - Heights outside 150–215 cm are treated as missing; four WTA values were impossible, for example a date entered as a height.
  - The WTA matches *without* heights involve lower-ranked players: the median better-ranked player is No. 49, against No. 26 when heights are known.
  - On those matches, ranking alone predicts better: 65.2% vs 63.0% (`results/missing_heights_check.csv`).
- **Sensitivity on high-coverage WTA data** (`results/wta_high_coverage_sensitivity.csv`): testing only on 2025, when 92% of WTA heights are known, gives the same picture. Height alone scores 53.7%, ranking 61.1%, and ranking + height 62.0%.
- **2026 is a partial season** (data to early November). It is part of the 2023–26 test period.

## How to run

```bash
make height_predicts_winner     # or: .venv/bin/python analyses/height_predicts_winner/run.py   (~1 min)
.venv/bin/python -m pytest tests/height_predicts_winner
```

- The code is in `data.py` (match table, random order, previous-season serve and return rates), `model.py` (logistic fits, metrics, paired bootstrap), `rank.py` (player-level height and ranking), `plots.py` and `run.py`.
- Shared helpers come from `tennis.scores`, `tennis.stats` (`auc`, `log_loss`, `wilson_ci`), `tennis.load` and `tennis.plotting`.
- The fixed seed is `SEED = 20261111`, and the output is deterministic.

## Method

1. **One row per match, players in random order.** For each match a seeded coin decides which player is "player 1".
   - The label is "player 1 won", which is 1 in 49.99% of rows.
   - Without this step, the winner/loser columns would leak the answer.
2. **Predictors.** All of them flip sign when the two players are swapped:
   - `ht_diff` = height of player 1 − height of player 2 (cm);
   - `log_rank_ratio` = ln(rank of player 2) − ln(rank of player 1).
3. **Models.** Logistic regressions **without an intercept**: by symmetry, two equal players have a 50% chance each. Fitted on **2016–2022** and tested on **2023–2026**, on the same complete-case rows for every model:
   - (i) coin flip;
   - height only;
   - (ii) ranking only;
   - (iii) ranking + height.
4. **Metrics on the test period:**
   - accuracy, with a prediction of exactly 50% counted as half right;
   - AUC;
   - log-loss, where a coin flip scores ln 2 = 0.693.
5. **Height's added value.** Two checks:
   - a Wald test of the height coefficient on the training data, with standard errors clustered by tournament;
   - a paired bootstrap over test matches (1,000 replicates) of the gain of (iii) over (ii).

   The bootstrap resamples matches, and matches of the same player are correlated, so its CIs are somewhat optimistic.
6. **By surface:**
   - the taller player's win rate, with Wilson CIs;
   - the odds ratio per 10 cm, from height alone and given ranking;
   - a joint Wald test of height × surface given ranking.
7. **Association with the serve.**
   - Each player's ace rate, serve points won and return points won from the **previous calendar year** are added. This needs at least 300 serve and 300 return points, so these are **established players**: 14,453 WTA and 19,742 ATP matches.
   - The analysis reports how much the height coefficient shrinks, with a CI from 200 bootstrap replicates that resample tournaments.
   - The return record serves as a placebo.

## Results

### Model comparison (test period 2023–26)

| Tour | Model | Accuracy | AUC | Log-loss | n test |
|---|---|---|---|---|---|
| **WTA** | Coin flip | 50.0% | 0.500 | 0.693 | 6,094 |
| | Height only | 53.6% | 0.553 | 0.689 | |
| | Ranking only | 63.0% | 0.690 | 0.633 | |
| | Ranking + height | 63.0% | 0.692 | 0.632 | |
| **ATP** | Coin flip | 50.0% | 0.500 | 0.693 | 10,391 |
| | Height only | 54.3% | 0.561 | 0.688 | |
| | Ranking only | 64.0% | 0.698 | 0.629 | |
| | Ranking + height | 63.9% | 0.700 | 0.628 | |

**What height adds to ranking** (`results/height_added_value.csv`):

| Tour | Height OR per 10 cm, given ranking | Log-loss gain (95% CI) | AUC gain (95% CI) | Accuracy gain (95% CI) |
|---|---|---|---|---|
| WTA | 1.11 (1.07–1.16) | 0.0012 (0.0001 to 0.0022) | 0.0018 (0.0000 to 0.0035) | −0.0 points (−0.5 to +0.5) |
| ATP | 1.09 (1.05–1.12) | 0.0010 (0.0003 to 0.0017) | 0.0017 (0.0006 to 0.0027) | −0.1 points (−0.4 to +0.2) |

- **WTA:** a borderline gain in probability quality.
- **ATP:** a small but clear gain.
- **Both:** no gain in correct picks.

![Model comparison](figures/fig2_model_comparison.png)

*Share of 2023–26 matches whose winner each model predicted correctly (models fitted on 2016–22).*

### By surface (all years, `results/by_surface.csv`, `height_by_surface_interaction.csv`)

| Tour | Surface | Taller player wins | OR per 10 cm (height alone) | OR per 10 cm (given ranking) |
|---|---|---|---|---|
| WTA | Hard | 53.7% (52.8–54.6) | 1.22 | 1.13 (1.08–1.18) |
| | Clay | 53.0% (51.6–54.5) | 1.16 | 1.09 (1.01–1.17) |
| | Grass | 53.8% (51.7–55.8) | 1.25 | 1.16 (1.04–1.30) |
| ATP | Hard | 54.9% (54.1–55.8) | 1.24 | 1.12 (1.08–1.16) |
| | Clay | 52.4% (51.3–53.6) | 1.10 | 1.00 (0.95–1.05) |
| | Grass | 56.4% (54.5–58.2) | 1.34 | 1.24 (1.15–1.33) |

Do the surfaces differ (height × surface, given ranking)?
- **WTA:** no, p = 0.61.
- **ATP:** yes, p < 0.001.

![By surface](figures/fig3_by_surface.png)

*Share of matches won by the taller player, by surface, 2016–2026; thin lines are 95% CIs.*

### Association with the serve (established players, `results/mechanism_serve.csv`)

Odds ratio per 10 cm, given ranking, on the same rows:

| Tour | Ranking + height | + previous-season ace rate | + serve points won | + return points won (placebo) | + serve and return points won |
|---|---|---|---|---|---|
| WTA | 1.14 | 1.06 (60% accounted, CI 38–89%) | 1.07 (48%, CI 31–73%) | **1.17 (−15%, CI −26 to −7%)** | 1.10 (30%) |
| ATP | 1.10 | 1.09 (7%, CI −27 to 42%) | 1.03 (69%, CI 43–97%) | **1.17 (−66%, CI −110 to −40%)** | 1.09 (8%) |

**Reading.**
- A better serve record goes with a smaller height effect, and a better *return* record with a larger one. That is the pattern expected if height helps on serve and hurts slightly on return.
- With both records held fixed, most of the height effect remains.
- Previous-season statistics are noisy proxies, and they also partly measure overall strength. So these numbers describe associations, not a mechanism.

## Does height predict ranking? (player level)

This section answers a different question from the match-level models above: are taller players ranked higher? Code is in `rank.py`. Output files are `results/height_rank_correlation.csv`, `height_reach_top_by_band.csv`, `height_rank_threshold_sensitivity.csv`, `height_effect_absorbed_by_ranking.csv` and `player_height_rank.csv`, and the figure is `figures/fig4_height_reaches_top20.png`.

**Players.** One row per player and tour from all non-team tour-level matches in 2016–26 (TennisMyLife), including retirements, because rankings are recorded before the match. A player is kept if they have a valid height (150–215 cm; the median of recorded values) and at least 20 matches with a recorded rank. That leaves 325 women and 342 men. Among women with 20 or more ranked matches, 325 of 335 (97%) have a height; every one of the 342 men does.

**Ranking summaries.**
- **Median rank** across the player's ranked matches is the primary measure for the correlation. It is robust to one lucky week and does not depend on career length the way "best rank" does.
- **Best rank** reached is the primary measure for "reached the top 100 / 20 / 10", because that is how those groups are defined.
- Both are reported for the correlation as a check.

**Correlation.** Spearman correlation of height with ranking quality (minus the rank number, so positive means taller players are ranked better). The 95% CI comes from a bootstrap over players (1,000 resamples, fixed seed).

| Tour | Ranking summary | Spearman rho (95% CI) | Players |
|---|---|---|---|
| WTA | Median rank | 0.22 (0.11 to 0.31) | 325 |
| WTA | Best rank | 0.23 (0.11 to 0.33) | 325 |
| ATP | Median rank | 0.25 (0.14 to 0.35) | 342 |
| ATP | Best rank | 0.28 (0.17 to 0.38) | 342 |

**Sensitivity of the correlation to the minimum number of ranked matches** (`results/height_rank_threshold_sensitivity.csv`; Spearman rho with median rank, bootstrap 95% CI; players need a recorded height):

| Tour | Min. ranked matches | Players | Spearman rho (95% CI) | Share reaching top 100 |
|---|---|---|---|---|
| WTA | 1 | 510 | 0.16 (0.06 to 0.24) | 60% |
| WTA | 5 | 430 | 0.16 (0.07 to 0.25) | 70% |
| WTA | 10 | 383 | 0.19 (0.09 to 0.29) | 79% |
| WTA | **20 (used)** | 325 | 0.22 (0.11 to 0.31) | 90% |
| WTA | 40 | 269 | 0.19 (0.06 to 0.29) | 97% |
| ATP | 1 | 767 | 0.12 (0.05 to 0.19) | 43% |
| ATP | 5 | 502 | 0.13 (0.03 to 0.21) | 66% |
| ATP | 10 | 429 | 0.14 (0.05 to 0.24) | 77% |
| ATP | **20 (used)** | 342 | 0.25 (0.14 to 0.35) | 93% |
| ATP | 40 | 280 | 0.28 (0.16 to 0.38) | 98% |

**Share reaching the top 100, 20 and 10 by height band** (the top 20 is plotted in figure 4; the top 100 is near its ceiling). Bands are 5 cm wide, with any band holding fewer than 30 players merged into its smaller neighbour. 95% Wilson intervals (players are treated as independent).

| Tour | Band (cm) | Players | Top 100 | Top 20 | Top 10 |
|---|---|---|---|---|---|
| WTA | 155–169 | 77 | 83.1% (73.2–89.9) | 18.2% (11.2–28.2) | 9.1% (4.5–17.6) |
| WTA | 170–174 | 101 | 86.1% (78.1–91.6) | 21.8% (14.8–30.8) | 13.9% (8.4–21.9) |
| WTA | 175–179 | 83 | 94.0% (86.7–97.4) | 33.7% (24.5–44.4) | 21.7% (14.2–31.7) |
| WTA | 180–189 | 64 | 98.4% (91.7–99.7) | 35.9% (25.3–48.2) | 28.1% (18.6–40.1) |
| ATP | 170–179 | 42 | 92.9% (81.0–97.5) | 11.9% (5.2–25.0) | 9.5% (3.8–22.1) |
| ATP | 180–184 | 98 | 90.8% (83.5–95.1) | 16.3% (10.3–24.9) | 8.2% (4.2–15.3) |
| ATP | 185–189 | 104 | 93.3% (86.8–96.7) | 26.9% (19.3–36.2) | 13.5% (8.2–21.3) |
| ATP | 190–194 | 62 | 91.9% (82.5–96.5) | 19.4% (11.4–30.9) | 16.1% (9.0–27.2) |
| ATP | 195–214 | 36 | 100% (90.4–100) | 58.3% (42.2–72.9) | 36.1% (22.5–52.4) |

**Very tall men.** Within the 195–214 cm band, the 26 men of 195–199 cm have 62% in the top 20 (and 42% in the top 10), the 7 men of 200–204 cm have 29% (14%) and the 3 men of 205 cm or more have 3 of 3 in the top 20 (1 of 3 in the top 10). With ten players above 200 cm, a peak followed by a decline cannot be confirmed or ruled out.

**How much of height's effect on winning does ranking absorb?** On the matches used in the models (all years 2016–26, complete cases), the no-intercept logit of the winner on height difference alone is compared with the same model including the log rank ratio. The share absorbed is 1 − (log OR per cm given ranking) / (log OR per cm alone). The 95% CI comes from a bootstrap that resamples tournaments (200 replicates, fixed seed).

| Tour | Height OR per 10 cm, alone | Given ranking | Share absorbed by ranking (95% CI) | Matches |
|---|---|---|---|---|
| WTA | 1.20 | 1.12 | 39% (31–50%) | 19,867 |
| ATP | 1.21 | 1.09 | 53% (43–60%) | 26,987 |

Logit coefficients are non-collapsible: adding a strong predictor such as ranking can change the height coefficient even if the two are unrelated, so the log-odds share is a conservative summary. On the probability scale (a linear probability model without intercept, same matches, same bootstrap) the shares are 43% (95% CI 36–52%) for women and 57% (49–63%) for men (outcome centred at 0.5 so that the model has the same symmetry as the no-intercept logit); both versions are in `results/height_effect_absorbed_by_ranking.csv`. A fair plain summary is "about 40% for women and about half or a little more for men". The bootstrap resamples tournaments, but the same players appear in many tournaments, so these intervals are somewhat narrow, as for the other match-level intervals in this analysis.

This is an association. It is consistent with height working partly through ranking, but it does not show how, and it does not separate height from other traits that go with it.

**Selection and other limits.**
- **Restricted range and the 20-match rule.** Everyone here has already reached tour level with at least 20 ranked matches, so players whose height kept them off the tour are missing. In general, selecting on the outcome weakens correlations, so the association could be larger among all aspiring players, but these data cannot show that. Within the data, loosening the match threshold lowers the correlation rather than raising it, probably because ranks based on a few matches are noisy (table below). The correlation of about 0.2 therefore depends on the 20-match rule.
- **Near-ceiling top-100 shares.** Because of the same selection, most players reached the top 100 (about 90% of women and 93% of men at the 20-match threshold), so the top-100 shares barely vary with height for men. The figure therefore uses the top 20, which has room to move on both tours. The top-100 table is kept above for completeness.
- **Missing heights.** Women's heights are missing for 10 of 335 eligible players (3%), but missing more often in recent seasons at match level (see the coverage figure), so players who debuted recently are somewhat more likely to be left out.
- **Rank is a snapshot over 2016–26,** so players are compared across different parts of their careers, and the 20-match minimum favours players with longer tour careers.
- **No multiplicity correction** is applied to the band results; they are descriptive.
- 
## Caveats

- **Rankings already contain height's effect.** "Height adds little given ranking" does not mean height is unimportant; its effect is already priced into the ranking.
- **WTA heights are missing non-randomly** in recent years, and the WTA test sample leans to higher-ranked players. The 2025-only check (92% coverage) agrees.
- **Heights are self-reported profile values,** often rounded. Measurement error biases the height effect towards zero.
- **Equal heights** (7% of WTA and 11% of ATP test matches) give the height-only model no information; it predicts 50%.
- **Many estimates are reported** (surfaces, mechanism variants). Treat individual p-values of about 0.01–0.05 with care.

## Conclusion

Height alone predicts the winner about 54% of the time, against 50% for a coin flip and 63–64% for simply picking the better-ranked player. The taller player's edge grows with the height gap. On the ATP it is largest on grass and absent on clay once ranking is known. It goes hand in hand with a better serve (and a slightly weaker return). Adding height to ranking does not improve the picks.

## Appendix

![Height coverage](figures/figA1_height_coverage.png)

*Figure A1. Share of completed matches with both players' heights recorded.*

## Review record

This analysis was independently cross-reviewed by a second agent, and the fixes were verified.
