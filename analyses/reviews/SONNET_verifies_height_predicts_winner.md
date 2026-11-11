# SONNET verifies the fixes to `analyses/height_predicts_winner/`

Read `OPUS_response_height_predicts_winner.md`, re-ran `make height_predicts_winner` and the tests (second run **byte-identical**; repo tests 86 passed), re-derived the key numbers with my own code, and opened fig1.

## My required points

| # | Point | Verdict | Evidence |
|---|---|---|---|
| R1 | Soften "statistically reliable" for the WTA | **Verified** | README: WTA gain "borderline, AUC CI reaches zero"; ATP "small but clear" in log-loss/AUC; "no gain in correct picks" (63.0% → 63.0%, 64.0% → 63.9%); the bootstrap-optimism remark is there. |
| R2 | Say the serve link is an association; CI on the share explained; return-skill placebo | **Verified** | Using my own previous-season serve/return records I get odds ratios (per 10 cm, given ranking) of WTA 1.143 → 1.072 with serve, 1.165 with the return placebo, 1.098 with both; ATP 1.101 → 1.030, 1.173, 1.092. These give shares of 48% / -15% / 30% (WTA) and 69% / -66% / 8% (ATP), identical to their table. Bootstrap CIs by tournament are added (WTA serve 48% (31-73%), ATP 69% (43-97%)). Their new finding is right and important: with serve and return records both held fixed most of the height effect remains (ATP 92%). The README no longer says "works through the serve"; it says height goes with a better serve and weaker return and that cause cannot be separated. The sample is labelled "established players" (14,453 WTA, 19,742 ATP matches, matching my 14,453 / 19,742). |

Optional points verified: no-intercept models (height-only 53.6% / 54.3%; ranking-only now equals the better-ranked rule, 63.0% / 64.0%, as it should); height x surface Wald test (`height_by_surface_interaction.csv`: WTA p = 0.61, ATP chi-square 24.8 on 2 df, p < 0.001) with the surface claim restricted to the ATP; high-coverage WTA check on 2025 (92% heights); ranking benchmark beside the 54% headline; fig1 lines now end at the data range (checked: WTA line ends at 22 cm, ATP at 28 cm).

## Remaining small points (optional)
- The WTA 2025-only sensitivity test is a single year (about 2,000 matches): its gain (62.0% vs 61.1%) is a point estimate; add its CI or say "consistent in direction".
- ATP fig1: the line extends past the last binned point (23 cm) to 28 cm, which is still within the data range (99th percentile of gaps) but leaves a visible gap; fine.

## Reader rules
WTA first, takeaway titles, direct "coin flip" label, faint CIs, no clipping, appendix split (figures 1-3 main, A1 coverage): all met in the figure I opened.

## Verdict: ACCEPT
