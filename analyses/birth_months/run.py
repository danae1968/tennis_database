"""Birth months: regenerates all tables and figures for the birth-month analysis.

    .venv/bin/python analyses/birth_months/run.py        (or: make birth_months)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

if __package__ in (None, ""):                       # run as a script: make ``analyses.*`` importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from analyses.birth_months import data, plots  # noqa: E402
from analyses.birth_months import months as stats  # noqa: E402
from tennis.load import load_atp_players, load_wta_players  # noqa: E402
from tennis.paths import analysis_dirs  # noqa: E402

RES_DIR, FIG_DIR, _ = analysis_dirs("birth_months")

SOUTH = {"AUS", "NZL", "ARG", "BRA", "CHI", "URU", "PAR", "PER", "BOL", "RSA", "ZIM", "ZAM", "MOZ", "BOT", "NAM"}
EQUATOR = {"ECU", "COL", "KEN", "UGA", "INA", "SIN", "MAS", "GAB", "CGO", "COD", "SRI", "SOM", "TAN"}


def populations(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Named subsets of a clean (placeholder-free) player table."""
    return {"all": df, "played": df[df.n_matches >= 1], "elite_20plus": df[df.n_matches >= 20],
            "elite_top100": df[df.best_rank <= 100]}


def main() -> None:
    FIG_DIR.mkdir(exist_ok=True); RES_DIR.mkdir(exist_ok=True)
    clean_tabs, logs, phs = {}, {}, {}
    for g, loader, ms in (("ATP", load_atp_players, data.match_stats_atp),
                          ("WTA", load_wta_players, data.match_stats_wta)):
        d, log, ph = data.clean_players(loader(), ms())
        clean_tabs[g], logs[g], phs[g] = d, log, ph
    # cleaning table
    steps = [s for s, _ in logs["ATP"]]
    pd.DataFrame({"step": steps, "ATP": [n for _, n in logs["ATP"]], "WTA": [n for _, n in logs["WTA"]]}).to_csv(RES_DIR / "cleaning_table.csv", index=False)
    pd.concat([phs["ATP"].assign(source="ATP"), phs["WTA"].assign(source="WTA")]).to_csv(RES_DIR / "placeholder_detection.csv", index=False)
    allp = pd.concat(clean_tabs.values(), ignore_index=True)
    allp.drop(columns=["name_norm"]).to_csv(RES_DIR / "clean_players.csv", index=False)

    # counts and tests
    rows, summ, tables, qtabs = [], {}, {}, {}
    def run(label: str, gender: str, sub: pd.DataFrame, extra: str = "") -> None:
        c = stats.month_counts(sub["month"])
        if c.sum() < 50:
            return
        key = f"{gender}|{label}{extra}"
        t = stats.month_table(c); tables[key] = t
        q = stats.quarter_table(c); qtabs[key] = q
        t.assign(gender=gender, population=label + extra).to_csv(RES_DIR / f"months_{gender}_{label}{extra}.csv".replace("|", "_"), index=False)
        chi = stats.chi_square_gof(c); tr = stats.trend_test(c)
        q1q4 = float(q.ratio[0] / q.ratio[3]); chiq = stats.chi_square_gof(c, stats.QUARTERS)
        summ[key] = {**chi, "quarter_chi2": chiq["chi2"], "quarter_p": chiq["p"], "Q1_over_Q4": q1q4,
                     "trend": tr, "significant_months_holm05": t.loc[t.p_holm < .05, "month"].tolist()}
        rows.append(t.assign(gender=gender, population=label + extra))
    for g, d in clean_tabs.items():
        main_d = d[~d.placeholder]
        for label, sub in populations(main_d).items():
            run(label, g, sub)
        run("played", g, d[d.n_matches >= 1], "_incl_placeholders")   # sensitivity
        # era and hemisphere (played only)
        pl = main_d[main_d.n_matches >= 1]
        for lo, hi in ((1900, 1969), (1970, 1979), (1980, 1989), (1990, 2015)):
            run("played", g, pl[pl.birth_year.between(lo, hi)], f"_born_{lo}-{hi}")
        run("played", g, pl[pl.country.isin(SOUTH)], "_southern_hemisphere")
        run("played", g, pl[~pl.country.isin(SOUTH | EQUATOR)], "_northern_hemisphere")
    # combined populations
    comb = pd.concat([d[~d.placeholder] for d in clean_tabs.values()])
    for label, sub in populations(comb).items():
        run(label, "ATP+WTA", sub)
    # pooled hemisphere split (relative age effect predicts the same Jan->Dec gradient in both hemispheres)
    for label in ("all", "played"):
        sub = populations(comb)[label]
        run(label, "ATP+WTA", sub[sub.country.isin(SOUTH)], "_southern_hemisphere")
        run(label, "ATP+WTA", sub[~sub.country.isin(SOUTH | EQUATOR)], "_northern_hemisphere")

    # placeholder / heaping diagnostics and sensitivity analysis
    data.wta_id_coverage(load_wta_players()).to_csv(RES_DIR / "wta_id_coverage.csv", index=False)
    jan_rows = []
    for g, d in clean_tabs.items():
        for label, sub in (("all", d), ("played", d[d.n_matches >= 1])):
            jan_rows.append({"source": g, "population": label, **data.january_early_days_test(sub["birthdate"])})
    pd.DataFrame(jan_rows).to_csv(RES_DIR / "january_heaping_test.csv", index=False)
    sens = []
    for g, d in clean_tabs.items():
        for label in ("all", "played"):
            base = d if label == "all" else d[d.n_matches >= 1]
            variants = {"main (flagged 1st-of-month dates removed)": (base[~base.placeholder], stats.DAYS),
                        "all dates kept": (base, stats.DAYS),
                        "also drop 1-10 January (expected January days = 21)": (base[~(base.placeholder | ((base.month == 1) & (base.birthdate.dt.day <= 10)))],
                                                                                   np.r_[21, stats.DAYS[1:]])}
            for vname, (sub, days) in variants.items():
                c = stats.month_counts(sub["month"]); q = stats.quarter_table(c, days); t = stats.month_table(c, days)
                chi = stats.chi_square_gof(c, days=days)
                sens.append({"source": g, "population": label, "variant": vname, "n": int(c.sum()), "chi2": chi["chi2"], "p": chi["p"],
                             "Jan_ratio": float(t.ratio[0]), "Q1_over_Q4": float(q.ratio[0] / q.ratio[3])})
    pd.DataFrame(sens).to_csv(RES_DIR / "sensitivity_placeholders.csv", index=False)
    pd.concat(rows).to_csv(RES_DIR / "month_counts_all_populations.csv", index=False)
    (RES_DIR / "summary_stats.json").write_text(json.dumps(summ, indent=1, sort_keys=True))
    pd.concat([q.assign(key=k) for k, q in qtabs.items()]).to_csv(RES_DIR / "quarter_tables.csv", index=False)
    pop_sizes = {k: int(v.observed.sum()) for k, v in tables.items()}
    (RES_DIR / "population_sizes.json").write_text(json.dumps(pop_sizes, indent=1, sort_keys=True))

    # figures
    plots.plot_obs_vs_exp(tables["ATP+WTA|played"], "Births per month, ATP+WTA players with at least one tour-level match: observed vs expected", FIG_DIR / "fig1_observed_vs_expected.png")
    plots.plot_ratio({"ATP+WTA|played": tables["ATP+WTA|played"]}, "Observed/expected births by month, ATP+WTA players with at least one tour-level match", FIG_DIR / "fig2_ratio.png", None)
    plots.plot_ratio({"ATP": tables["ATP|played"], "WTA": tables["WTA|played"]}, "Observed/expected births by month: ATP vs WTA players (at least one tour-level match)", FIG_DIR / "fig3_atp_vs_wta.png")
    plots.plot_quarters({"ATP": qtabs["ATP|played"], "WTA": qtabs["WTA|played"]}, "Births by quarter relative to expectation (relative age effect)", FIG_DIR / "fig4_quarters.png")
    plots.plot_ratio({"all": tables["ATP+WTA|all"], "elite": tables["ATP+WTA|elite_20plus"]}, "Observed/expected births by month: all players vs elite (20+ tour matches), ATP+WTA", FIG_DIR / "fig5_elite_vs_all.png")
    print(pd.read_csv(RES_DIR / "cleaning_table.csv").to_string(index=False))
    for k, v in summ.items():
        print(k, pop_sizes[k], f"chi2={v['chi2']:.1f} p={v['p']:.2g} Q1/Q4={v['Q1_over_Q4']:.2f} sig={v['significant_months_holm05']}")


if __name__ == "__main__":
    main()
