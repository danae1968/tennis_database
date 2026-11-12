"""Long-run shape of the tour trends: like-for-like yearly levels, slope before vs after a knot year,
and a check for step changes that would point to a change of data source rather than of tennis.

All three compare each tournament with itself (tournament fixed effects), weight each match by the
denominator of its rate (so the fit targets the pooled rate) and cluster standard errors by tournament.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy.stats import norm

KNOT = 2016            # start of the last ten full seasons (2016-2025)
MIN_SEASONS = 3        # tournaments seen in fewer seasons carry no within-event information about years


def _fit(df: pd.DataFrame, formula: str, weight: str, cluster: str):
    return smf.wls(formula, df, weights=df[weight]).fit(
        cov_type="cluster", cov_kwds={"groups": pd.factorize(df[cluster])[0]})


def like_for_like_index(d: pd.DataFrame, rate: str, num: str, den: str, ref_year: int,
                        cluster: str = "tournament") -> pd.DataFrame:
    """Yearly level with each tournament compared with itself: WLS of the per-match ``rate`` on
    C(year) + C(tournament).  Year effects are shifted so that ``ref_year`` equals its pooled rate
    (num/den over that year's matches).  Columns: year, rate, lo, hi (95% CI of the year effect), n_matches.
    Only tournaments seen in at least :data:`MIN_SEASONS` seasons are used."""
    seasons = d.groupby(cluster)["year"].nunique()
    x = d[d[cluster].isin(seasons[seasons >= MIN_SEASONS].index)]
    res = _fit(x, f"{rate} ~ C(year, Treatment({ref_year})) + C({cluster})", den, cluster)
    ref = x[x["year"] == ref_year]
    base = ref[num].sum() / ref[den].sum()
    rows = []
    for y in sorted(x["year"].unique()):
        k = f"C(year, Treatment({ref_year}))[T.{y}]"
        b, se = (float(res.params[k]), float(res.bse[k])) if k in res.params else (0.0, 0.0)
        rows.append({"year": int(y), "rate": base + b, "lo": base + b - 1.96 * se, "hi": base + b + 1.96 * se,
                     "n_matches": int((x["year"] == y).sum())})
    return pd.DataFrame(rows)


def slope_change(d: pd.DataFrame, rate: str, den: str, knot: int = KNOT, cluster: str = "tournament",
                 scale: float = 100) -> dict:
    """Continuous piecewise-linear trend with one knot (tournament fixed effects).  Returns the slope
    before and after ``knot`` and their difference, per decade (x ``scale``), with a 95% CI and p-value
    for the difference."""
    x = d.copy()
    x["_pre"] = np.minimum(x["year"] - knot, 0) / 10
    x["_post"] = np.maximum(x["year"] - knot, 0) / 10
    res = _fit(x, f"{rate} ~ _pre + _post + C({cluster})", den, cluster)
    c = res.cov_params()
    diff = float(res.params["_post"] - res.params["_pre"])
    se = float(np.sqrt(c.loc["_post", "_post"] + c.loc["_pre", "_pre"] - 2 * c.loc["_post", "_pre"]))
    return {"slope_before": scale * float(res.params["_pre"]), "slope_after": scale * float(res.params["_post"]),
            "change": scale * diff, "change_lo": scale * (diff - 1.96 * se), "change_hi": scale * (diff + 1.96 * se),
            "p_change": float(2 * norm.sf(abs(diff / se))), "n": int(len(x)), "first_year": int(x["year"].min()),
            "last_year": int(x["year"].max())}


def year_on_year_jumps(index: pd.DataFrame, scale: float = 100) -> pd.DataFrame:
    """Year-on-year changes of a like-for-like index, and each change relative to the median absolute
    change of that series (a source switch shows up as a single large, lasting step)."""
    g = index.sort_values("year")
    dlt = g["rate"].diff() * scale
    mad = float(np.nanmedian(np.abs(dlt)))
    out = pd.DataFrame({"year": g["year"].values, "change": dlt.values})
    out["relative_to_median_change"] = out["change"].abs() / mad
    return out.dropna().reset_index(drop=True)
