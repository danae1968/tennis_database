# SONNET reviews `analyses/height_predicts_winner/`

Scratch checks: `scratch/sonnet_review_checks3.py` (run with `PYTHONPATH=.`).

## Reproducibility
- `make height_predicts_winner` runs cleanly (50 s); the md5 of all `results/` and `figures/` files is **identical** before and after, so the output is deterministic. `pytest tests/height_predicts_winner`: 4 passed; the tests check the random player order (and that `ht1` is the winner's height exactly when player 1 won), the lag of previous-season rates, and metrics on known cases.

## Correctness
- **Headline numbers verified with my own code** (raw winner/loser columns, no randomisation, same completed-match and height rules, 2023-26): taller player wins **53.9% (WTA, n = 5,689)** and **54.9% (ATP, n = 9,244)** when heights differ; the better-ranked player wins **63.0% (WTA, n = 6,094)** and **64.0% (ATP, n = 10,391)** on the same complete-case rows (README ranking-only models: 62.8%, 64.0%). All match the README.
- **Leakage: none.** A seeded coin decides the player order, so `p1_won` is about 50/50; all predictors are antisymmetric; ranks are the pre-tournament ranks in the file; previous-season serve stats are lagged by a year (tested).
- **Train/test split by time (2016-22 vs 2023-26): correct.** Note the test set differs in composition on the WTA: median |log rank ratio| 0.97 vs 0.89 in training and equal-height matches 7.0% vs 5.3%, because of the heights missing in 2022-24. This is mentioned, not a bug.
- **Minor modelling point.** All predictors flip sign when players swap, so the logit should have *no intercept*, but one is fitted (0.019 on both tours). It makes the 50% threshold depend on a coin-flip artefact. Effect on height-only test accuracy: WTA 53.66% with vs 53.51% without, ATP 54.35% vs 54.32%. Negligible, but drop the intercept.
- **Missing heights (WTA 79% coverage, 40% in 2026).** Handled honestly: complete cases, a check showing the missing matches involve lower-ranked players (median rank 49 vs 26), and a statement that the test sample leans to high-profile matches. Suggested sensitivity (not required): repeat the WTA model on years with at least 90% coverage (2016-18, 2025) to show the headline does not rest on the missingness pattern. Also, the mechanism sample (previous season with at least 300 serve points) is only 14,562 of 46,854 WTA+ATP rows and excludes new players, so say it is an established-player sample.

## Statistics
- Logistic models with tournament-clustered SEs, a paired bootstrap for the gain over ranking-only, same rows for every model: **the accuracy / AUC / log-loss comparison is fair.**
- **"Statistically reliable but tiny" over-claims for the WTA.** The WTA AUC gain CI is 0.0000 to 0.0035, the accuracy gain CI (-0.2, +0.7) includes 0, and the log-loss CI starts at 0.0001. The bootstrap resamples matches, but matches of the same player are correlated, so these CIs are somewhat optimistic. For the ATP, log-loss and AUC are clearer. Suggest: "a small, borderline gain for the WTA, a small reliable gain for the ATP in log-loss/AUC; none in accuracy".
- **Surface claims.** "Height matters most on grass and least on clay (ATP)" is supported by the point estimates (OR per 10 cm given ranking 1.24 vs 1.00 (0.95-1.05)), but no interaction test is given and six cells are shown; the README does caveat this. Add a height x surface interaction test, or say "suggestive".
- **"Works through the serve" (mechanism) is supported descriptively, but is a mediation claim.** I ran a placebo: odds ratio per 10 cm given ranking, same data, adding previous-season serve vs return points won:

| Tour | ranking + height | + serve points won | + return points won (placebo) | both |
|---|---|---|---|---|
| WTA | 1.143 | 1.072 | **1.165** | 1.098 |
| ATP | 1.101 | **1.030** | **1.173** | 1.092 |

  Controlling for return skill *raises* the height effect (tall players return worse), while serve skill lowers it, so the shrinkage is not just "any quality proxy". That strengthens the claim. Still: (a) previous-season stats are noisy proxies, so the share explained is probably understated; (b) there is no CI on "60%" or "two thirds"; (c) causal wording ("works through") is stronger than the design. Suggest "is largely accounted for by a player's previous-season serve record", add a bootstrap CI for the percentage reduction, and add the return-skill placebo above (it takes a few lines).

## The user's rules
- WTA first everywhere (tables and figures): yes. Okabe-Ito colours, markers differ (squares WTA, circles ATP), faint CIs, "coin flip" labelled directly, no legends: good; no clipped text in the four figures I opened (fig1, fig3 inspected closely).
- Titles state takeaways ("The taller player wins more often, and more so the bigger the gap"); no internal notes such as "WTA left". Surface results: yes, by surface (Hard, Clay, Grass).
- README leads with the question and a plain-language answer with a small table: yes. One clarity point: put "picking the better-ranked player wins about 63-64%" next to the "54%" headline so a newcomer sees how small height's 54% is.
- Fig1: the fitted line is drawn to 30 cm although the data end at about 24 cm; shorten the line to the data range.

## Verdict: ACCEPT WITH MINOR CHANGES

Required:
1. Soften "statistically reliable" for the WTA (CI on AUC reaches 0; accuracy CI includes 0).
2. Reword "height works through the serve" as an association, with a CI on the share explained, and add the return-skill placebo (results above).

Optional:
3. Drop the intercept in the antisymmetric logits. 4. Height x surface interaction test. 5. WTA sensitivity on high-coverage years; label the mechanism sample as established players. 6. Put the 63-64% ranking benchmark next to the 54% headline; end the fig1 line at the data range.
