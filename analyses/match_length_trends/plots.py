"""Figures for the trend analysis.

House style from :mod:`tennis.plotting` (Okabe-Ito; men blue, women orange; constrained layout; tight
bbox at 150 dpi); distinct markers and line styles per series; no in-plot annotations that can overlap
(rule-change markers are explained in a legend below the figure).
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt  # noqa: F401
import pandas as pd
from matplotlib.lines import Line2D

from tennis.plotting import BAND_ALPHA, BLACK, BLUE, GREEN, ORANGE, PURPLE, SKY, VERMILLION, new_figure, save_figure, wrap

VERM = VERMILLION
# label (exact, then first matching key by substring) -> (colour, marker, linestyle)
STYLE = {
    "men": (BLUE, "o", "-"), "women": (ORANGE, "s", "--"),
    "ATP bo3": (BLUE, "o", "-"), "ATP bo5": (SKY, "D", "-."), "WTA": (ORANGE, "s", "--"), "Challenger": (GREEN, "^", ":"),
    "men 3 sets": (SKY, "o", "-"), "men 4 sets": (BLUE, "s", "--"), "men 5 sets": (BLACK, "^", "-."),
    "women 2 sets": (ORANGE, "o", "-"), "women 3 sets": (VERM, "s", "--"),
    "US Open": (BLUE, "o", "-"), "Wimbledon": (GREEN, "s", "--"), "Australian Open": (ORANGE, "^", "-."), "French Open": (PURPLE, "D", ":"),
    "Hard": (BLUE, "o", "-"), "Clay": (ORANGE, "s", "--"), "Grass": (GREEN, "^", ":"),
}
# panel-specific labels such as "ATP bo3 2 sets" fall back to a cycle below
FALLBACK = [(SKY, "o", "-"), (BLUE, "s", "--"), (BLACK, "^", "-."), (ORANGE, "D", ":")]
RULES = [(2018, "2018: 25-second serve clock (US Open)", "--"), (2019, "2019: Wimbledon 12-12 final-set tiebreak", (0, (6, 2, 1, 2, 1, 2))),
         (2020, "2020: COVID-19 season", ":"), (2022, "2022: 10-point final-set tiebreak at 6-6 (US Open, Wimbledon)", "-.")]


def style_for(label: str, i: int = 0) -> tuple[str, str, str]:
    """(colour, marker, linestyle) for a series label."""
    if label in STYLE:
        return STYLE[label]
    for grp in ("ATP bo3", "ATP bo5", "WTA", "Challenger"):          # e.g. "WTA 3 sets": group colour, marker/line by series
        if label.startswith(grp):
            return STYLE[grp][0], FALLBACK[i % len(FALLBACK)][1], FALLBACK[i % len(FALLBACK)][2]
    return FALLBACK[i % len(FALLBACK)]


def _rules(ax, years) -> None:
    lo, hi = min(years), max(years)
    for x, _, ls in RULES:
        if lo <= x <= hi:
            ax.axvline(x, color="grey", ls=ls, lw=1.1, zorder=0)


def _rule_legend(fig, years) -> None:
    lo, hi = min(years), max(years)
    hs = [Line2D([0], [0], color="grey", ls=ls, lw=1.3, label=lab) for x, lab, ls in RULES if lo <= x <= hi]
    fig.legend(handles=hs, loc="outside lower center", ncol=2, frameon=False, title="Vertical lines mark rule changes and events", title_fontsize=10.5)


def line_bands(ax, t: pd.DataFrame, label: str, i: int = 0, stat: str = "median", legend_label: str | None = None) -> None:
    """Median line, IQR band (alpha .2) and bootstrap-CI whiskers for one series; or mean +- CI if ``stat='mean'``."""
    c, m, ls = style_for(label, i)
    lab = legend_label or label
    if stat == "mean":
        ax.errorbar(t["year"], t["mean"], yerr=[t["mean"] - t["mean_lo"], t["mean_hi"] - t["mean"]], color=c, marker=m, ls=ls,
                    ms=6, capsize=3, lw=1.6, label=lab)
        return
    ax.fill_between(t["year"], t["q25"], t["q75"], color=c, alpha=BAND_ALPHA, lw=0)
    ax.errorbar(t["year"], t["median"], yerr=[t["median"] - t["ci_lo"], t["ci_hi"] - t["median"]], color=c, marker=m, ls=ls,
                ms=6, capsize=3, lw=1.6, label=lab)


def _finish(fig, path: Path, title: str, width: int, years) -> Path:
    fig.suptitle(wrap(title, width), fontsize=12)
    _rule_legend(fig, years)
    return save_figure(fig, path)


def series_figure(tables: dict[str, pd.DataFrame], title: str, ylabel: str, path: Path, colors: dict | None = None, stat: str = "median") -> Path:
    """One axis, one line per entry. Shading = interquartile range of the unit; bars = 95% CI of the median."""
    fig, ax = new_figure(figsize=(9.5, 6))
    yrs = []
    for i, (k, t) in enumerate(tables.items()):
        line_bands(ax, t, k, i, stat); yrs += list(t["year"])
    _rules(ax, yrs)
    ax.set_xlabel("Year"); ax.set_ylabel(ylabel); ax.grid(alpha=.3)
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0), frameon=False)
    return _finish(fig, path, title, 80, yrs)


def panel_figure(panels: dict[str, dict[str, pd.DataFrame]], title: str, ylabel: str, path: Path, colors: dict | None = None, stat: str = "median") -> Path:
    """Several subplots (one per panel name), each with its own series dict and its own legend underneath."""
    n = len(panels)
    fig, axes = new_figure(1, n, figsize=(5.4 * n, 6.6))
    axes = [axes] if n == 1 else list(axes)
    allyrs = []
    for ax, (name, tabs) in zip(axes, panels.items()):
        yrs = []
        for i, (k, t) in enumerate(tabs.items()):
            line_bands(ax, t, k, i, stat); yrs += list(t["year"])
        if yrs:
            _rules(ax, yrs); allyrs += yrs
        ax.set_title(name); ax.set_xlabel("Year"); ax.grid(alpha=.3)
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.17), frameon=False, ncol=1)
    axes[0].set_ylabel(ylabel)
    return _finish(fig, path, title, 100, allyrs)
