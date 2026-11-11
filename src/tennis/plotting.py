"""House plotting style for all analyses (the user's figure guidelines).

* Okabe-Ito colour-blind-safe palette; men / ATP = #0072B2 (blue), women / WTA = #E69F00 (orange)
  in every figure.  Series must also differ by marker and/or line style (never colour alone).
* Constrained layout (``new_figure``) and ``save_figure`` with ``bbox_inches="tight"`` at 150 dpi, so
  no text is clipped.  Ticks >= 10 pt, labels >= 11 pt.  Shaded bands use alpha 0.2.
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
BAND_ALPHA = 0.2
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
