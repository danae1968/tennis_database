"""Can height alone predict who wins a match? (WTA and ATP tour level, 2016-2026)

    .venv/bin/python analyses/height_predicts_winner/run.py        (or: make height_predicts_winner)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

if __package__ in (None, ""):                       # run as a script: make ``analyses.*`` importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from analyses.height_predicts_winner import data as D  # noqa: E402
from analyses.height_predicts_winner import model as Mo  # noqa: E402
from analyses.height_predicts_winner import plots  # noqa: E402
from analyses.height_predicts_winner import rank as Rk  # noqa: E402
from tennis.paths import analysis_dirs  # noqa: E402
from tennis.stats import expit, wilson_ci  # noqa: E402

RES, FIG, _ = analysis_dirs("height_predicts_winner")
BOOT_REPS = 1000
MECH_BOOT = 200                                      # tournament-bootstrap replicates for the mechanism shares
BINS = [0.5, 2.5, 5.5, 9.5, 14.5, 19.5, 60]          # |height difference| in cm: 1-2, 3-5, 6-9, 10-14, 15-19, 20+
BIN_LABELS = ["1-2", "3-5", "6-9", "10-14", "15-19", "20+"]


def _save(df: pd.DataFrame, name: str) -> None:
    df.to_csv(RES / name, index=False, float_format="%.6f")


def taller_frame(m: pd.DataFrame) -> pd.DataFrame:
    """Matches with a height difference, seen from the taller player."""
    d = m[m["ht_diff"].notna() & (m["ht_diff"] != 0)].copy()
    d["gap"] = d["ht_diff"].abs()
    d["taller_won"] = ((d["ht_diff"] > 0) == (d["p1_won"] == 1)).astype(int)
    return d


def main() -> None:
    raw = D.load_raw()
    rates = D.player_ace_rates(raw)
    m, log = D.build_matches(raw, ace_rates=rates)
    _save(log, "cleaning.csv")
    cov = D.height_coverage(m)
    _save(cov, "height_coverage.csv")
    cc = m[m["ht_diff"].notna() & m["log_rank_ratio"].notna()].copy()       # complete cases for all models

    comp, added, surf_rows, mech_rows, miss_rows, bin_rows, curve_rows, plain = [], [], [], [], [], [], [], {}
    inter_rows, sens_rows = [], []
    for tour in D.TOURS:
        x = cc[cc["tour"] == tour]
        tr, te = x[x["split"] == "train"], x[x["split"] == "test"]
        tab, fitted = Mo.evaluate(tr, te)
        comp.append(tab.assign(tour=tour, n_train=len(tr)))
        boot = Mo.paired_bootstrap(te["p1_won"].values, fitted["Ranking only"][1], fitted["Ranking + height"][1],
                                   reps=BOOT_REPS, seed=D.SEED)
        rh = fitted["Ranking + height"][0]
        added.append({"tour": tour, **boot, "wald_p_height_train": float(rh.pvalues["ht_diff"]),
                      "or_per_10cm_given_rank": float(np.exp(10 * rh.params["ht_diff"]))})
        tw = Mo.taller_player_wins(te)
        plain[tour] = {"taller_player_wins_test": tw, "accuracy": tab.set_index("model")["accuracy"].to_dict()}

        # by surface: plain taller-wins rate (all years) and test accuracy of the pooled models per surface
        for s in D.SURFACES:
            xs = x[x["surface"] == s]
            t = taller_frame(xs)
            lo, hi = wilson_ci(t["taller_won"].sum(), len(t))
            row = {"tour": tour, "surface": s, "taller_wins": float(t["taller_won"].mean()), "lo": lo, "hi": hi, "n": len(t)}
            r_h = Mo.fit(xs, ["ht_diff"])
            r_rh = Mo.fit(xs, ["log_rank_ratio", "ht_diff"])
            for nm, r in (("height_only", r_h), ("given_rank", r_rh)):
                b, se = float(r.params["ht_diff"]), float(r.bse["ht_diff"])
                row.update({f"or10_{nm}": float(np.exp(10 * b)), f"or10_{nm}_lo": float(np.exp(10 * (b - 1.96 * se))),
                            f"or10_{nm}_hi": float(np.exp(10 * (b + 1.96 * se)))})
            tes = te[te["surface"] == s]
            for name in ("Height only", "Ranking only", "Ranking + height"):
                row[f"test_acc_{name}"] = Mo.metrics(tes["p1_won"].values, fitted[name][1][(te["surface"] == s).values])["accuracy"]
            surf_rows.append(row)

        # association with the serve: how much of height's effect (given ranking) is accounted for by the
        # previous season's serve record?  Placebo: previous-season RETURN record (not a serve channel).
        # Sample = established players (previous season with >= 300 serve and return points).
        y = x.dropna(subset=["ace_diff", "spw_diff", "rpw_diff"])
        specs = (("ranking + height", ["log_rank_ratio", "ht_diff"]),
                 ("+ ace rate (prev. season)", ["log_rank_ratio", "ht_diff", "ace_diff"]),
                 ("+ serve points won (prev. season)", ["log_rank_ratio", "ht_diff", "spw_diff"]),
                 ("+ return points won (prev. season; placebo)", ["log_rank_ratio", "ht_diff", "rpw_diff"]),
                 ("+ serve and return points won", ["log_rank_ratio", "ht_diff", "spw_diff", "rpw_diff"]))
        base_b = None
        for label, xs_ in specs:
            r = Mo.fit(y, xs_)
            b, se = float(r.params["ht_diff"]), float(r.bse["ht_diff"])
            base_b = b if base_b is None else base_b
            mech_rows.append({"tour": tour, "model": label, "n": len(y), "or_per_10cm": float(np.exp(10 * b)),
                              "lo": float(np.exp(10 * (b - 1.96 * se))), "hi": float(np.exp(10 * (b + 1.96 * se))),
                              "p": float(r.pvalues["ht_diff"]), "share_of_height_effect_accounted": 1 - b / base_b,
                              **{f"coef_{v}": float(r.params[v]) for v in xs_ if v != "ht_diff"}})
        # bootstrap (resampling tournaments) CI for the share of the height log-odds accounted for
        rng = np.random.default_rng(D.SEED)
        tours_ = y["tourney_id"].unique()
        groups = {t_: g.index.values for t_, g in y.groupby("tourney_id")}
        shares = {"ace": [], "spw": [], "rpw": []}
        import statsmodels.api as sm
        for _ in range(MECH_BOOT):
            idx = np.concatenate([groups[t_] for t_ in rng.choice(tours_, len(tours_))])
            yb = y.loc[idx]
            def coef(cols):
                return float(sm.Logit(yb["p1_won"].astype(float), yb[cols].astype(float)).fit(disp=0).params["ht_diff"])
            b0 = coef(["log_rank_ratio", "ht_diff"])
            for k, col in (("ace", "ace_diff"), ("spw", "spw_diff"), ("rpw", "rpw_diff")):
                shares[k].append(1 - coef(["log_rank_ratio", "ht_diff", col]) / b0)
        for k, v in shares.items():
            lo_, hi_ = np.percentile(v, [2.5, 97.5])
            mech_rows.append({"tour": tour, "model": f"bootstrap CI of share accounted ({k})", "n": len(y),
                              "share_lo": float(lo_), "share_hi": float(hi_)})
        mech_rows.append({"tour": tour, "model": "corr(height diff, ace diff)", "n": len(y),
                          "or_per_10cm": float(y["ht_diff"].corr(y["ace_diff"]))})

        # does the height effect differ by surface? joint Wald test of height x surface (given ranking)
        xi = x[x["surface"].isin(D.SURFACES)].copy()
        for s_ in ("Clay", "Grass"):
            xi[f"ht_x_{s_}"] = xi["ht_diff"] * (xi["surface"] == s_)
        ri = Mo.fit(xi, ["log_rank_ratio", "ht_diff", "ht_x_Clay", "ht_x_Grass"])
        w = ri.wald_test("ht_x_Clay = 0, ht_x_Grass = 0", scalar=True)
        inter_rows.append({"tour": tour, "chi2": float(w.statistic), "df": 2, "p": float(w.pvalue),
                           "or10_hard": float(np.exp(10 * ri.params["ht_diff"])),
                           "or10_clay": float(np.exp(10 * (ri.params["ht_diff"] + ri.params["ht_x_Clay"]))),
                           "or10_grass": float(np.exp(10 * (ri.params["ht_diff"] + ri.params["ht_x_Grass"])))})

        # sensitivity: test only on seasons with high height coverage (WTA 2025: 92%)
        if tour == "WTA":
            te25 = te[te["year"] == 2025]
            for name in ("Coin flip", "Height only", "Ranking only", "Ranking + height"):
                res_, _ = fitted[name]
                xs_ = Mo.MODELS[name]
                sens_rows.append({"tour": tour, "test": "2025 only (92% height coverage)", "model": name,
                                  **Mo.metrics(te25["p1_won"].values, Mo.predict(res_, te25, xs_))})

        # are matches with missing heights different? ranking-only accuracy with vs without heights
        allr = m[(m["tour"] == tour) & m["log_rank_ratio"].notna()]
        r_rank = Mo.fit(allr[allr["split"] == "train"], ["log_rank_ratio"])
        for has, g in allr[allr["split"] == "test"].groupby(allr["ht_diff"].notna()):
            miss_rows.append({"tour": tour, "heights_available": bool(has), "n": len(g),
                              "ranking_only_accuracy": Mo.metrics(g["p1_won"].values, Mo.predict(r_rank, g, ["log_rank_ratio"]))["accuracy"],
                              "median_better_rank": float(np.median(np.minimum(g["rank1"], g["rank2"])))})

        # binned curve (all years) and fitted height-only curve
        t = taller_frame(x)
        t["bin"] = pd.cut(t["gap"], BINS, labels=BIN_LABELS)
        for lab, g in t.groupby("bin", observed=True):
            lo, hi = wilson_ci(g["taller_won"].sum(), len(g))
            bin_rows.append({"tour": tour, "bin": lab, "mid_cm": float(g["gap"].median()), "p": float(g["taller_won"].mean()),
                             "lo": lo, "hi": hi, "n": len(g)})
        # no intercept (random player order), so the taller player's curve is expit(b * gap); drawn over the data range
        r_all = Mo.fit(x, ["ht_diff"])
        for dcm in np.arange(0, float(np.ceil(t["gap"].quantile(0.99))) + 1, 1.0):
            curve_rows.append({"tour": tour, "diff_cm": dcm, "p_taller": expit(float(r_all.params["ht_diff"]) * dcm)})

    comp = pd.concat(comp, ignore_index=True)
    _save(comp, "model_comparison.csv")
    _save(pd.DataFrame(added), "height_added_value.csv")
    surf = pd.DataFrame(surf_rows)
    _save(surf, "by_surface.csv")
    _save(pd.DataFrame(mech_rows), "mechanism_serve.csv")
    _save(pd.DataFrame(inter_rows), "height_by_surface_interaction.csv")
    _save(pd.DataFrame(sens_rows), "wta_high_coverage_sensitivity.csv")
    _save(pd.DataFrame(miss_rows), "missing_heights_check.csv")
    binned = pd.DataFrame(bin_rows)
    _save(binned, "taller_player_by_gap.csv")
    curve = pd.DataFrame(curve_rows)
    _save(curve, "fitted_height_curve.csv")
    # does height predict ranking?  (player level) and how much of height's effect on winning does ranking absorb?
    players = Rk.player_table(raw)
    corr_rows, reach_frames, att_rows, sel_rows = [], [], [], []
    for tour in D.TOURS:
        pl = players[players["tour"] == tour]
        for col in ("median_rank", "best_rank"):
            corr_rows.append({"tour": tour, "ranking_summary": col, **Rk.spearman_height_rank(pl, col, seed=D.SEED)})
        bands = Rk.height_bands(pl["height"])
        reach_frames.append(Rk.reach_by_band(pl, bands).assign(tour=tour))
        att_rows.append({"tour": tour, **Rk.attenuation(cc[cc["tour"] == tour].reset_index(drop=True), seed=D.SEED)})
        allp = Rk.player_table(raw, require_height=False)
        sel_rows.append({"tour": tour, "players_ranked_20plus_matches_with_height": len(pl),
                         "players_ranked_20plus_matches": int((allp["tour"] == tour).sum()),
                         "median_height_cm": float(pl["height"].median()), "mean_height_cm": float(pl["height"].mean())})
    thr_rows = []                                       # sensitivity of the correlation to the match threshold
    for tour in D.TOURS:
        for k in (1, 5, 10, 20, 40):
            pk = Rk.player_table(raw, min_matches=k)
            pk = pk[pk["tour"] == tour]
            thr_rows.append({"tour": tour, "min_ranked_matches": k, **Rk.spearman_height_rank(pk, "median_rank", seed=D.SEED),
                             "share_top100": float((pk["best_rank"] <= 100).mean())})
    _save(pd.DataFrame(thr_rows), "height_rank_threshold_sensitivity.csv")
    _save(pd.DataFrame(corr_rows), "height_rank_correlation.csv")
    reach = pd.concat(reach_frames, ignore_index=True)
    _save(reach, "height_reach_top_by_band.csv")
    _save(pd.DataFrame(att_rows), "height_effect_absorbed_by_ranking.csv")
    _save(players, "player_height_rank.csv")
    (RES / "headline.json").write_text(json.dumps(plain, indent=1, default=float))

    plots.taller_player_curve(binned, curve, FIG / "fig1_taller_player_wins.png")
    plots.model_comparison(comp, FIG / "fig2_model_comparison.png")
    plots.by_surface(surf, FIG / "fig3_by_surface.png")
    plots.coverage(cov, FIG / "figA1_height_coverage.png")
    plots.reach_top20(reach, FIG / "fig4_height_reaches_top20.png")
    pd.set_option("display.width", 200)
    print(comp.round(4).to_string(index=False))
    print(pd.DataFrame(added).round(5).to_string(index=False))
    print(surf.round(3).to_string(index=False))
    print(pd.DataFrame(mech_rows).round(4).to_string(index=False))
    print(pd.DataFrame(miss_rows).round(4).to_string(index=False))
    for nm in (corr_rows, att_rows, sel_rows, thr_rows):
        print(pd.DataFrame(nm).round(4).to_string(index=False))
    print(reach.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
