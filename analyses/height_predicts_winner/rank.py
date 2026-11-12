"""Does height predict ranking?  Player-level association of height with tour-level ranking (2016-2026).

Players are the unit.  Each player with a known height and at least ``MIN_MATCHES`` ranked tour-level
matches gets two ranking summaries: the **median** rank across those matches (primary for the
correlation: robust to one lucky week and to career length) and the **best** rank reached (primary for
"reached the top 100 / 20 / 10", which is defined by the best rank).  Both are reported.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from analyses.height_predicts_winner import data as D
from analyses.height_predicts_winner import model as Mo
from tennis.stats import wilson_ci

MIN_MATCHES = 20
BAND_CM = 5
MIN_BAND_PLAYERS = 30
TOP_LEVELS = (100, 20, 10)


def player_table(raw: pd.DataFrame, min_matches: int = MIN_MATCHES, require_height: bool = True) -> pd.DataFrame:
    """One row per (tour, player): height (median of recorded heights, cm), ranked match count,
    median and best rank.  Team events are excluded; players without a valid height or with fewer than
    ``min_matches`` ranked matches are dropped (``require_height=False`` keeps players without a height,
    with NaN height)."""
    d = raw[~raw["tourney_level"].isin(D.TEAM_LEVELS)]
    parts = []
    for side in ("winner", "loser"):
        parts.append(pd.DataFrame({"tour": d["tour"].values, "player": d[f"{side}_id"].astype(str).values,
                                   "ht": D.clean_height(d[f"{side}_ht"]).values,
                                   "rank": pd.to_numeric(d[f"{side}_rank"], errors="coerce").values}))
    p = pd.concat(parts, ignore_index=True)
    ranked = p.dropna(subset=["rank"])
    g = ranked.groupby(["tour", "player"]).agg(n_matches=("rank", "size"), median_rank=("rank", "median"),
                                               best_rank=("rank", "min")).reset_index()
    h = p.dropna(subset=["ht"]).groupby(["tour", "player"])["ht"].median().rename("height").reset_index()
    out = g.merge(h, on=["tour", "player"], how="inner" if require_height else "left")
    return out[out["n_matches"] >= min_matches].reset_index(drop=True)


def spearman_height_rank(df: pd.DataFrame, rank_col: str = "median_rank", reps: int = 1000, seed: int = 0) -> dict:
    """Spearman correlation of height with ranking *quality* (minus the rank number), so a positive value
    means taller players are ranked better.  95% CI from a bootstrap over players."""
    h, r = df["height"].to_numpy(float), -df[rank_col].to_numpy(float)
    rho = float(spearmanr(h, r)[0])
    rng = np.random.default_rng(seed)
    n = len(df)
    boots = np.empty(reps)
    for i in range(reps):
        idx = rng.integers(0, n, n)
        boots[i] = spearmanr(h[idx], r[idx])[0]
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return {"rho": rho, "lo": float(lo), "hi": float(hi), "n": n}


def height_bands(heights: pd.Series, width: int = BAND_CM, min_n: int = MIN_BAND_PLAYERS) -> list[tuple[int, int]]:
    """Consecutive bands ``[lo, hi)`` of about ``width`` cm covering every height, with bands holding fewer
    than ``min_n`` players merged into the neighbour that has fewer players, until none is thin
    (or one band is left)."""
    h = np.asarray(heights, float)
    lo0, hi0 = int(np.floor(h.min() / width) * width), int(np.floor(h.max() / width) * width) + width
    bands = [(a, a + width) for a in range(lo0, hi0, width)]
    count = lambda b: int(((h >= b[0]) & (h < b[1])).sum())  # noqa: E731
    while len(bands) > 1:
        counts = [count(b) for b in bands]
        i = int(np.argmin(counts))
        if counts[i] >= min_n:
            break
        if i == 0:
            j = 1
        elif i == len(bands) - 1:
            j = i - 1
        else:
            j = i - 1 if counts[i - 1] <= counts[i + 1] else i + 1
        a, b = sorted((i, j))
        bands[a:b + 1] = [(bands[a][0], bands[b][1])]
    return bands


def band_label(b: tuple[int, int]) -> str:
    return f"{b[0]}-{b[1] - 1}"


def reach_by_band(df: pd.DataFrame, bands: list[tuple[int, int]], levels=TOP_LEVELS, rank_col: str = "best_rank") -> pd.DataFrame:
    """Share of players whose best rank was within each top level, by height band (Wilson 95% CIs)."""
    rows = []
    for b in bands:
        g = df[(df["height"] >= b[0]) & (df["height"] < b[1])]
        row = {"band": band_label(b), "mid_cm": float(g["height"].median()), "n_players": len(g)}
        for lv in levels:
            k = int((g[rank_col] <= lv).sum())
            lo, hi = wilson_ci(k, len(g))
            row.update({f"top{lv}": k / len(g), f"top{lv}_lo": lo, f"top{lv}_hi": hi})
        rows.append(row)
    return pd.DataFrame(rows)


def attenuation(x: pd.DataFrame, reps: int = 200, seed: int = 0) -> dict:
    """Share of height's effect on winning that ranking absorbs: ``1 - b_given_rank / b_alone`` (coefficients
    on the height difference, no-intercept models on the same complete-case matches), with a 95% CI from a
    bootstrap that resamples tournaments.  Reported on the log-odds scale (logit) and, as a check, on the
    probability scale (linear probability model, which does not suffer from logit non-collapsibility)."""
    def coefs(df: pd.DataFrame) -> dict:
        ba = float(Mo.fit(df, ["ht_diff"]).params["ht_diff"])
        bg = float(Mo.fit(df, ["log_rank_ratio", "ht_diff"]).params["ht_diff"])
        y = df["p1_won"].to_numpy(float) - 0.5            # centred: P = 0.5 at zero differences
        h = df["ht_diff"].to_numpy(float)
        X = df[["log_rank_ratio", "ht_diff"]].to_numpy(float)
        la = float((h @ y) / (h @ h))
        lg = float(np.linalg.lstsq(X, y, rcond=None)[0][1])
        return {"ba": ba, "bg": bg, "logit": 1 - bg / ba, "lpm": 1 - lg / la}
    c = coefs(x)
    rng = np.random.default_rng(seed)
    groups = {t: g.index.values for t, g in x.groupby("tourney_id")}
    keys = np.array(list(groups))
    boots = {"logit": [], "lpm": []}
    for _ in range(reps):
        cb = coefs(x.loc[np.concatenate([groups[k] for k in rng.choice(keys, len(keys))])])
        for k in boots:
            boots[k].append(cb[k])
    out = {"share_absorbed": c["logit"], "lo": float(np.percentile(boots["logit"], 2.5)),
           "hi": float(np.percentile(boots["logit"], 97.5)),
           "or10_alone": float(np.exp(10 * c["ba"])), "or10_given_rank": float(np.exp(10 * c["bg"])), "n": len(x),
           "share_absorbed_lpm": c["lpm"], "lpm_lo": float(np.percentile(boots["lpm"], 2.5)),
           "lpm_hi": float(np.percentile(boots["lpm"], 97.5))}
    return out
