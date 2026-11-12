"""Figures for the top-10 profiles (WTA panels left / top; markers differ by tour)."""
from __future__ import annotations

import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import numpy as np
import pandas as pd

from tennis.plotting import BLUE, GREY, LIGHT_GREY, MEN, ORANGE, VERMILLION, WOMEN, new_figure

TOURS = ["WTA", "ATP"]
COLOUR = {"WTA": WOMEN, "ATP": MEN}
MARKER = {"WTA": "o", "ATP": "s"}
SURF_MARKER = {"Hard": "o", "Clay": "^", "Grass": "D"}


def short(name: str) -> str:
    """'Felix Auger-Aliassime' -> 'F. Auger-Aliassime' (keeps labels compact)."""
    p = name.split(" ", 1)
    return f"{p[0][0]}. {p[1]}" if len(p) == 2 else name


def place_labels(ax, xs, ys, labels, fontsize: float = 9.5, extra_boxes=None) -> None:
    """Greedy label placement: try eight directions at two distances, take the first position whose box
    overlaps no earlier label, no data point and stays inside the axes; draw a leader line when moved far.
    Call after the axis limits are final."""
    fig = ax.figure
    fig.canvas.draw()
    rend = fig.canvas.get_renderer()
    pts = ax.transData.transform(np.column_stack([xs, ys]))
    axbox = ax.get_window_extent(rend)
    placed: list = []
    r = 9 * fig.dpi / 72                           # marker clearance in pixels
    point_boxes = [(x - r, y - r, x + r, y + r) for x, y in pts]
    dirs = [(1, 0, "left", "center"), (-1, 0, "right", "center"), (0, 1, "center", "bottom"), (0, -1, "center", "top"),
            (1, 1, "left", "bottom"), (-1, 1, "right", "bottom"), (1, -1, "left", "top"), (-1, -1, "right", "top")]
    order = np.argsort(-pts[:, 1])                  # top to bottom
    for i in order:
        best = None
        for dist in (7, 16, 28, 42):
            for dx, dy, ha, va in dirs:
                t = ax.annotate(labels[i], (xs[i], ys[i]), xytext=(dx * dist, dy * dist), textcoords="offset points",
                                ha=ha, va=va, fontsize=fontsize, zorder=5,
                                arrowprops=dict(arrowstyle="-", color=GREY, lw=0.6, shrinkA=0, shrinkB=3) if dist > 10 else None)
                bb = t.get_window_extent(rend)
                box = (bb.x0 - 2, bb.y0 - 2, bb.x1 + 2, bb.y1 + 2)
                inside = box[0] >= axbox.x0 and box[2] <= axbox.x1 and box[1] >= axbox.y0 and box[3] <= axbox.y1
                clash = sum(_ov(box, q) for q in placed) + sum(_ov(box, q) for j, q in enumerate(point_boxes) if j != i)
                clash += sum(_ov(box, q) for q in (extra_boxes or []))
                score = clash + (0 if inside else 1e9)
                if best is None or score < best[0]:
                    if best is not None:
                        best[1].remove()
                    best = (score, t, box)
                else:
                    t.remove()
                if score == 0:
                    break
            if best[0] == 0:
                break
        placed.append(best[2])


def _line_boxes(ax, x: float, y: float, half: float = 3.0) -> list:
    """Thin display-space boxes around a vertical line at ``x`` and a horizontal line at ``y`` (pixels)."""
    ab = ax.get_window_extent(ax.figure.canvas.get_renderer())
    px, py = ax.transData.transform((x, y))
    return [(px - half, ab.y0, px + half, ab.y1), (ab.x0, py - half, ab.x1, py + half)]


def _ov(a, b) -> float:
    """Overlap area of two (x0, y0, x1, y1) boxes."""
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    return w * h if (w > 0 and h > 0) else 0.0


def _lims(lo, hi, pad=0.18):
    lo, hi = np.nanmin(lo), np.nanmax(hi)
    d = (hi - lo) * pad
    return lo - d, hi + d


