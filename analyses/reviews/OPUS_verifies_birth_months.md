# OPUS verification of SONNET's fixes: `analysis/birth_months/`

**Rerun.** `run_analysis.py` exits 0, and two consecutive runs give identical md5 for all CSVs **and** PNGs. 7 tests pass.

| My required point | Status | Evidence |
|---|---|---|
| R1. WTA 2018+ ID-coverage claim | ✔ Fixed | The README now gives measured coverage: 94% (2018), 89% (2020), 81% (2022), 71% (2024), 59% (2026), from the new `results/wta_id_coverage.csv`. This agrees with my review numbers (93.7 / 88.9 / 81.4 / 71.3%). |
| R2. Trend-test SE (scale < 1) | ✔ Fixed | Dispersion is now floored at 1. ATP+WTA played trend p = 1e-20 (was 1.8e-34). My review calculation gave 1.4e-21 with the Poisson SE on n=8,087; the new n is 8,073, so the two are consistent. |
| R3. Lead with "played"; flag WTA "all" heaping | ✔ Fixed | The results table now leads with ATP+WTA played (n=8,073, χ²=94, Q1/Q4=1.32). This matches my independent "WTA 1-Jan dropped" check exactly: n=8,073, χ²=94.3, Q1/Q4=1.319. The README describes the early-January heaping (35.3% of January births on days 1–10, p=0.002) and includes a sensitivity table. |
| R4. Fig 1 and palette | ✔ Fixed | Fig 1 is redrawn as points with CIs against the expected line: no bars, legend below the plot, wrapped title. All figures use Okabe-Ito with ATP blue and WTA orange, plus marker shape differences. |

**Optional points.**
- **Done:**
  - Liberal placeholder detection, which now also removes WTA 1-Jan (89 players).
  - A pooled southern-hemisphere check (n=1,209, Q1/Q4=1.34, the same as the north). This is a good argument against a birth-seasonality explanation.
  - Exploratory labels on the decade and hemisphere splits.
- **Declined:** a general-population baseline, with the reason given (no external data added) and an honest caveat. I accept this.

**Figures spot-checked:** fig 1 and fig 3. No clipped or overlapping text, colour-blind-safe colours, markers that differ between series, readable fonts. The unadjusted N/12 line is kept but now clearly labelled "ignores month length", which is fine.

## Verdict: **ACCEPT**
