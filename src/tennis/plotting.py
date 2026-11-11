"""House plotting style for all analyses (the user's figure guidelines).

* Okabe-Ito colour-blind-safe palette; men / ATP = #0072B2 (blue), women / WTA = #E69F00 (orange)
  in every figure.  Series must also differ by marker and/or line style (never colour alone).
* Constrained layout (``new_figure``) and ``save_figure`` with ``bbox_inches="tight"`` at 150 dpi, so
  no text is clipped.  Ticks >= 10 pt, labels >= 11 pt.

Plots are for the READER (user rule):
* One point per figure; the title states the takeaway in plain words ("Aces are rising on the WTA
  tour"), not the pipeline ("Aces/svpt by year, tour-level incl. Slams").
* No internal conventions or process notes in figures ("WTA left", "(dashed)", sample definitions,
  caveats): those belong in the README caption.  Panel titles "WTA" / "ATP" are enough.
* Uncertainty must not dominate: use :func:`faint_band` / :data:`FAINT_ERR` (alpha <= 0.15, thin
  lines); drop error crosses on labelled scatter plots and give the typical CI in the caption.
  Keep CIs (lightly) only when they are the message.
* Little clutter: only needed gridlines; label reference lines directly with
  :func:`label_hline` / :func:`label_vline` instead of a legend; no duplicated legends; few ticks with
  sensible units (:func:`percent_axis`).
"""
from __future__ import annotations

import os
import textwrap
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

# Okabe-Ito
BLUE, ORANGE, VERMILLION, GREEN = "#0072B2", "#E69F00", "#D55E00", "#009E73"
SKY, PURPLE, YELLOW, BLACK = "#56B4E9", "#CC79A7", "#F0E442", "#000000"
OKABE_ITO = {"blue": BLUE, "orange": ORANGE, "vermillion": VERMILLION, "bluish green": GREEN,
             "sky blue": SKY, "reddish purple": PURPLE, "yellow": YELLOW, "black": BLACK}
MEN, WOMEN = BLUE, ORANGE
GREY, LIGHT_GREY = "#666666", "#BBBBBB"
BAND_ALPHA = 0.2          # bands that ARE the message
FAINT_ALPHA = 0.15        # uncertainty that is context, not the message
# light error bars: ``ax.errorbar(..., **FAINT_ERR)``
FAINT_ERR = {"elinewidth": 0.8, "capsize": 0, "alpha": 0.6}
DPI = 150

HOUSE_RC = {
    "figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white",
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": "#e4e3df",
    "grid.linewidth": 0.8, "axes.axisbelow": True,
    "font.size": 11, "axes.labelsize": 12, "axes.titlesize": 12, "xtick.labelsize": 11, "ytick.labelsize": 11,
    "legend.fontsize": 10.5, "legend.frameon": False, "figure.dpi": 100, "savefig.dpi": DPI,
}


def apply_house_style() -> None:
    """Set the shared matplotlib rcParams (idempotent)."""
    plt.rcParams.update(HOUSE_RC)


apply_house_style()


def new_figure(*args, **kwargs):
    """``plt.subplots`` with constrained layout by default."""
    kwargs.setdefault("layout", "constrained")
    return plt.subplots(*args, **kwargs)


def faint_band(ax, x, lo, hi, color: str, alpha: float = FAINT_ALPHA, **kw):
    """A faint uncertainty band (alpha <= 0.15, no edge) behind a line."""
    return ax.fill_between(x, lo, hi, color=color, alpha=alpha, lw=0, zorder=1, **kw)


def label_hline(ax, y: float, text: str, x: float = 1.0, ha: str = "right", color: str = GREY, ls: str = "--", **kw):
    """Horizontal reference line labelled directly ("coin flip", "tour average") instead of via a legend.
    ``x`` is in axes coordinates (0 = left, 1 = right)."""
    ax.axhline(y, color=color, ls=ls, lw=1, zorder=1, **kw)
    return ax.annotate(text, xy=(x, y), xycoords=("axes fraction", "data"), xytext=(-3 if ha == "right" else 3, 3),
                       textcoords="offset points", ha=ha, va="bottom", fontsize=10, color=color)


def label_vline(ax, x: float, text: str, y: float = 1.0, color: str = GREY, ls: str = ":", **kw):
    """Vertical reference line (e.g. a rule change) labelled directly at the top of the axes."""
    ax.axvline(x, color=color, ls=ls, lw=1, zorder=1, **kw)
    return ax.annotate(text, xy=(x, y), xycoords=("data", "axes fraction"), xytext=(3, -3),
                       textcoords="offset points", ha="left", va="top", fontsize=10, color=color)


def percent_axis(ax, axis: str = "y", decimals: int = 0, xmax: float = 1.0, nbins: int = 5) -> None:
    """Format an axis holding proportions as percentages with few ticks."""
    from matplotlib.ticker import MaxNLocator, PercentFormatter
    a = ax.yaxis if axis == "y" else ax.xaxis
    a.set_major_formatter(PercentFormatter(xmax, decimals=decimals))
    a.set_major_locator(MaxNLocator(nbins=nbins))


def light_grid(ax, axis: str = "y") -> None:
    """Keep only the gridlines that help reading values (default: horizontal)."""
    ax.grid(False)
    ax.grid(True, axis=axis, color="#ececec", lw=0.8)


def wrap(text: str, width: int = 70) -> str:
    """Wrap a long title to lines of at most ``width`` characters."""
    return "\n".join(textwrap.wrap(text, width))


def save_figure(fig, path: Path, dpi: int = DPI, retries: int = 5) -> Path:
    """Save a PNG (tight bounding box, no software stamp so bytes are reproducible) and close it.

    Writes to a temporary file and atomically replaces the target, retrying: overwriting files in
    place on a Windows-mounted drive (WSL /mnt/c) intermittently fails with EINVAL.
    """
    path = Path(path)
    tmp = path.with_name(path.stem + ".tmp.png")
    try:
        for attempt in range(retries):
            try:
                fig.savefig(tmp, bbox_inches="tight", dpi=dpi, metadata={"Software": None})
                os.replace(tmp, path)
                return path
            except OSError:
                if attempt == retries - 1:
                    raise
                time.sleep(1.0 + attempt)
    finally:
        plt.close(fig)
    return path
