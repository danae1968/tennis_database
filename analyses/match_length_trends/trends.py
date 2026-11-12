"""Yearly summaries (median + IQR + bootstrap CI) and trend regressions with clustered SEs."""
from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

from tennis.stats import boot_median_ci

SEED = 20240611
N_BOOT = 500


def yearly_summary(df: pd.DataFrame, value: str, by: list[str], min_n: int = 10) -> pd.DataFrame:
    """Per ``by`` group and year: n, mean, median, Q1, Q3 and a bootstrap CI for the median.

    Deterministic: the generator is re-seeded for every call.
    """
    rng = np.random.default_rng(SEED)
    rows = []
    for key, g in df.dropna(subset=[value]).groupby(by + ["year"], sort=True):
        x = g[value].to_numpy(float)
        if len(x) < min_n:
            continue
        lo, hi = boot_median_ci(x, rng, n_boot=N_BOOT)
        key = key if isinstance(key, tuple) else (key,)
        rows.append({**dict(zip(by + ["year"], key)), "n": len(x), "mean": x.mean(), "mean_lo": x.mean() - 1.96 * x.std(ddof=1) / np.sqrt(len(x)),
                     "mean_hi": x.mean() + 1.96 * x.std(ddof=1) / np.sqrt(len(x)), "median": np.median(x),
                     "q25": np.percentile(x, 25), "q75": np.percentile(x, 75), "ci_lo": lo, "ci_hi": hi})
    return pd.DataFrame(rows)


def trend_per_decade(df: pd.DataFrame, value: str, cluster: str, controls: str = "", y0: int = 2014,
                     log: bool = False) -> dict:
    """OLS of ``value`` on (year - y0) [+ controls] with cluster-robust SEs.

    Returns the change per decade in the units of ``value`` (or in % when ``log=True``, using
    100*(exp(10*slope)-1)), its 95% CI and p-value, the sample size and the number of clusters.
    """
    d = df.dropna(subset=[value]).copy()
    if log:
        d = d[d[value] > 0]; d["_y"] = np.log(d[value])
    else:
        d["_y"] = d[value]
    d["yc"] = d["year"] - y0
    d["_cl"] = pd.factorize(d[cluster])[0]
    f = "_y ~ yc" + (f" + {controls}" if controls else "")
    # small-cluster correction: CR1 variance with t(G-1) reference distribution (about 20 clusters in the Slam data)
    r = smf.ols(f, d).fit(cov_type="cluster", cov_kwds={"groups": d["_cl"], "use_correction": True, "df_correction": True}, use_t=True)
    b, (lo, hi) = float(r.params["yc"]), r.conf_int().loc["yc"].astype(float)
    tf = (lambda v: 100 * (np.exp(10 * v) - 1)) if log else (lambda v: 10 * v)
    return {"n": int(len(d)), "clusters": int(d["_cl"].nunique()), "per_decade": tf(b), "ci_lo": tf(float(lo)),
            "ci_hi": tf(float(hi)), "p": float(r.pvalues["yc"]), "unit": "% per decade" if log else f"{value} per decade"}


def trend_with_step(df: pd.DataFrame, value: str, cluster: str, controls: str = "", step_year: int = 2013,
                    log: bool = False) -> dict[str, dict]:
    """Trend per decade over the whole period, allowing a one-off level shift in ``step_year``, plus the
    separate trends before and from ``step_year``.  Returns ``{"whole (step allowed)", "before", "since"}``."""
    d = df.copy()
    d["step"] = (d["year"] >= step_year).astype(int)
    ctrl = (controls + " + " if controls else "") + "step"
    out = {"whole (step allowed)": trend_per_decade(d, value, cluster, ctrl, y0=int(d["year"].min()), log=log)}
    for lab, part in (("before", d[d["year"] < step_year]), ("since", d[d["year"] >= step_year])):
        try:
            out[lab] = trend_per_decade(part, value, cluster, controls, y0=int(part["year"].min()), log=log)
        except Exception as e:           # too few years for a trend
            out[lab] = {"n": len(part), "per_decade": np.nan, "error": str(e)}
    return out
