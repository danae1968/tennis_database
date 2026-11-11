"""Logistic models for P(player 1 wins), evaluated on a later test period."""
from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm

from tennis.stats import auc, log_loss

MODELS = {                      # name -> covariates (all antisymmetric: they flip sign when players swap)
    "Coin flip": [],
    "Height only": ["ht_diff"],
    "Ranking only": ["log_rank_ratio"],
    "Ranking + height": ["log_rank_ratio", "ht_diff"],
}


def fit(train: pd.DataFrame, xs: list[str], cluster: str = "tourney_id"):
    """Logit of ``p1_won`` on ``xs`` WITHOUT an intercept (players are in random order and every
    predictor flips sign when they swap, so P = 0.5 at zero differences by symmetry), with
    tournament-clustered SEs; None for the coin flip."""
    if not xs:
        return None
    X = train[xs].astype(float)
    return sm.Logit(train["p1_won"].astype(float), X).fit(
        disp=0, cov_type="cluster", cov_kwds={"groups": pd.factorize(train[cluster])[0]})


def predict(res, df: pd.DataFrame, xs: list[str]) -> np.ndarray:
    """Predicted P(player 1 wins); 0.5 for the coin flip."""
    if res is None:
        return np.full(len(df), 0.5)
    return np.asarray(res.predict(df[xs].astype(float)))


def metrics(y: np.ndarray, p: np.ndarray) -> dict:
    """Accuracy (ties at exactly 0.5 count as half right), AUC and log-loss."""
    y = np.asarray(y, dtype=float)
    p = np.asarray(p, dtype=float)
    acc = np.where(p == 0.5, 0.5, ((p > 0.5) == (y == 1)).astype(float)).mean()
    return {"accuracy": float(acc), "auc": float(auc(y, p)) if len(np.unique(p)) > 1 else 0.5,
            "log_loss": float(log_loss(y, p)), "n": int(len(y))}


def evaluate(train: pd.DataFrame, test: pd.DataFrame, models: dict = MODELS) -> tuple[pd.DataFrame, dict]:
    """Fit every model on ``train`` and score it on ``test`` (same rows for all models).
    Returns (metrics table, {model name: (fit result, test predictions)})."""
    rows, fitted = [], {}
    for name, xs in models.items():
        res = fit(train, xs)
        p = predict(res, test, xs)
        fitted[name] = (res, p)
        row = {"model": name, **metrics(test["p1_won"].values, p)}
        if res is not None and "ht_diff" in xs:
            b, se = float(res.params["ht_diff"]), float(res.bse["ht_diff"])
            row.update(height_or_per_10cm=float(np.exp(10 * b)), height_or_lo=float(np.exp(10 * (b - 1.96 * se))),
                       height_or_hi=float(np.exp(10 * (b + 1.96 * se))), height_p=float(res.pvalues["ht_diff"]))
        rows.append(row)
    return pd.DataFrame(rows), fitted


def paired_bootstrap(y: np.ndarray, p_a: np.ndarray, p_b: np.ndarray, reps: int = 1000, seed: int = 0) -> dict:
    """Bootstrap (over test matches) of the improvement of model b over model a:
    delta log-loss (a - b, positive = b better), delta AUC (b - a) and delta accuracy (b - a)."""
    rng = np.random.default_rng(seed)
    y, p_a, p_b = (np.asarray(v, dtype=float) for v in (y, p_a, p_b))
    n = len(y)
    out = {"d_logloss": [], "d_auc": [], "d_accuracy": []}
    for _ in range(reps):
        i = rng.integers(0, n, n)
        ma, mb = metrics(y[i], p_a[i]), metrics(y[i], p_b[i])
        out["d_logloss"].append(ma["log_loss"] - mb["log_loss"])
        out["d_auc"].append(mb["auc"] - ma["auc"])
        out["d_accuracy"].append(mb["accuracy"] - ma["accuracy"])
    full_a, full_b = metrics(y, p_a), metrics(y, p_b)
    point = {"d_logloss": full_a["log_loss"] - full_b["log_loss"], "d_auc": full_b["auc"] - full_a["auc"],
             "d_accuracy": full_b["accuracy"] - full_a["accuracy"]}
    res = {}
    for k, v in out.items():
        v = np.asarray(v)
        res[k] = point[k]
        res[f"{k}_lo"], res[f"{k}_hi"] = float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))
        res[f"{k}_share_le0"] = float((v <= 0).mean())
    return res


def taller_player_wins(df: pd.DataFrame) -> dict:
    """Plain-language baseline: share of matches (with a height difference) won by the taller player."""
    d = df[df["ht_diff"].notna() & (df["ht_diff"] != 0)]
    taller_won = ((d["ht_diff"] > 0) == (d["p1_won"] == 1)).astype(float)
    from tennis.stats import wilson_ci
    lo, hi = wilson_ci(taller_won.sum(), len(d))
    return {"taller_wins": float(taller_won.mean()), "lo": lo, "hi": hi, "n": int(len(d)),
            "share_equal_height": float((df["ht_diff"] == 0).mean())}
