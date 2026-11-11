"""Static PNG figures (matplotlib, Agg backend).

House style from :mod:`tennis.plotting` (Okabe-Ito, men blue / women orange, constrained layout,
tight bbox at 150 dpi). Series also differ by marker shape / hatch, never by colour alone.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker
import numpy as np
import pandas as pd

from tennis.paths import SLAM_LABEL, SLAM_ORDER
from tennis.plotting import BLACK, GREEN, LIGHT_GREY, PURPLE, SKY, VERMILLION, new_figure, save_figure
from tennis.plotting import MEN, WOMEN  # noqa: F401  (house colours: men blue, women orange)

SET1, LATER = GREEN, PURPLE                   # set 1 = bluish green (circles), sets 2+ = reddish purple (squares)
VERM, LIGHT = VERMILLION, LIGHT_GREY
GREY, INK2 = "#666666", "#333333"
MK = {"men": "o", "women": "s", "set 1": "o", "sets 2+": "s"}
PCT = matplotlib.ticker.PercentFormatter(1.0, decimals=0)



def save_fig(fig, out: Path) -> None:
    """House ``save_figure`` (tight bbox, 150 dpi, reproducible bytes)."""
    save_figure(fig, out)


def _ref(ax, horizontal: bool = True) -> None:
    (ax.axhline if horizontal else ax.axvline)(0.5, color=GREY, lw=1, ls="--", zorder=1)


def _err(ax, x, p, lo, hi, color, label=None, marker="o", horizontal=False, ms=8):
    kw = dict(fmt=marker, color=color, ms=ms, lw=2, capsize=0, label=label, zorder=3, mec="white", mew=0.8)
    if horizontal:
        ax.errorbar(p, x, xerr=[p - lo, hi - p], **kw)
    else:
        ax.errorbar(x, p, yerr=[p - lo, hi - p], **kw)


def fig_raw_vs_adjusted(models: pd.DataFrame, out: Path) -> None:
    """Lead figure: raw vs strength-adjusted P(first server wins), set 1 and sets 2+."""
    fig, ax = new_figure(figsize=(10, 5.6))
    order_m = ["raw", "pre-match rank", "rank + previous set result", "rank + in-match serve form (other sets)"]
    lab = ["Raw\n(what happens\non court)", "Equal\nranking", "Equal ranking and\nprevious-set result",
           "Equal ranking and\nserve form on the day"]
    m = models[models.gender == "All"]
    for off, sg, c in ((-0.13, "set 1", SET1), (0.13, "sets 2+", LATER)):
        for j, nm in enumerate(order_m):
            r = m[(m.set_group == sg) & (m.model == nm)]
            if not len(r):
                continue
            r = r.iloc[0]
            _err(ax, np.array([j + off]), np.array([r.p_adj]), np.array([r.lo]), np.array([r.hi]), c,
                 marker=MK[sg], label=("Set 1" if sg == "set 1" else "Sets 2+") if j == 0 else None)
            ax.annotate(f"{r.p_adj:.1%}", (j + off, r.hi), xytext=(0, 5), textcoords="offset points", ha="center",
                        fontsize=10, color=INK2)
    _ref(ax)
    ax.text(0.5, 0.5007, "50% = no advantage", ha="center", va="bottom", fontsize=10, color=GREY)
    ax.set_xticks(range(len(order_m)), lab)
    ax.set_xlim(-0.5, len(order_m) - 0.5)
    ax.set_ylabel("P(first server of the set wins it)")
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    ax.set_title("Serving first barely matters once player strength is held equal")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=2)
    save_fig(fig, out)
    plt.close(fig)


def fig_by_set_number(bs: pd.DataFrame, out: Path) -> None:
    """P(first server wins) by set number, men and women, with 95% CIs."""
    fig, ax = new_figure(figsize=(9, 5.2))
    for off, (g, c) in zip((-0.12, 0.12), (("Men", MEN), ("Women", WOMEN))):
        d = bs[bs.gender == g]
        _err(ax, d.set_no + off, d.p.values, d.lo.values, d.hi.values, c, label=g, marker=MK[g.lower()])
    _ref(ax)
    ticks = []
    for k in range(1, 6):
        nm = bs[(bs.gender == "Men") & (bs.set_no == k)].n_sets
        nw = bs[(bs.gender == "Women") & (bs.set_no == k)].n_sets
        t = f"Set {k}\nmen n={int(nm.iloc[0]):,}" if len(nm) else f"Set {k}"
        ticks.append(t + (f"\nwomen n={int(nw.iloc[0]):,}" if len(nw) else ""))
    ax.set_xticks(range(1, 6), ticks)
    ax.yaxis.set_major_locator(matplotlib.ticker.MultipleLocator(0.05))
    ax.set_ylabel("P(first server of the set wins it)")
    ax.yaxis.set_major_formatter(PCT)
    ax.set_ylim(0.38, 0.6)
    ax.set_title("Raw win rate of the set's first server, by set number (95% CIs)")
    ax.legend(loc="upper right", title="Women play best of 3", title_fontsize=9)
    save_fig(fig, out)
    plt.close(fig)


def fig_gender_slam(tab: pd.DataFrame, out: Path) -> None:
    """Forest plot: set 1 and sets 2+ by gender x Slam."""
    fig, axes = new_figure(1, 2, figsize=(12, 5.6), sharey=True)
    labels = []
    for gi, g in enumerate(("M", "W")):
        for si, s in enumerate(SLAM_ORDER):
            labels.append((gi * 5 + si, g, s, f"{'Men' if g == 'M' else 'Women'}, {SLAM_LABEL[s]}"))
    for ax, sg in zip(axes, ("set 1", "sets 2+")):
        d = tab[tab.set_group == sg]
        for y, g, s, _ in labels:
            r = d[(d.gender == g) & (d.slam == s)]
            if len(r):
                r = r.iloc[0]
                _err(ax, np.array([y]), np.array([r.p]), np.array([r.lo]), np.array([r.hi]),
                     MEN if g == "M" else WOMEN, marker="o" if g == "M" else "s", horizontal=True)
                ax.annotate(f"{r.p:.1%}  (n={int(r.n_sets):,})", (r.hi, y), xytext=(6, 0), textcoords="offset points",
                            va="center", fontsize=9.5, color=INK2)
        _ref(ax, horizontal=False)
        ax.set_title("Set 1" if sg == "set 1" else "Sets 2+")
        ax.set_xlabel("P(first server wins the set), 95% CI")
        ax.xaxis.set_major_formatter(PCT)
        ax.set_xlim(0.40, 0.65)
        ax.grid(axis="y", visible=False)
    axes[0].set_yticks([y for y, *_ in labels], [lab for *_, lab in labels])
    axes[0].invert_yaxis()
    fig.suptitle("Raw win rate of the set's first server by gender and Slam: no Slam stands out",
                 fontweight="bold", fontsize=12)
    save_fig(fig, out)
    plt.close(fig)


def fig_how_sets_end(ends: pd.DataFrame, out: Path) -> None:
    """Why the first server of a later set is usually the previous set's loser."""
    d = ends.set_index("ending")
    rows = [("winner held serve to close", "Winner HELD serve in the last game", "next set opened by the set's LOSER", VERM, ""),
            ("winner broke serve to close", "Winner BROKE serve in the last game", "next set opened by the set's WINNER", SKY, "//"),
            ("tiebreak", "Set ended in a TIEBREAK", "next set opened by either player (about 50/50)", LIGHT, "..")]
    fig, ax = new_figure(figsize=(10, 4.8))
    for i, (key, head, tail, col, hatch) in enumerate(rows):
        sh = d.loc[key, "share"]
        ax.barh(i, sh, color=col, height=0.55, edgecolor="white", hatch=hatch, lw=0)
        ax.text(sh + 0.01, i, f"{sh:.0%} of sets", va="center", fontsize=11, fontweight="bold")
        ax.text(0.0, i - 0.43, f"{head}  →  {tail}", va="center", fontsize=10.5, color=INK2)
    ax.set_yticks([])
    ax.set_xlim(0, 0.78)
    ax.set_ylim(2.5, -0.8)
    ax.xaxis.set_major_formatter(PCT)
    ax.set_xlabel("Share of sets that were followed by another set")
    tot = d.loc["all", "next_fs_is_loser"]
    ax.set_title(f"Serve alternates through set breaks, so {tot:.0%} of later sets\n"
                 "are opened by the player who has just lost a set", loc="left")
    ax.grid(axis="y", visible=False)
    save_fig(fig, out)
    plt.close(fig)