def scatter_two(frames: dict[str, pd.DataFrame], xcol: str, ycol: str, title: str, xlabel: str, ylabel: str,
                ref: dict[str, tuple[float, float]], ref_text: tuple[str, str], path, scale: float = 100.0,
                hollow_col: str | None = None, label_col: str = "label", pct: bool = True,
                hollow_note: str = "") -> None:
    """Two-panel scatter (WTA, ATP), no error bars, tour-reference lines labelled directly, repelled name labels."""
    from matplotlib.ticker import PercentFormatter
    from tennis.plotting import save_figure
    fig, axes = new_figure(1, 2, figsize=(14, 6.6))
    for ax, tour in zip(axes, TOURS):
        d = frames[tour]
        x, y = d[xcol].to_numpy() * scale, d[ycol].to_numpy() * scale
        hollow = d[hollow_col].to_numpy() if hollow_col else np.zeros(len(d), bool)
        ax.scatter(x[~hollow], y[~hollow], s=80, marker=MARKER[tour], color=COLOUR[tour], edgecolor="black", linewidth=0.8, zorder=3)
        if hollow.any():
            ax.scatter(x[hollow], y[hollow], s=80, marker=MARKER[tour], facecolor="white", edgecolor=COLOUR[tour], linewidth=2.0, zorder=3)
        rx, ry = ref[tour][0] * scale, ref[tour][1] * scale
        ax.axvline(rx, color=GREY, ls="--", lw=1.1, zorder=0)
        ax.axhline(ry, color=GREY, ls="--", lw=1.1, zorder=0)
        ax.set_xlim(*_lims(np.r_[x, rx], np.r_[x, rx], 0.2))
        ax.set_ylim(*_lims(np.r_[y, ry], np.r_[y, ry], 0.2))
        t1 = ax.text(rx, 0.015, " " + ref_text[0], transform=ax.get_xaxis_transform(), rotation=90, ha="left", va="bottom",
                     color=GREY, fontsize=9.5)
        t2 = ax.text(0.99, ry, ref_text[1] + " ", transform=ax.get_yaxis_transform(), ha="right", va="bottom", color=GREY, fontsize=9.5)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.set_title(tour, fontweight="bold", loc="left")
        if pct:
            ax.xaxis.set_major_locator(MaxNLocator(integer=True, steps=[1, 2, 5, 10]))
            ax.yaxis.set_major_locator(MaxNLocator(integer=True, steps=[1, 2, 5, 10]))
            ax.xaxis.set_major_formatter(PercentFormatter(decimals=0))
            ax.yaxis.set_major_formatter(PercentFormatter(decimals=0))
        ax.figure.canvas.draw()
        rend = ax.figure.canvas.get_renderer()
        boxes = [(bb.x0, bb.y0, bb.x1, bb.y1) for bb in (t1.get_window_extent(rend), t2.get_window_extent(rend))]
        boxes += _line_boxes(ax, rx, ry)           # keep labels off the reference lines
        place_labels(ax, x, y, d[label_col].tolist(), extra_boxes=boxes)
    if hollow_note:
        h = plt.Line2D([], [], marker="o", ls="", mfc="white", mec=GREY, mew=2.0, ms=9)
        fig.legend([h], [hollow_note], loc="outside lower center", fontsize=10.5)
    fig.suptitle(title, fontsize=14, fontweight="bold")
    save_figure(fig, path)


