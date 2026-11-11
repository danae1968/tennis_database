"""Figures. All functions save a PNG and return its path.

House style from :mod:`tennis.plotting` (Okabe-Ito; ATP/men blue, WTA/women orange; constrained
layout; tight bbox at 150 dpi); distinct markers per series; titles wrapped to the figure width.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt  # noqa: F401
import numpy as np
import pandas as pd

from tennis.plotting import BLACK, BLUE, GREEN, ORANGE, PURPLE, SKY, VERMILLION, new_figure, save_figure, wrap

from .months import MONTHS

VERM = VERMILLION
# series -> (colour, marker, linestyle); ATP (men) blue, WTA (women) orange as everywhere in the project
STYLE = {"ATP": (BLUE, "o", "-"), "WTA": (ORANGE, "s", "--"), "all": (BLACK, "D", "-"), "elite": (VERM, "^", "--"),
         "played": (BLUE, "o", "-"), "ATP+WTA|played": (BLUE, "o", "-")}
COL = {k: v[0] for k, v in STYLE.items()}


def _title(fig, title: str, width: int = 70) -> None:
    fig.suptitle(wrap(title, width), fontsize=12)


def _save(fig, path: Path) -> Path:
    return save_figure(fig, path)


def plot_obs_vs_exp(t: pd.DataFrame, title: str, path: Path) -> Path:
    """Observed counts (points, 95% CI) against the days-adjusted expectation (line); no bars, so the
    y-axis need not start at zero. The dotted line is the unadjusted mean N/12 for reference."""
    fig, ax = new_figure(figsize=(9.5, 5.8)); x = np.arange(12)
    n = t["observed"].sum()
    lo, hi = t["ratio_lo"] * t["expected"], t["ratio_hi"] * t["expected"]
    ax.plot(x, t["expected"], "s--", color=ORANGE, ms=7, label="Expected (proportional to days in month)")
    ax.axhline(n / 12, color="grey", ls=":", label=f"Unadjusted mean N/12 = {n/12:.0f} (ignores month length)")
    ax.errorbar(x, t["observed"], yerr=[t["observed"] - lo, hi - t["observed"]], fmt="o", color=BLUE, ecolor=BLUE, ms=8, capsize=4,
                label="Observed births (95% CI)")
    ax.set_xticks(x, MONTHS); ax.set_xlabel("Birth month"); ax.set_ylabel("Number of players"); ax.grid(alpha=.3)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=1, frameon=False)
    _title(fig, title); return _save(fig, path)


def plot_ratio(tables: dict[str, pd.DataFrame], title: str, path: Path, colors: dict | None = None) -> Path:
    """Observed/expected ratio with 95% CI, one series per entry in ``tables`` (offset side by side)."""
    fig, ax = new_figure(figsize=(9.5, 5.8)); x = np.arange(12); k = len(tables); w = 0.8 / k
    for i, (name, t) in enumerate(tables.items()):
        c, m, ls = STYLE.get(name, (BLUE, "o", "-"))
        xs = x - 0.4 + w * (i + .5)
        ax.errorbar(xs, t["ratio"], yerr=[t["ratio"] - t["ratio_lo"], t["ratio_hi"] - t["ratio"]], fmt=m, color=c, capsize=3, ms=7, label=name.replace("|played", " (>=1 tour match)"))
    ax.axhline(1, color=BLACK, lw=1); ax.set_xticks(x, MONTHS)
    ax.set_xlabel("Birth month"); ax.set_ylabel("Observed / expected (1 = no excess)")
    ax.legend(loc="upper right", frameon=True); ax.grid(alpha=.3)
    _title(fig, title); return _save(fig, path)


def plot_quarters(tables: dict[str, pd.DataFrame], title: str, path: Path) -> Path:
    """Observed/expected ratio per quarter with 95% CI (relative age effect)."""
    fig, ax = new_figure(figsize=(8, 5.8)); x = np.arange(4); k = len(tables); w = 0.8 / k
    hatches = {"ATP": "", "WTA": "//"}
    for i, (name, t) in enumerate(tables.items()):
        xs = x - 0.4 + w * (i + .5)
        ax.bar(xs, t["ratio"], width=w * .9, color=STYLE[name][0], alpha=.75, hatch=hatches.get(name, ""), edgecolor=BLACK, label=name)
        ax.errorbar(xs, t["ratio"], yerr=[t["ratio"] - t["ratio_lo"], t["ratio_hi"] - t["ratio"]], fmt="none", ecolor=BLACK, capsize=3)
    ax.axhline(1, color=BLACK, lw=1); ax.set_xticks(x, ["Q1\nJan-Mar", "Q2\nApr-Jun", "Q3\nJul-Sep", "Q4\nOct-Dec"])
    ax.set_ylim(0, 1.35); ax.set_xlabel("Birth quarter"); ax.set_ylabel("Observed / expected")
    ax.legend(loc="upper right"); _title(fig, title, 55); return _save(fig, path)