def fig_prev_set(sel: pd.DataFrame, pwc: pd.DataFrame, out: Path) -> None:
    """A: first server's win rate after winning vs losing the previous set (the selection).
    B: model-free check - previous-set winner's win rate when serving first vs receiving first."""
    fig, axes = new_figure(1, 2, figsize=(12, 5.4))
    won = sel[sel.cell.str.contains("won previous")].iloc[0]
    lost = sel[sel.cell.str.contains("lost previous")].iloc[0]
    ax = axes[0]
    for i, (r, hatch) in enumerate(((won, ""), (lost, "//"))):
        ax.bar(i, r.p_win, color=LIGHT, edgecolor=GREY, hatch=hatch, width=0.55)
        ax.errorbar(i, r.p_win, yerr=[[r.p_win - r.lo], [r.hi - r.p_win]], color=BLACK, lw=1.5, capsize=6)
        ax.text(i, r.hi + 0.015, f"{r.p_win:.1%}\n(n = {int(r.n):,} sets)", ha="center", va="bottom", fontsize=10.5)
    ax.set_xticks([0, 1], ["First server WON\nthe previous set", "First server LOST\nthe previous set"])
    ax.set_ylabel("Wins the set they serve first")
    ax.set_title(f"A. Sets 2+: {lost.n / (won.n + lost.n):.0%} of first servers\njust lost a set, and they usually lose again")
    ax2 = axes[1]
    a = pwc[pwc.gender == "All"].set_index("previous_set_winner")
    for i, (key, hatch) in enumerate((("serves first", ""), ("receives first", "//"))):
        r = a.loc[key]
        ax2.bar(i, r.p_wins, color=LIGHT, edgecolor=GREY, hatch=hatch, width=0.55)
        ax2.errorbar(i, r.p_wins, yerr=[[r.p_wins - r.lo], [r.hi - r.p_wins]], color=BLACK, lw=1.5, capsize=6)
        ax2.text(i, r.hi + 0.015, f"{r.p_wins:.1%}\n(n = {int(r.n_sets):,} sets)", ha="center", va="bottom", fontsize=10.5)
    ax2.set_xticks([0, 1], ["Previous-set winner\nSERVES first", "Previous-set winner\nRECEIVES first"])
    ax2.set_ylabel("Previous-set winner wins this set")
    ax2.set_title("B. Same previous-set result, different serve order:\nno difference (model-free check)")
    for axx in axes:
        _ref(axx)
        axx.set_ylim(0, 0.88)
        axx.yaxis.set_major_formatter(PCT)
        axx.grid(axis="x", visible=False)
    save_fig(fig, out)
    plt.close(fig)


