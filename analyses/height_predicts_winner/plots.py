"""Figures for "can height predict the winner?" (house style and reader rules from tennis.plotting)."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from tennis.plotting import (BLACK, BLUE, GREEN, GREY, LIGHT_GREY, MEN, ORANGE, VERMILLION, WOMEN, FAINT_ERR,
                             label_hline, light_grid, new_figure, save_figure)

TOUR_STYLE = {"WTA": (WOMEN, "s"), "ATP": (MEN, "o")}


def _pct(ax, lo: float, hi: float, step: int = 5) -> None:
    from matplotlib.ticker import FuncFormatter, MultipleLocator
    ax.set_ylim(lo, hi)
    ax.yaxis.set_major_locator(MultipleLocator(step / 100))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v * 100:.0f}%"))


def taller_player_curve(binned: pd.DataFrame, curve: pd.DataFrame, path: Path) -> Path:
    """Win rate of the taller player by height difference, with the fitted height-only logistic curve."""
    fig, axes = new_figure(1, 2, figsize=(10, 4.6), sharey=True)
    for ax, tour in zip(axes, ("WTA", "ATP")):
        c, m = TOUR_STYLE[tour]
        b = binned[binned["tour"] == tour]
        cv = curve[curve["tour"] == tour]
        ax.plot(cv["diff_cm"], cv["p_taller"], color=c, lw=2)
        ax.errorbar(b["mid_cm"], b["p"], yerr=[b["p"] - b["lo"], b["hi"] - b["p"]], fmt=m, color=c, ms=7,
                    mec="white", **FAINT_ERR)
        label_hline(ax, 0.5, "coin flip", x=0.98)
        ax.set_title(tour)
        ax.set_xlabel("Height difference (cm)")
        light_grid(ax)
        _pct(ax, 0.45, 0.70)
    axes[0].set_ylabel("Taller player wins")
    fig.suptitle("The taller player wins more often, and more so the bigger the gap", fontsize=13)
    return save_figure(fig, path)


def model_comparison(tab: pd.DataFrame, path: Path) -> Path:
    """Test-period accuracy of the four models, WTA and ATP."""
    order = ["Coin flip", "Height only", "Ranking only", "Ranking + height"]
    colours = [LIGHT_GREY, GREEN, BLUE, BLACK]
    hatches = ["", "//", "", "xx"]
    fig, axes = new_figure(1, 2, figsize=(10, 4.6), sharey=True)
    for ax, tour in zip(axes, ("WTA", "ATP")):
        t = tab[tab["tour"] == tour].set_index("model").loc[order]
        for i, (mname, col, h) in enumerate(zip(order, colours, hatches)):
            v = t.loc[mname, "accuracy"]
            ax.bar(i, v, color=col, hatch=h, edgecolor="white", width=0.65)
            ax.text(i, v + 0.005, f"{v * 100:.1f}%", ha="center", va="bottom", fontsize=10.5)
        ax.set_xticks(range(4), ["Coin\nflip", "Height\nonly", "Ranking\nonly", "Ranking\n+ height"])
        ax.set_title(tour)
        light_grid(ax)
        _pct(ax, 0.40, 0.70, step=10)
    axes[0].set_ylabel("Winner predicted correctly (2023-26)")
    fig.suptitle("Height alone beats a coin flip, but adds almost nothing once ranking is known", fontsize=13)
    return save_figure(fig, path)


def by_surface(surf: pd.DataFrame, path: Path) -> Path:
    """Taller player's win rate by surface (all years), WTA and ATP."""
    order = ["Hard", "Clay", "Grass"]
    fig, axes = new_figure(1, 2, figsize=(9, 4.4), sharey=True)
    for ax, tour in zip(axes, ("WTA", "ATP")):
        c, m = TOUR_STYLE[tour]
        t = surf[surf["tour"] == tour].set_index("surface").loc[order]
        x = np.arange(3)
        ax.errorbar(x, t["taller_wins"], yerr=[t["taller_wins"] - t["lo"], t["hi"] - t["taller_wins"]], fmt=m,
                    color=c, ms=9, mec="white", **FAINT_ERR)
        for xi, v in zip(x, t["taller_wins"]):
            ax.annotate(f"{v * 100:.1f}%", (xi, v), xytext=(10, 0), textcoords="offset points", va="center", fontsize=10.5)
        label_hline(ax, 0.5, "coin flip", x=0.98)
        ax.set_xticks(x, order)
        ax.set_xlim(-0.5, 2.7)
        ax.set_title(tour)
        light_grid(ax)
        _pct(ax, 0.48, 0.60, step=2)
    axes[0].set_ylabel("Taller player wins")
    fig.suptitle("On the ATP, height matters most on grass and least on clay", fontsize=13)
    return save_figure(fig, path)


def coverage(cov: pd.DataFrame, path: Path) -> Path:
    """Share of matches with both players' heights recorded, by year."""
    fig, ax = new_figure(figsize=(8, 4.2))
    for tour, ls in (("WTA", "-"), ("ATP", "--")):
        c, m = TOUR_STYLE[tour]
        t = cov[cov["tour"] == tour].sort_values("year")
        ax.plot(t["year"], t["both_heights"], color=c, marker=m, ls=ls, lw=2)
        ax.annotate(tour, (t["year"].iloc[-1], t["both_heights"].iloc[-1]), xytext=(8, 0), textcoords="offset points",
                    va="center", color=c, fontsize=11)
    ax.set_xlim(cov["year"].min() - 0.5, cov["year"].max() + 1.2)
    light_grid(ax)
    _pct(ax, 0.0, 1.05, step=20)
    ax.set_ylabel("Matches with both heights")
    ax.set_title("WTA heights are often missing for recent seasons", fontsize=13)
    return save_figure(fig, path)
