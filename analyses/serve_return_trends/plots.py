"""Figures for the serve/return trends (style from :mod:`tennis.plotting`).

Each figure makes one point; panels are ordered WTA, ATP, Challenger; surfaces differ by colour AND
marker/line style; uncertainty is a faint band; 2026 (partial season) is drawn with an open marker.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from tennis.plotting import BLACK, BLUE, GREEN, GREY, ORANGE, VERMILLION, faint_band, light_grid, new_figure, save_figure, wrap

SURFACE_STYLE = {"Hard": (BLUE, "o", "-"), "Clay": (VERMILLION, "s", "--"), "Grass": (GREEN, "^", ":")}
GENDER_STYLE = {"W": (ORANGE, "s", "-"), "M": (BLUE, "o", "-")}
PANEL_NAME = {"W": "WTA", "M": "ATP", "WTA": "WTA", "ATP": "ATP", "Challenger": "Challenger"}


def _series(ax, t: pd.DataFrame, color: str, marker: str, ls: str, label: str, partial_year: int | None,
            scale: float = 1.0, muted: bool = False) -> None:
    """Line + faint CI band; a partial final year is drawn with an open marker and a thin link.
    ``muted`` draws a context series lighter (thinner line, fainter band) so the main series stands out."""
    t = t.sort_values("year")
    full = t[t["year"] != partial_year] if partial_year else t
    faint_band(ax, t["year"], t["lo"] * scale, t["hi"] * scale, color, alpha=0.05 if muted else 0.15)
    ax.plot(full["year"], full["rate"] * scale, color=color, marker=marker, ls=ls, lw=1.1 if muted else 1.8,
            ms=4.5 if muted else 6, alpha=0.55 if muted else 1.0, label=label)
    if partial_year and (t["year"] == partial_year).any():
        last2 = t[t["year"] >= partial_year - 1]
        ax.plot(last2["year"], last2["rate"] * scale, color=color, ls=":", lw=1)
        p = t[t["year"] == partial_year]
        ax.plot(p["year"], p["rate"] * scale, marker=marker, ms=6, mfc="white", mec=color, ls="none")


def _year_ticks(ax, years, partial_year: int | None) -> None:
    """Every second year for short series (the partial final season labelled as such); every fifth
    year for long ones (the partial season is then explained in the caption)."""
    years = list(years)
    if years[-1] - years[0] > 14:
        ax.set_xticks([y for y in years if y % 5 == 0])
        return
    ticks = [y for y in years if y % 2 == 0] + ([partial_year] if partial_year and partial_year % 2 else [])
    ax.set_xticks(ticks, [f"{y}\n(partial)" if y == partial_year else str(y) for y in ticks])


def surface_panels(tab: pd.DataFrame, groups: list[str], title: str, ylabel: str, path: Path,
                   partial_year: int | None = None, group_col: str = "tour", scale: float = 100,
                   ylim: tuple[float, float] | None = None, emphasis: str | None = None) -> Path:
    """One panel per group (tour or gender), one line per surface; values in % (x ``scale``).
    With ``emphasis`` (a surface), the other surfaces are drawn as muted context."""
    spans = [max(int(np.ptp(tab.loc[tab[group_col] == g, "year"])) + 1, 1) for g in groups]
    if max(spans) > 1.5 * min(spans):                   # panels of different length: same width per year
        width = min(17.0, 0.27 * sum(spans) + 1.2)
        fig, axes = new_figure(1, len(groups), figsize=(width, 4.8), sharey=True, gridspec_kw={"width_ratios": spans})
    else:
        fig, axes = new_figure(1, len(groups), figsize=(4.6 * len(groups), 4.6), sharey=True)
    axes = np.atleast_1d(axes)
    for ax, g in zip(axes, groups):
        sub = tab[tab[group_col] == g]
        for s, (c, m, ls) in SURFACE_STYLE.items():
            t = sub[sub["surface"] == s]
            if len(t) >= 2:
                _series(ax, t, c, m, ls, s, partial_year, scale, muted=bool(emphasis) and s != emphasis)
        ax.set_title(PANEL_NAME.get(g, g))
        light_grid(ax)
        _year_ticks(ax, sorted(sub["year"].unique()), partial_year)
        ax.set_xlim(sub["year"].min() - 0.8, sub["year"].max() + 0.8)
        if ylim:
            ax.set_ylim(*ylim)
    axes[0].set_ylabel(ylabel)
    _int_pct_ticks(axes[0])
    # legend from the panel with the most lines (e.g. the Challenger panel has no grass line)
    handles, labels = max((ax.get_legend_handles_labels() for ax in axes), key=lambda hl: len(hl[1]))
    axes[-1].legend(handles, labels, loc="best", frameon=False)
    fig.suptitle(title, fontsize=13)
    return save_figure(fig, path)


def _pct_points():
    from matplotlib.ticker import FuncFormatter
    return FuncFormatter(lambda v, _: f"{v:.0f}%")


def _int_pct_ticks(ax) -> None:
    """Whole-number percentage ticks (avoids rounded duplicates such as 32% / 32%)."""
    from matplotlib.ticker import MaxNLocator
    ax.yaxis.set_major_locator(MaxNLocator(nbins=6, integer=True))
    ax.yaxis.set_major_formatter(_pct_points())


def source_comparison(comp: pd.DataFrame, path: Path) -> Path:
    """Winners per 100 points: every Slam match vs the charted subset (same matches, two sources)."""
    fig, axes = new_figure(1, 2, figsize=(9.5, 4.6), sharey=True)
    bars = [("all_pbp", "All Slam matches\n(point-by-point)", "#BBBBBB", ""),
            ("charted_pbp", "Charted matches\n(point-by-point)", BLUE, ""),
            ("charted_chart", "Charted matches\n(charters' count)", BLUE, "//")]
    for ax, g in zip(axes, ("W", "M")):
        r = comp[comp["gender"] == g].set_index("sample")
        for i, (key, lab, col, hatch) in enumerate(bars):
            v = r.loc[key]
            ax.bar(i, v["rate"] * 100, color=col if col != BLUE else (ORANGE if g == "W" else BLUE),
                   hatch=hatch, edgecolor="white", width=0.65)
            ax.errorbar(i, v["rate"] * 100, yerr=[[(v["rate"] - v["lo"]) * 100], [(v["hi"] - v["rate"]) * 100]],
                        color=BLACK, elinewidth=0.8, capsize=0, alpha=0.6)
            ax.text(i, v["hi"] * 100 + 0.4, f"{v['rate'] * 100:.1f}", ha="center", va="bottom", fontsize=10)
        ax.set_xticks(range(3), [b[1] for b in bars], fontsize=9.5)
        ax.set_title(PANEL_NAME[g])
        light_grid(ax)
    axes[0].set_ylabel("Winners (excl. aces) per 100 points")
    axes[0].set_ylim(0, None)
    fig.suptitle("Charted Slam matches are typical Slam matches;\n"
                 "charters just count slightly fewer winners on the same matches", fontsize=13)
    return save_figure(fig, path)


TOUR_STYLE = {"WTA": (ORANGE, "s", "-"), "ATP": (BLUE, "o", "-"), "Challenger": (VERMILLION, "^", "--")}


def index_panels(idx: pd.DataFrame, title: str, path: Path) -> Path:
    """Like-for-like yearly levels (tournament fixed effects): aces and breaks, one line per tour,
    labelled directly at the line ends."""
    fig, axes = new_figure(1, 2, figsize=(12, 4.8))
    for ax, (m, lab) in zip(axes, (("ace_rate", "Aces per 100 serve points"), ("break_rate", "Breaks per 100 return games"))):
        for t, (c, mk, ls) in TOUR_STYLE.items():
            g = idx[(idx["tour"] == t) & (idx["metric"] == m)].sort_values("year")
            faint_band(ax, g["year"], 100 * g["lo"], 100 * g["hi"], c)
            ax.plot(g["year"], 100 * g["rate"], color=c, marker=mk, ls=ls, lw=1.8, ms=4)
            ax.annotate(t, (g["year"].iloc[-1], 100 * g["rate"].iloc[-1]), xytext=(6, 0), textcoords="offset points",
                        va="center", fontsize=10.5, color=c)
        ax.set_title(lab)
        ax.set_xlim(idx["year"].min() - 1, idx["year"].max() + 5)
        ax.set_xticks(range(1990, int(idx["year"].max()) + 1, 5))
        light_grid(ax)
        _int_pct_ticks(ax)
    fig.suptitle(wrap(title, 95), fontsize=13)
    return save_figure(fig, path)


def coverage_figure(cov: pd.DataFrame, start: dict, path: Path) -> Path:
    """Share of completed matches with serve statistics, per tour and year; seasons before each tour's
    first season used are drawn light."""
    tours = list(start)
    cov = cov[cov["year"] >= 1991]
    fig, axes = new_figure(1, len(tours), figsize=(14, 3.6), sharey=True)
    for ax, t in zip(axes, tours):
        g = cov[cov["tour"] == t]
        ax.bar(g["year"], 100 * g["share"], width=0.8, color=np.where(g["year"] >= start[t], "#7a7a7a", "#d9d9d9"))
        ax.set_title(t)
        ax.set_ylim(0, 112)
        ax.set_yticks([0, 50, 100], ["0%", "50%", "100%"])
        ax.set_xticks(range(1995, int(g["year"].max()) + 1, 10))
        if start[t] > cov["year"].min():
            ax.annotate(f"used from {start[t]}", (start[t] - 0.4, 104), ha="left", va="bottom", fontsize=9.5, color=GREY)
        light_grid(ax)
    axes[0].set_ylabel("Matches with serve stats")
    fig.suptitle("Serve statistics are near-complete from 1991 (ATP), 2009 (WTA) and 2010 (Challenger)", fontsize=13)
    return save_figure(fig, path)


def tour_lines(tab: pd.DataFrame, title: str, ylabel: str, path: Path, partial_year: int | None,
               tours=("WTA", "ATP", "Challenger"), scale: float = 100) -> Path:
    """All surfaces pooled: one line per tour (WTA orange squares, ATP blue circles, Challenger grey)."""
    style = {"WTA": (ORANGE, "s", "-"), "ATP": (BLUE, "o", "--"), "Challenger": (GREY, "^", ":")}
    fig, ax = new_figure(figsize=(8, 4.6))
    for t in tours:
        c, m, ls = style[t]
        sub = tab[tab["tour"] == t]
        _series(ax, sub, c, m, ls, t, partial_year, scale)
        last = sub[sub["year"] == sub["year"].max()]
        ax.annotate(t, (last["year"].iloc[0], last["rate"].iloc[0] * scale), xytext=(8, 0),
                    textcoords="offset points", va="center", color=c, fontsize=11)
    ax.set_ylabel(ylabel)
    _int_pct_ticks(ax)
    _year_ticks(ax, sorted(tab["year"].unique()), partial_year)
    ax.set_xlim(tab["year"].min() - 0.5, tab["year"].max() + 1.6)
    light_grid(ax)
    ax.set_title(title, fontsize=13)
    return save_figure(fig, path)


def group_panels(tab: pd.DataFrame, groups: list[str], lines: dict[str, tuple[str, str, str]], line_col: str,
                 title: str, ylabel: str, path: Path, partial_year: int | None = None, group_col: str = "tour",
                 scale: float = 100) -> Path:
    """One panel per group (WTA, ATP), one line per value of ``line_col`` styled by ``lines``."""
    fig, axes = new_figure(1, len(groups), figsize=(4.8 * len(groups), 4.6), sharey=True)
    axes = np.atleast_1d(axes)
    for ax, g in zip(axes, groups):
        sub = tab[tab[group_col] == g]
        for name, (c, m, ls) in lines.items():
            t = sub[sub[line_col] == name]
            if len(t) >= 2:
                _series(ax, t, c, m, ls, name, partial_year, scale)
        ax.set_title(PANEL_NAME.get(g, g))
        light_grid(ax)
        _year_ticks(ax, sorted(tab["year"].unique()), partial_year)
    axes[0].set_ylabel(ylabel)
    _int_pct_ticks(axes[0])
    axes[-1].legend(loc="best", frameon=False)
    fig.suptitle(title, fontsize=13)
    return save_figure(fig, path)


def charter_figure(tab: pd.DataFrame, path: Path, partial_year: int | None) -> Path:
    """Men's charted non-Slam matches: all vs without the most prolific charter (one panel)."""
    fig, ax = new_figure(figsize=(8, 4.6))
    allm = tab[(tab["gender"] == "M") & (tab["sample"] == "All charted matches")].sort_values("year")
    rest = tab[(tab["gender"] == "M") & (tab["sample"] == "Without the most prolific charter")]
    _series(ax, rest, GREEN, "o", "-", "Without the most prolific charter", partial_year, 100)
    full = allm[allm["year"] != partial_year] if partial_year else allm
    ax.plot(full["year"], full["rate"] * 100, color=GREY, marker="s", ls="--", lw=1.8, ms=6, label="All charted matches")
    for t, c in ((allm, GREY), (rest.sort_values("year"), GREEN)):
        last = t[t["year"] == t["year"].max() - (1 if partial_year else 0)]
        ax.annotate(t["sample"].iloc[0].replace("Without the most prolific charter", "without one charter")
                    .replace("All charted matches", "all charted"), (last["year"].iloc[0], last["rate"].iloc[0] * 100),
                    xytext=(8, 0), textcoords="offset points", va="center", color=c, fontsize=10.5)
    ax.set_ylabel("Winners per 100 points (ATP, outside the Slams)")
    _int_pct_ticks(ax)
    _year_ticks(ax, sorted(tab["year"].unique()), partial_year)
    ax.set_xlim(tab["year"].min() - 0.5, tab["year"].max() + 2.2)
    light_grid(ax)
    ax.set_title("The jump in charted men's winners comes from one charter's matches", fontsize=13)
    return save_figure(fig, path)