def fig_validation(V: pd.DataFrame, svyear: pd.DataFrame, est: pd.DataFrame, out: Path) -> None:
    """Three panels: SvGms rule outcome vs truth by era; SvGms correctness by year; estimators vs truth."""
    fig, axes = new_figure(1, 3, figsize=(17, 6),
                             gridspec_kw={"width_ratios": [1.15, 1.1, 1.2]})
    ax = axes[0]
    cats = [("identified, correct", SET1, ""), ("identified, WRONG", VERM, "xx"), ("ambiguous (both fit)", LIGHT, ""),
            ("neither fits", GREY, "")]
    groups = []
    for g in ("M", "W"):
        for era, m in (("2011-15, 2024", V.year.isin([2011, 2012, 2013, 2014, 2015, 2024])),
                       ("2016-23", V.year.between(2016, 2023))):
            d = V[(V.gender == g) & m & (V.category != "no score/stats")]
            idf = d.category == "identified"
            vals = [(idf & (d.fit_w == d.truth_w_first)).mean(), (idf & (d.fit_w != d.truth_w_first)).mean(),
                    (d.category == "ambiguous").mean(), (d.category == "neither").mean()]
            groups.append((f"{'Men' if g == 'M' else 'Women'} {era}\n(n={len(d):,})", vals))
    left = np.zeros(len(groups))
    for ci, (cname, col, hatch) in enumerate(cats):
        w = np.array([v[ci] for _, v in groups])
        ax.barh(range(len(groups)), w, left=left, color=col, edgecolor="white", hatch=hatch, lw=0.5,
                label=cname, height=0.6)
        for i, (wi, li) in enumerate(zip(w, left)):
            if wi > 0.07:
                on_hatch = bool(hatch)          # text on a hatched segment gets a solid white background
                ax.text(li + wi / 2, i, f"{wi:.0%}", ha="center", va="center", fontsize=10,
                        color=BLACK if (on_hatch or col == LIGHT) else "white", fontweight="bold",
                        bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none") if on_hatch else None)
        left += w
    ax.set_yticks(range(len(groups)), [g for g, _ in groups])
    ax.invert_yaxis()
    ax.set_xlim(0, 1)
    ax.xaxis.set_major_formatter(PCT)
    ax.set_xlabel("Share of linked matches")
    ax.set_title("A. SvGms rule vs true first server")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.13), ncol=2)
    ax.grid(axis="y", visible=False)
    ax = axes[1]
    for g, c, mk, nm in (("M", MEN, "o", "Men"), ("W", WOMEN, "s", "Women (stats from 2014)")):
        d = svyear[svyear.gender == g].sort_values("year")
        ax.plot(d.year, d.svgms_exact, color=c, lw=2, marker=mk, ms=7, label=nm, ls="-" if g == "M" else "--")
    ax.set_ylim(0, 1.05)
    ax.yaxis.set_major_formatter(PCT)
    ax.set_xlabel("Year")
    ax.set_ylabel("Matches where TML SvGms = true count")
    ax.set_title("B. TML service-game counts\nare often wrong in 2016-23")
    ax.legend(loc="lower left")
    ax = axes[2]
    spec = [("truth (pbp)", "Truth (point-by-point)", BLACK, "o"),
            ("A: posterior (all matches)", "A: earlier headline (posterior, all matches)", MEN, "s"),
            ("B*: B minus null selection bias", "B*: identified only, bias-corrected", SKY, "D"),
            ("B: SvGms-identified only", "B: identified matches only (biased)", VERM, "^")]
    for k, sg in enumerate(("set 1", "sets 2+", "all sets")):
        for j, (nm, lab, col, mk) in enumerate(spec):
            r = est[(est.gender == "Men") & (est.set_group == sg) & (est.estimator == nm)]
            if not len(r):
                continue
            r = r.iloc[0]
            x = k + (j - 1.5) * 0.18
            if np.isnan(r.lo):
                ax.plot([x], [r.p], marker=mk, color=col, ms=8, ls="none", label=lab if k == 0 else None, zorder=3)
            else:
                _err(ax, np.array([x]), np.array([r.p]), np.array([r.lo]), np.array([r.hi]), col, marker=mk,
                     label=lab if k == 0 else None)
    _ref(ax)
    ax.set_xticks(range(3), ["Set 1", "Sets 2+", "All sets"])
    ax.set_ylabel("P(first server wins the set)")
    ax.yaxis.set_major_formatter(PCT)
    ax.set_title("C. Men, same matches:\nearlier estimators vs truth")
    h, l = ax.get_legend_handles_labels()
    order = [l.index(lab) for _, lab, _, _ in spec if lab in l]
    ax.legend([h[i] for i in order], [l[i] for i in order], loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=1)
    ax.grid(axis="x", visible=False)
    save_fig(fig, out)
    plt.close(fig)


def fig_over_time(tab: pd.DataFrame, out: Path) -> None:
    """Appendix: by year, set 1 and sets 2+, both genders pooled, 95% CI bands."""
    fig, ax = new_figure(figsize=(10, 5.2))
    for sg, c, ls in (("set 1", SET1, "-"), ("sets 2+", LATER, "--")):
        d = tab[tab.set_group == sg].sort_values("year")
        ax.fill_between(d.year, d.lo, d.hi, color=c, alpha=0.2, lw=0)
        ax.plot(d.year, d.p, color=c, lw=2, ls=ls, marker=MK[sg], ms=7, label="Set 1" if sg == "set 1" else "Sets 2+")
    _ref(ax)
    ax.set_xlabel("Year")
    ax.set_ylabel("P(first server wins the set)")
    ax.yaxis.set_major_formatter(PCT)
    ax.yaxis.set_major_locator(matplotlib.ticker.MultipleLocator(0.02))
    ax.set_xticks(sorted(tab.year.unique()))
    ax.tick_params(axis="x", rotation=45)
    ax.set_title("Raw win rate of the set's first server by year (men and women pooled, 95% CIs)")
    ax.legend(loc="upper right", ncol=2)
    save_fig(fig, out)
    plt.close(fig)
