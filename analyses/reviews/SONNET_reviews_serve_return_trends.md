# SONNET reviews `analyses/serve_return_trends/` (and the shared code it uses)

Scratch checks: `scratch/sonnet_review_checks1.py`, `checks2.py`, `checks4.py` (run with `PYTHONPATH=.`).

## Reproducibility
- `make serve_return_trends` runs cleanly in about 1 minute. I recorded the md5 of every file in `results/` and `figures/` before and after the run: **all identical**, so the output is deterministic.
- `pytest tests/serve_return_trends tests/shared`: 45 passed. The five analysis tests cover meaningful logic (break rate from score not SvGms, exclusions, partial year, pbp ace/winner flags for both providers, charting winners excluding aces).

## Correctness: items you asked me to check
1. **Break % from the score, not SvGms: confirmed.** With my own regex score parser (tiebreak = not a service game, completed matches, no Davis Cup), breaks / regular games is ATP 21.14% (2016) and 19.65% (2025), WTA 35.70% and 33.88%. The README reports 21.1 → 19.6 and 35.7 → 33.9.
2. **IBM includes aces in winners, Infosys excludes them: confirmed.** Share of ace points that are also flagged as winners, by Slam-year: 1.00 in every US Open and Wimbledon year, and in AO/RG 2016-17; **0.00** in AO/RG 2018-21. The charting claim (`winners >= aces + fh + bh winners`) holds in 100% of rows in every year 1960-2026. It is a valid test: if aces were excluded, that inequality would fail for any player with an ace.
3. **Charting-selection explanation of the men's +5 points/decade: right direction, wrong mechanism, and it can be made much sharper.** I recomputed non-Slam men's charted winners (excl. aces) per 100 points:
   - It is **not** a change in which tournaments get charted: the 96 tournaments charted both up to 2021 and from 2022 go from 24.7 to 28.8.
   - It is **not** a change in which charters are active: the 13 charters active in both periods go 24.6 → 28.6.
   - **One charter ("Ludo") drives it.** He charted 31% of post-2021 non-Slam men's matches, and his own rate is 32.3 → 40.9 winners per 100 points (the Slam-draw level is about 25). **Excluding him, the non-Slam rate is flat: 23.8 → 24.1.** Other large charters are flat (Zindaras 23.8 → 24.2, BG 25.4 → 25.4).
   - So the finding is "one prolific charter's coding", not "which matches". The README sentence ("a change in which matches are charted (more events, different charters and coding habits)") should say this; the charting trend SEs should cluster by charter, not tournament-year.
4. **Is the hard-court concentration of the break-% decline robust? Partly.** My WLS check (year slope, per decade, SE clustered by tournament-edition):
   - Hard: WTA -2.06 (SE 0.55), ATP -1.79 (SE 0.59); stable when 2020-21 are dropped.
   - Clay and grass: all CIs include 0 but are wide (SE about 0.7-1.0), so "no change" is not shown, only "not detected".
   - Hard minus clay slope difference: WTA -2.5 (p = 0.022), ATP -2.1 (p = 0.05). With about 50 trends reported, the claim "comes almost entirely from hard courts" is stronger than the evidence; "is concentrated on hard courts (the surface difference is only borderline)" is accurate.
   - **Tournament composition matters.** README says CIs are "clustered by tournament", but the cluster variable is `tourney_id` (e.g. `2016-0339`, an *edition*; 2,636 clusters, not 805 tournaments). Clustering by tournament: WTA overall -1.24 (-2.33, -0.15), ATP overall -0.99 (-1.69, -0.28); both still significant. With **tournament fixed effects** (within-tournament change): WTA hard -2.82 (-4.31, -1.33), ATP hard -1.26 (-2.33, -0.19) hold, but **ATP all-surfaces becomes -0.74 (-1.81, +0.32)**. So the ATP tour-wide headline ("breaks fell by about 1 point per decade") is sensitive to which events are on the calendar; the hard-court statement survives.

## Statistics
- Rates are pooled and the CIs are linearised ratio CIs, the right tool. Trends use WLS with clustered SEs and a t reference (`trend_per_decade`), reasonable.
- README caveat on about 50 trend estimates is honest. The "plain answer" nonetheless states the break decline as a result; add the clustering/FE sensitivity above.
- The plain answer says "none of the tour-wide ace trends is larger than ±0.3", while the table shows Challenger -0.32 (CI -0.60 to -0.05). Reword ("about ±0.3 or less").
- Charted-Slam vs all-Slam winner equality (26.4 vs 26.3, 24.8 vs 24.8) and the round reweighting are good evidence that charting selection is small at the Slams.

## Code review (shared code touched)
- `tennis.scores.parse_score`: set-score rules are tight and tested; retirements rejected. Fine.
- `tennis.stats.ratio_ci`: normal CI with k/(k-1) correction; with very few clusters (under about 10) the normal approximation is too narrow. Minor, mention in the docstring.
- `tennis.names.names_match`: the final clause (same first initial and same last token) can match two different players with the same initial and surname, but linking requires the same Slam, year, gender and *both* players and a unique hit, so the risk is negligible.

## The user's rules
- WTA first in every figure: yes (WTA, ATP, Challenger order). Okabe-Ito and marker/line variation: yes. No clipping seen in figures 1-6 and A1-A3 that I opened.
- Reader rules:
  - Titles state takeaways: yes. README leads with a plain-language answer: yes.
  - **fig4** title ("In charted men's matches outside the Slams, winners jump after 2021") reads as a real change; it is a coding artefact of one charter. Retitle (e.g. "Charted men's matches outside the Slams show a jump in winners that comes from one charter"), or drop the figure from the main text and show it only with the charter split.
  - **fig2**: three surfaces x three tours with overlapping shaded bands is busy, and the title says "breaks rarer on WTA and ATP" while only the hard-court line visibly falls. Fade the bands for the non-hard surfaces or title it "...mainly on hard courts".
  - fig5 bars start at 0 so a 1-point gap is invisible, which is the point, but the CI whiskers are tiny; fine.
  - "(partial)" under 2026 is a reader-relevant label, acceptable.

## Verdict: ACCEPT WITH MINOR CHANGES

Required:
1. Rewrite the charting-jump explanation to name the single-charter driver (24.7/28.8 same tournaments; 23.8 -> 24.1 without one charter) and cluster the charting trend by charter; retitle fig4.
2. Fix the "clustered by tournament" wording (clusters are tournament editions) and add the tournament-clustered / tournament-FE sensitivity; state that the ATP tour-wide break trend is not robust to tournament FE while the hard-court trend is.
3. Soften "almost entirely from hard courts" to "concentrated on hard courts (surface difference borderline, p about 0.02-0.05)".

Optional:
4. "±0.3" wording in the ace bullet. 5. Fade non-hard bands in fig2. 6. Docstring note on `ratio_ci` with few clusters.
