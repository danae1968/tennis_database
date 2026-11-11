"""Match-clustered bootstrap helpers (each row of the count arrays is one match, so resampling rows
resamples matches; points and games within a match are not treated as independent)."""
from __future__ import annotations

from typing import Callable

import numpy as np

N_BOOT = 2000          # resamples everywhere (tour-wide references included)
_CHUNK = 250           # resamples per block, to bound memory for large tour-wide samples


def boot_ci(counts: np.ndarray, stat: Callable[[np.ndarray], np.ndarray], seed: int, n_boot: int = N_BOOT,
            return_sd: bool = False):
    """Point estimate and 95% percentile CI of ``stat`` under a match bootstrap (optionally also the bootstrap SD).

    ``counts`` has shape (n_matches, k); ``stat`` maps column sums (shape (..., k)) to the statistic, so it
    must be vectorised over leading axes.  Deterministic for a given ``seed``.  The reported CI is widened if
    needed to contain the point estimate (a percentile interval of a skewed ratio can miss it by a hair).
    """
    counts = np.asarray(counts, dtype=float)
    n = len(counts)
    nan = (np.nan, np.nan, np.nan, np.nan) if return_sd else (np.nan, np.nan, np.nan)
    if n == 0:
        return nan
    rng = np.random.default_rng(seed)
    reps = []
    with np.errstate(divide="ignore", invalid="ignore"):
        est = float(stat(counts.sum(0)))
        for start in range(0, n_boot, _CHUNK):
            m = min(_CHUNK, n_boot - start)
            idx = rng.integers(0, n, size=(m, n))
            reps.append(np.asarray(stat(counts[idx].sum(1))))
    reps = np.concatenate(reps)
    reps = reps[np.isfinite(reps)]
    if len(reps) < 10:
        return (est, np.nan, np.nan, np.nan) if return_sd else (est, np.nan, np.nan)
    lo, hi = np.percentile(reps, [2.5, 97.5])
    out = (est, float(min(lo, est)), float(max(hi, est)))
    return out + (float(reps.std(ddof=1)),) if return_sd else out


def ratio(num: int, den: int):
    """Statistic: ratio of two column sums (columns ``num`` and ``den``)."""
    return lambda s: s[..., num] / s[..., den]
