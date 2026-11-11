"""Statistics helpers shared by the analyses: proportion CIs (Wilson, cluster-adjusted Wilson,
Clopper-Pearson), bootstrap CI of a median, Holm correction, chi-square goodness of fit and a
match-clustered logistic regression."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy import stats as _st

Z95 = 1.959963984540054


def wilson_ci(k: float, n: float, z: float = Z95) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion k/n (k may be fractional)."""
    if n <= 0:
        return (float("nan"), float("nan"))
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (centre - half, centre + half)


def cluster_prop_ci(y: np.ndarray, cluster: np.ndarray | None = None, z: float = Z95) -> dict:
    """Proportion with a 95% CI that respects clustering (e.g. several sets from the same match).

    The cluster-robust (sandwich) variance of the mean gives a design effect
    ``deff = var_cluster / var_iid``; the Wilson interval is then computed with the effective sample
    size n / deff.  With one observation per cluster this is exactly Wilson.
    Returns dict(p, lo, hi, n, n_clusters, deff).
    """
    y = np.asarray(y, dtype=float)
    n = len(y)
    if n == 0:
        return dict(p=np.nan, lo=np.nan, hi=np.nan, n=0, n_clusters=0, deff=np.nan)
    p = y.mean()
    if cluster is None:
        cluster = np.arange(n)
    g = pd.DataFrame({"r": y - p, "c": np.asarray(cluster)}).groupby("c").r.sum()
    k = len(g)
    var_iid = p * (1 - p) / n
    if k > 1 and var_iid > 0:
        var_cl = (g**2).sum() * k / (k - 1) / n**2
        deff = max(var_cl / var_iid, 1e-9) if (g.index.size < n) else 1.0
    else:
        deff = 1.0
    lo, hi = wilson_ci(p * n / deff, n / deff, z)
    return dict(p=p, lo=lo, hi=hi, n=n, n_clusters=k, deff=deff)


def clopper_pearson(k: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """Exact (Clopper-Pearson) 100*(1-alpha)% CI for a binomial proportion k/n.
    (Parameterised by ``alpha`` so the quantiles are exactly 0.025 / 0.975 for the default.)"""
    lo = _st.beta.ppf(alpha / 2, k, n - k + 1) if k > 0 else 0.0
    hi = _st.beta.ppf(1 - alpha / 2, k + 1, n - k) if k < n else 1.0
    return float(lo), float(hi)


def holm(p: np.ndarray) -> np.ndarray:
    """Holm-Bonferroni adjusted p-values."""
    p = np.asarray(p, dtype=float)
    order = np.argsort(p)
    adj = np.empty_like(p)
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, (len(p) - rank) * p[i])
        adj[i] = min(1.0, running)
    return adj


def boot_median_ci(x: np.ndarray, rng: np.random.Generator, n_boot: int = 500) -> tuple[float, float]:
    """95% percentile bootstrap CI of the median (NaN for fewer than 5 values)."""
    x = np.asarray(x, dtype=float)
    if len(x) < 5:
        return (np.nan, np.nan)
    idx = rng.integers(0, len(x), size=(n_boot, len(x)))
    m = np.median(x[idx], axis=1)
    return float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def chisq_gof(observed: np.ndarray, probs: np.ndarray) -> dict:
    """Chi-square goodness of fit of ``observed`` counts against cell probabilities ``probs``.
    Returns n, chi2, df, p and Cramer's V."""
    counts = np.asarray(observed, dtype=float)
    exp = counts.sum() * np.asarray(probs, dtype=float)
    chi2, p = _st.chisquare(counts, exp)
    return {"n": int(counts.sum()), "chi2": float(chi2), "df": len(counts) - 1, "p": float(p),
            "cramers_v": float(np.sqrt(chi2 / (counts.sum() * (len(counts) - 1))))}


def expit(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def logit_cluster(df: pd.DataFrame, y: str, xs: list[str], cluster: str) -> dict:
    """Logistic regression of ``y`` on ``xs`` + intercept with cluster-robust standard errors.

    If all covariates are coded antisymmetrically from the point of view of the unit of interest
    (they flip sign when the roles are swapped), ``expit(intercept)`` is the probability at "level"
    covariates.  Returns the adjusted probability with CI and all coefficients.
    """
    import statsmodels.api as sm

    d = df.dropna(subset=[y, *xs])
    X = sm.add_constant(d[xs].astype(float), has_constant="add")
    res = sm.GLM(d[y].astype(float), X, family=sm.families.Binomial()).fit(
        cov_type="cluster", cov_kwds={"groups": pd.factorize(d[cluster])[0]})
    b0, se0 = res.params["const"], res.bse["const"]
    out = dict(p_adj=expit(b0), lo=expit(b0 - Z95 * se0), hi=expit(b0 + Z95 * se0), n=int(len(d)),
               n_clusters=int(d[cluster].nunique()), covariates="+".join(xs) if xs else "(none)")
    for v in xs:
        out[f"coef_{v}"] = float(res.params[v])
        out[f"se_{v}"] = float(res.bse[v])
    return out
