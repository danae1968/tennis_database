"""Birth-month specific statistics: month-length expectations, month and quarter tables,
goodness of fit against month length, and the Jan->Dec trend test. Generic helpers come from
:mod:`tennis.stats`."""
from __future__ import annotations

import calendar

import numpy as np
import pandas as pd
from scipy import stats

from tennis.stats import chisq_gof, clopper_pearson, holm  # noqa: F401  (holm re-exported)

DAYS = np.array([31, 28.25, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31])   # Feb = 28.25 (leap years)
MONTHS = [calendar.month_abbr[i] for i in range(1, 13)]


def expected_probs(days: np.ndarray = DAYS) -> np.ndarray:
    """Probability of a birth in each month under uniformity over days of the year."""
    days = np.asarray(days, dtype=float)
    return days / days.sum()


def expected_counts(n: int, days: np.ndarray = DAYS) -> np.ndarray:
    """Expected monthly counts for ``n`` births, proportional to month length."""
    return n * expected_probs(days)


def month_table(counts: np.ndarray, days: np.ndarray = DAYS) -> pd.DataFrame:
    """Per-month observed/expected, ratio with 95% Clopper-Pearson CI, standardised residual and Holm p."""
    counts = np.asarray(counts, dtype=int)
    n = int(counts.sum())
    pr = expected_probs(days)
    exp = n * pr
    ci = np.array([clopper_pearson(int(k), n) for k in counts])
    lo, hi = ci[:, 0] * n, ci[:, 1] * n
    pvals = np.array([stats.binomtest(int(k), n, p).pvalue for k, p in zip(counts, pr)])
    return pd.DataFrame({
        "month": MONTHS, "observed": counts, "expected": exp.round(2),
        "ratio": counts / exp, "ratio_lo": lo / exp, "ratio_hi": hi / exp,
        "std_resid": (counts - exp) / np.sqrt(exp * (1 - pr)),
        "p_binom": pvals, "p_holm": holm(pvals),
    })


def chi_square_gof(counts: np.ndarray, groups: list[list[int]] | None = None, days: np.ndarray = DAYS) -> dict:
    """Chi-square goodness of fit against month-length expectations (optionally on grouped months)."""
    counts = np.asarray(counts, dtype=float)
    pr = expected_probs(days)
    if groups is not None:
        counts = np.array([counts[g].sum() for g in groups])
        pr = np.array([pr[g].sum() for g in groups])
    return chisq_gof(counts, pr)


QUARTERS = [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9, 10, 11]]


def quarter_table(counts: np.ndarray, days: np.ndarray = DAYS) -> pd.DataFrame:
    """Observed / expected by calendar quarter with 95% Clopper-Pearson CI."""
    counts = np.asarray(counts, dtype=int)
    n = int(counts.sum()); pr = expected_probs(days)
    rows = []
    for q, g in enumerate(QUARTERS, 1):
        k = int(counts[g].sum()); p = pr[g].sum(); e = n * p
        cl, ch = clopper_pearson(k, n)
        lo = cl * n / e; hi = ch * n / e
        rows.append({"quarter": f"Q{q}", "observed": k, "expected": round(e, 1), "ratio": k / e,
                     "ratio_lo": lo, "ratio_hi": hi})
    return pd.DataFrame(rows)


def trend_test(counts: np.ndarray) -> dict:
    """Poisson regression of monthly counts on month index with a log-days offset.

    The slope is the log rate-ratio per month; exp(slope*11) is the Dec/Jan relative rate.
    Standard errors are scaled by the Pearson dispersion **only if it exceeds 1** (quasi-Poisson);
    with 12 counts the estimated dispersion can fall below 1 by chance, and shrinking the SE
    below the Poisson value would be anti-conservative. ``dispersion_used`` reports the scale applied.
    """
    import statsmodels.api as sm
    counts = np.asarray(counts, dtype=float)
    X = sm.add_constant(np.arange(12, dtype=float))
    fam = sm.families.Poisson()
    est = sm.GLM(counts, X, family=fam, offset=np.log(DAYS)).fit(scale="X2")
    disp = max(float(est.scale), 1.0)
    res = sm.GLM(counts, X, family=fam, offset=np.log(DAYS)).fit(scale=disp)
    b, se, p = float(res.params[1]), float(res.bse[1]), float(res.pvalues[1])
    return {"slope_per_month": b, "se": se, "p": p, "dec_vs_jan_rate_ratio": float(np.exp(11 * b)),
            "pearson_dispersion_estimated": float(est.scale), "dispersion_used": disp}


def month_counts(months: pd.Series) -> np.ndarray:
    """Counts of months 1..12 as an int array of length 12."""
    return months.value_counts().reindex(range(1, 13), fill_value=0).sort_index().to_numpy(dtype=int)
