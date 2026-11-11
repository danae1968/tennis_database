# OPUS verification of SONNET's fixes: `analysis/match_length_trends/`

**Rerun.** `run_analysis.py` exits 0, and two consecutive runs give identical md5 for all CSVs **and** PNGs. 7 tests pass, including the new advantage-set tiebreak test.

| My required point | Status | Evidence |
|---|---|---|
| 1. `SetWinner` bug and Wimbledon tiebreak timeline | ✔ Fixed | Set winners now come from `P1GamesWon`/`P2GamesWon` with a legal-final-score check. `final_set_tiebreak_check.csv` now shows Wimbledon 12-12 tiebreaks in 2019 and 2021, and 7 / 10 / 11 deciding sets with a 6-6 tiebreak in 2022 / 2023 / 2024, exactly matching my reconstruction. The wrong "seen in data" marker is gone. The README's format table is correct. |
| 2. `is_tiebreak_game` for advantage sets | ✔ Fixed | A tiebreak now requires two servers in the game, and a test covers the advantage-set case. Tiebreak games went from 2,912 to 2,804. |
| 3. AO/FO 2018–21 wording | ✔ Fixed | The README states that these files have set and game numbers, servers and point winners, but no clock. The extension to count outcomes was declined, with a reasonable justification. |
| 4. Round composition; small-cluster SEs | ✔ Fixed / partly | Round fixed effects give men +2.5 s and women +1.8 s per decade, matching my check (+2.55 / +1.76). The README now uses CR1 variance with t(G−1) (a small-cluster correction). CR2 and the wild bootstrap were not run, which is acceptable at this effect size (p = 0.003). |
| 5. Figures | ✔ Fixed | 4 main figures plus appendix A1–A8. Okabe-Ito colours, men blue and women orange, line styles and markers that differ between series, event markers explained in a legend. No red/green. |

**Residual check on completeness (not blocking).** I compared SONNET's new completeness flag with my independent game-count reconstruction from `analysis/serve_first` (script: `scratch/verify_match_length.py`).
- **The systematic problem is gone.** All Wimbledon 2022–23 final-set-tiebreak matches are now kept.
- **About 9 matches disagree in each direction:**
  - Where the last row's `GamesWon` misses the set's final game, SONNET drops a complete match. Examples: `2015-wimbledon-1123` shows 5-3 instead of 6-3, and `2021-wimbledon-1150` shows 5-1 instead of 6-1.
  - Where points are missing mid-set but `GamesWon` carries the true score, SONNET correctly keeps matches that my rule would drop.
- These cases are scattered across years (about 9 of 6,500 matches) and are not concentrated in long matches, so they cannot bias the trends materially.
- **Optional:** call a match complete if *either* the `GamesWon` rule or a game-winner count gives a legal finished score.

**Numbers checked.**
- Men's seconds per point: +2.31 s per decade (+2.49 s with round fixed effects). My independent estimate was +2.39 / +2.55.
- Men's match minutes: +10.8 min per decade. This is plausible given that only about 8 net matches changed.

**Figures spot-checked:** fig 1, fig 4 (composition) and A4 (by Slam). No clipped or overlapping text, and the legends sit outside the data.
- Fig 4 is very wide and repeats its legend in each panel, but it is legible.
- A4 has heavily overlapping IQR bands; it is acceptable as an appendix figure.

## Verdict: **ACCEPT**

The optional improvement to the completeness rule above is not required.