def dotwhisker_grid(rows: list[list[tuple[pd.DataFrame, str, str, float | None, str]]], title: str, xlabel_row: list[str],
                    path, xlim_pad: float = 1.0, pct_axis: bool = False, zero: float = 0.0, zero_label: str = "own baseline",
                    avg_label: str = "tour average") -> None:
    """Grid of sorted dot-and-whisker panels.  ``rows[r][c]`` = (frame, tour, col prefix, tour-average gap, panel title);
    frame needs ``label`` and ``<prefix>``, ``<prefix>_lo``, ``<prefix>_hi``.  WTA is always the left column."""
    from matplotlib.ticker import PercentFormatter
    from tennis.plotting import save_figure
    nr, nc = len(rows), len(rows[0])
    fig, axes = new_figure(nr, nc, figsize=(7.4 * nc, 4.6 * nr), squeeze=False)
    for r in range(nr):
        # common x range per row so the two tours are comparable
        lo = min(np.nanmin(f[p + "_lo"]) for f, _, p, _, _ in rows[r])
        hi = max(np.nanmax(f[p + "_hi"]) for f, _, p, _, _ in rows[r])
        avgs = [a for *_, a, _ in rows[r] if a is not None] + [zero]
        lo, hi = min(lo, min(avgs)) - xlim_pad, max(hi, max(avgs)) + xlim_pad
        for c in range(nc):
            f, tour, p, avg, ttl = rows[r][c]
            ax = axes[r][c]
            f = f.sort_values(p).reset_index(drop=True)
            y = np.arange(len(f))
            ax.errorbar(f[p], y, xerr=[f[p] - f[p + "_lo"], f[p + "_hi"] - f[p]], fmt="none", ecolor=GREY, elinewidth=1.4,
                        alpha=0.55, capsize=0, zorder=2)
            ax.scatter(f[p], y, marker=MARKER[tour], color=COLOUR[tour], edgecolor="black", linewidth=0.8, s=75, zorder=3)
            ax.axvline(zero, color=GREY, lw=1.0, ls="--", zorder=0)
            top = len(f) - 0.15
            if avg is not None:
                ax.axvline(avg, color=GREY, lw=1.3, ls=":", zorder=0)
                lo_first = avg < zero
                ax.text(avg, top, avg_label + " ", ha="right" if lo_first else "left", va="bottom", fontsize=9.5, color=GREY)
                ax.text(zero, top, " " + zero_label if lo_first else zero_label + " ", ha="left" if lo_first else "right",
                        va="bottom", fontsize=9.5, color=GREY)
            else:
                ax.text(zero, top, " " + zero_label, ha="left", va="bottom", fontsize=9.5, color=GREY)
            ax.set_ylim(-0.6, len(f) + 0.5)
            ax.set_yticks(y)
            ax.set_yticklabels(f.label)
            if pct_axis:
                ax.xaxis.set_major_locator(MaxNLocator(nbins=6, integer=True, steps=[1, 2, 5, 10]))
                ax.xaxis.set_major_formatter(PercentFormatter(decimals=0))
            ax.set_xlim(lo, hi)
            ax.xaxis.set_major_locator(MaxNLocator(integer=True, steps=[1, 2, 5, 10]))
            ax.set_title(ttl, loc="left", fontweight="bold")
            ax.set_xlabel(xlabel_row[r])
            ax.grid(axis="y", visible=False)
    fig.suptitle(title, fontsize=14, fontweight="bold")
    save_figure(fig, path)


def surface_scatter(tables: dict[str, pd.DataFrame], surfaces: list[str], ref: dict[tuple[str, str], tuple[float, float]], path) -> None:
    """Hold vs break by surface: rows WTA then ATP, columns Hard / Clay / Grass; point labels repelled."""
    from matplotlib.ticker import PercentFormatter
    from tennis.plotting import save_figure
    fig, axes = new_figure(2, len(surfaces), figsize=(6.0 * len(surfaces), 11.5), squeeze=False)
    for r, tour in enumerate(TOURS):
        for c, surf in enumerate(surfaces):
            ax = axes[r][c]
            d = tables[tour]
            d = d[d.surface == surf].reset_index(drop=True)
            x, y = d.hold.to_numpy() * 100, d.brk.to_numpy() * 100
            rx, ry = ref[(tour, surf)]
            ax.axvline(rx * 100, color=GREY, ls="--", lw=1.1, zorder=0)
            ax.axhline(ry * 100, color=GREY, ls="--", lw=1.1, zorder=0)
            ax.scatter(x, y, s=80, marker=SURF_MARKER[surf], color=COLOUR[tour], edgecolor="black",
                       linewidth=0.8, zorder=3)
            ax.set_xlim(*_lims(np.r_[x, rx * 100], np.r_[x, rx * 100], 0.22))
            ax.set_ylim(*_lims(np.r_[y, ry * 100], np.r_[y, ry * 100], 0.22))
            ax.set_title(f"{tour}: {surf}", loc="left", fontweight="bold")
            ax.set_xlabel("Hold % (service games held)")
            ax.set_ylabel("Break % (return games won)")
            t1 = ax.text(rx * 100, 0.015, " tour average", transform=ax.get_xaxis_transform(), rotation=90, ha="left", va="bottom", color=GREY, fontsize=9)
            t2 = ax.text(0.01, ry * 100, " tour average", transform=ax.get_yaxis_transform(), ha="left", va="bottom", color=GREY, fontsize=9)
            ax.xaxis.set_major_locator(MaxNLocator(integer=True, steps=[1, 2, 5, 10]))
            ax.yaxis.set_major_locator(MaxNLocator(integer=True, steps=[1, 2, 5, 10]))
            ax.xaxis.set_major_formatter(PercentFormatter(decimals=0))
            ax.yaxis.set_major_formatter(PercentFormatter(decimals=0))
            ax.figure.canvas.draw()
            rend = ax.figure.canvas.get_renderer()
            boxes = [(bb.x0, bb.y0, bb.x1, bb.y1) for bb in (t1.get_window_extent(rend), t2.get_window_extent(rend))]
            place_labels(ax, x, y, [f"{short(n)} ({k})" for n, k in zip(d.name, d.n_matches)], fontsize=9, extra_boxes=boxes)
    fig.suptitle("Hold and break change a lot from surface to surface, and clay and grass rest on few matches ",
                 fontsize=14, fontweight="bold")
    save_figure(fig, path)


def keypoints_figure(frames: dict[str, pd.DataFrame], ref: dict[str, dict], min_charted: int, path, title: str) -> None:
    """Charted key points: serve (top) and return (bottom), WTA left.  Three markers per player (break point /
    game point / deuce) giving the win rate in that situation minus the player's overall rate; no whiskers."""
    from tennis.plotting import save_figure
    spec = {0: [("BP", "break points", "o"), ("GP", "game points", "^"), ("Deuce", "deuce points", "D")],
            1: [("BPO", "break points", "o"), ("GPF", "game points", "^"), ("DeuceR", "deuce points", "D")]}
    fig, axes = new_figure(2, 2, figsize=(14, 11.5), squeeze=False)
    for r in range(2):
        vals = [frames[t][f"{k}_gap"] for t in TOURS for k, *_ in spec[r]]
        lo, hi = min(v.min() for v in vals) - 3, max(v.max() for v in vals) + 3
        for c, tour in enumerate(TOURS):
            ax = axes[r][c]
            f = frames[tour].sort_values(f"{spec[r][0][0]}_gap").reset_index(drop=True)
            y = np.arange(len(f))
            for j, (key, lab, mk) in enumerate(spec[r]):
                ax.scatter(f[f"{key}_gap"], y + (j - 1) * 0.24, marker=mk, s=55, color=COLOUR[tour], edgecolor="black", linewidth=0.7, zorder=3)
            ax.axvline(0, color=GREY, lw=1.0, ls="--", zorder=0)
            ax.text(0, len(f) + 0.15, " own average", ha="left", va="bottom", fontsize=9.5, color=GREY)
            ax.set_yticks(y)
            ax.set_yticklabels([f"{l} ({n}){'*' if few else ''}" for l, n, few in zip(f.label, f.n_matches, f.few)])
            ax.set_xlim(lo, hi)
            ax.set_ylim(-0.7, len(f) + 0.7)
            ax.grid(axis="y", visible=False)
            ax.set_title(f"{tour}: {'serving' if r == 0 else 'returning'}", loc="left", fontweight="bold")
            ax.set_xlabel("Points won, relative to own overall rate (percentage points)")
    h = [plt.Line2D([], [], marker=mk, ls="", mfc="white", mec="black", ms=8) for _, _, mk in spec[0]]
    fig.legend(h, [lab for _, lab, _ in spec[0]], loc="outside lower center", ncol=3, fontsize=10.5)
    fig.suptitle(title, fontsize=14, fontweight="bold")
    save_figure(fig, path)


def regulars_scatter(regs: dict, path) -> None:
    """Hold vs break of every regular player (grey) with the top 10 highlighted: selection explains the top-10 pattern."""
    from matplotlib.ticker import PercentFormatter
    from tennis.plotting import save_figure
    fig, axes = new_figure(1, 2, figsize=(14, 6.2))
    for ax, tour in zip(axes, TOURS):
        tab, top_ids = regs[tour]
        top = tab.id.isin(top_ids)
        ax.scatter(tab.hold[~top] * 100, tab.brk[~top] * 100, s=28, marker=MARKER[tour], facecolor="white", edgecolor=GREY, linewidth=0.9, zorder=2)
        ax.scatter(tab.hold[top] * 100, tab.brk[top] * 100, s=80, marker=MARKER[tour], color=COLOUR[tour], edgecolor="black", linewidth=0.8, zorder=3)
        ax.set_xlabel("Service games held")
        ax.set_ylabel("Return games won (breaks)")
        ax.set_title(tour, loc="left", fontweight="bold")
        ax.xaxis.set_major_formatter(PercentFormatter(decimals=0))
        ax.yaxis.set_major_formatter(PercentFormatter(decimals=0))
    h = [plt.Line2D([], [], marker="o", ls="", mfc=GREY, mec="black", ms=9), plt.Line2D([], [], marker="o", ls="", mfc="white", mec=GREY, ms=7)]
    fig.legend(h, ["current top 10", "other regular players (30+ matches)"], loc="outside lower center", ncol=2, fontsize=10.5)
    fig.suptitle("Across all regular players, serving and returning are only weakly related", fontsize=14, fontweight="bold")
    save_figure(fig, path)
