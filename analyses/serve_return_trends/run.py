"""Serve and return trends: aces and breaks (WTA 2009-, ATP 1991-, Challenger 2010-), Slam winners
(excl. aces) and unforced errors 2011-2024, Match Charting 2016-2026.

    .venv/bin/python analyses/serve_return_trends/run.py        (or: make serve_return_trends)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

if __package__ in (None, ""):                       # run as a script: make ``analyses.*`` importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from analyses.serve_return_trends import data, eras, plots  # noqa: E402
from analyses.serve_return_trends import winners as W  # noqa: E402
from tennis.paths import analysis_dirs  # noqa: E402
from tennis.plotting import GREEN as GREEN_, GREY as GREY_  # noqa: E402
from tennis.stats import ratio_ci, trend_per_decade  # noqa: E402

RES, FIG, _ = analysis_dirs("serve_return_trends")
METRICS = {"ace_rate": ("aces", "svpt"), "break_rate": ("breaks", "service_games"),
           "bp_conversion": ("breaks", "bp_faced")}
WIN_METRICS = {"winners_ex_rate": ("winners_ex", "points"), "ue_rate": ("ue", "points"), "ace_rate": ("aces", "points")}


def _save(df: pd.DataFrame, name: str) -> None:
    df.to_csv(RES / name, index=False, float_format="%.6f")


def yearly(d: pd.DataFrame, by: list[str], metrics: dict, cluster: str) -> pd.DataFrame:
    """Pooled rate with clustered 95% CI per group and year."""
    rows = []
    for key, g in d.groupby(by + ["year"], sort=True):
        key = key if isinstance(key, tuple) else (key,)
        for m, (num, den) in metrics.items():
            r = ratio_ci(g[num], g[den], g[cluster])
            rows.append({**dict(zip(by + ["year"], key)), "metric": m, "rate": r["rate"], "lo": r["lo"], "hi": r["hi"],
                         "n_matches": r["n"], "num": r["num"], "den": r["den"]})
    return pd.DataFrame(rows)


def trends(d: pd.DataFrame, group: str, groups, metrics: dict, cluster: str, fe: str, label: str) -> pd.DataFrame:
    """Change per decade (percentage points) per group, all surfaces (with surface/event FE) and by surface."""
    rows = []
    for g in groups:
        sub = d[d[group] == g]
        for m, (num, den) in metrics.items():
            for surf in ["All", "Hard", "Clay", "Grass"]:
                s = sub if surf == "All" else sub[sub["surface"] == surf]
                if s["year"].nunique() < 4:
                    continue
                ctrl = fe if surf == "All" else (fe if fe.startswith("C(slam") else fe.replace("C(surface) + ", "").replace("C(surface)", ""))
                r = trend_per_decade(s, m, weight=den, cluster=cluster, controls=ctrl, scale=100)
                rows.append({"source": label, group: g, "metric": m, "surface": surf, **r})
    return pd.DataFrame(rows)


def main() -> None:
    # ------------------------------------------------ A1/A2 aces and breaks (TennisMyLife)
    raw = data.load_raw()
    _save(data.coverage_table(raw), "coverage_serve_stats.csv")
    d, log = data.build_match_frame(raw)
    del raw
    _save(log, "cleaning_tml.csv")
    full = d[~d["partial_year"]]
    recent = full[full["year"].between(*data.RECENT)]
    y_all = yearly(d, ["tour"], METRICS, "edition")
    y_surf = yearly(d[d["surface"].notna()], ["tour", "surface"], METRICS, "edition")
    _save(y_all, "yearly_tml_by_tour.csv")
    _save(y_surf, "yearly_tml_by_tour_surface.csv")
    tr = pd.concat([trends(full, "tour", data.TOURS, METRICS, "tournament", "C(surface)", "whole period"),
                    trends(full, "tour", data.TOURS, METRICS, "tournament", "C(tournament)", "whole period, tournament fixed effects"),
                    trends(recent, "tour", data.TOURS, METRICS, "tournament", "C(surface)", "2016-2025"),
                    trends(recent, "tour", data.TOURS, METRICS, "tournament", "C(tournament)", "2016-2025, tournament fixed effects")])
    first = full.groupby("tour")["year"].min()
    tr["first_year"] = np.where(tr["source"].str.startswith("2016"), 2016, tr["tour"].map(first))
    _save(tr, "trends_tml.csv")
    surf_tab = yearly(d[d["surface"].notna()], ["tour", "surface"], {"n": ("aces", "svpt")}, "edition")
    _save(surf_tab.groupby(["tour", "surface"]).n_matches.sum().reset_index(), "matches_by_tour_surface.csv")
    # long-run shape: slope before vs after 2016, like-for-like yearly levels, step check
    kink, idx, steps = [], [], []
    for t_ in data.TOURS:
        for m in ("ace_rate", "break_rate"):
            num, den = METRICS[m]
            for surf in ("All", "Hard", "Clay", "Grass"):
                s = full[full["tour"] == t_] if surf == "All" else full[(full["tour"] == t_) & (full["surface"] == surf)]
                if s["year"].nunique() >= 8 and s["year"].min() < eras.KNOT - 3 and len(s) >= 2000:
                    kink.append({"tour": t_, "metric": m, "surface": surf, **eras.slope_change(s, m, den)})
            ix = eras.like_for_like_index(full[full["tour"] == t_], m, num, den, ref_year=data.RECENT[1])
            idx.append(ix.assign(tour=t_, metric=m))
            steps.append(eras.year_on_year_jumps(ix).assign(tour=t_, metric=m))
    _save(pd.DataFrame(kink), "slope_change_2016.csv")
    # sensitivity: ATP Slam serve-point counts look about 10% high before 2000 (Slam points per game 6.9-7.1 in
    # 1992-99 against 6.3 later), which would understate early Slam ace rates; refit ATP without those Slams
    atp = full[full["tour"] == "ATP"]
    early_slams = (atp["tourney_level"] == "G") & (atp["year"] < 2000)
    ppg = atp.assign(ppg=atp["svpt"] / atp["service_games"], slam=atp["tourney_level"] == "G", pre2000=atp["year"] < 2000)
    sens = [{"check": "ATP Slam serve points per service game, 1991-99", "value": float(ppg[ppg.slam & ppg.pre2000]["svpt"].sum() / ppg[ppg.slam & ppg.pre2000]["service_games"].sum())},
            {"check": "ATP Slam serve points per service game, 2000-25", "value": float(ppg[ppg.slam & ~ppg.pre2000]["svpt"].sum() / ppg[ppg.slam & ~ppg.pre2000]["service_games"].sum())},
            {"check": "ATP non-Slam serve points per service game, 1991-99", "value": float(ppg[~ppg.slam & ppg.pre2000]["svpt"].sum() / ppg[~ppg.slam & ppg.pre2000]["service_games"].sum())}]
    for lab, x in (("all ATP matches", atp), ("without Slams before 2000", atp[~early_slams]), ("without any Slams", atp[atp["tourney_level"] != "G"])):
        for m in ("ace_rate", "break_rate"):
            r = trend_per_decade(x, m, weight=METRICS[m][1], cluster="tournament", controls="C(tournament)", scale=100)
            k = eras.slope_change(x, m, METRICS[m][1])
            sens.append({"check": f"{m}: {lab}", "value": r["per_decade"], "lo": r["lo"], "hi": r["hi"],
                         "slope_before_2016": k["slope_before"], "slope_after_2016": k["slope_after"], "change": k["change"],
                         "change_lo": k["change_lo"], "change_hi": k["change_hi"]})
    _save(pd.DataFrame(sens), "sensitivity_atp_early_slams.csv")
    idx = pd.concat(idx, ignore_index=True)
    _save(idx, "like_for_like_index.csv")
    _save(pd.concat(steps, ignore_index=True), "step_check.csv")

    # ------------------------------------------------ A3 winners: Slam pbp and Match Charting
    p = W.load_pbp_matches()
    _save(W.feed_check(p), "slam_feed_check.csv")
    p = p[p["annotated"]].copy()
    _save(W.round_reweighted(p, p), "slam_round_reweighting.csv")
    c = W.load_charting_matches()
    for df in (p, c):
        for m, (num, den) in WIN_METRICS.items():
            df[m] = df[num] / df[den]
    # one Slam per surface-year for clay and grass, so yearly CIs cluster by match (points within matches)
    p_y = yearly(p, ["gender", "surface"], WIN_METRICS, "match_id")
    c["cluster"] = c["tournament"] + "|" + c["year"].astype(str)
    c_y = yearly(c, ["gender", "surface"], WIN_METRICS, "charter")
    _save(p_y, "yearly_slam_pbp_winners.csv")
    _save(c_y, "yearly_charting_winners.csv")
    _save(yearly(p, ["gender", "provider"], WIN_METRICS, "match_id"), "yearly_slam_pbp_winners_by_provider.csv")
    c["event_type"] = np.where(c["slam"].notna(), "Grand Slams", "Other events")
    c_k = yearly(c, ["gender", "event_type"], WIN_METRICS, "charter")
    _save(c_k, "yearly_charting_winners_by_event_type.csv")
    kt = []
    for g in ("W", "M"):
        for k in ("Grand Slams", "Other events"):
            s_ = c[(c["gender"] == g) & (c["event_type"] == k) & (c["year"] < data.PARTIAL_YEAR)]
            r = trend_per_decade(s_, "winners_ex_rate", weight="points", cluster="cluster", controls="C(surface)", scale=100)
            kt.append({"gender": g, "event_type": k, **r})
    _save(pd.DataFrame(kt), "trends_charting_winners_by_event_type.csv")
    # the men's non-Slam jump: one prolific charter (identified from the data, not named in outputs)
    ns = c[(c["gender"] == "M") & c["slam"].isna()].copy()
    ns["period"] = np.where(ns["year"] <= 2021, "2016-21", "2022-26")
    top = ns[ns["period"] == "2022-26"]["charter"].value_counts().index[0]
    rows = []
    for lab, x in (("all charted non-Slam men's matches", ns), ("without the most prolific charter", ns[ns["charter"] != top]),
                   ("most prolific charter only", ns[ns["charter"] == top])):
        for per, g in x.groupby("period"):
            r = ratio_ci(g["winners_ex"], g["points"], g["charter"])
            rows.append({"sample": lab, "period": per, "winners_ex_per_100": 100 * r["rate"], "matches": len(g)})
    _save(pd.DataFrame(rows), "charting_charter_check.csv")
    ct = []
    for g in ("W", "M"):
        for lab, x in (("all", c), ("without the most prolific charter", c[c["charter"] != top])):
            s_ = x[(x["gender"] == g) & (x["year"] < data.PARTIAL_YEAR)]
            ct.append({"gender": g, "sample": lab, **trend_per_decade(s_, "winners_ex_rate", weight="points", cluster="charter",
                                                                      controls="C(surface)", scale=100)})
    _save(pd.DataFrame(ct), "trends_charting_by_charter_cluster.csv")
    c_ns = c[c["slam"].isna()].copy()
    c_ns_y = pd.concat([yearly(c_ns, ["gender"], {"winners_ex_rate": ("winners_ex", "points")}, "charter").assign(sample="All charted matches"),
                        yearly(c_ns[c_ns["charter"] != top], ["gender"], {"winners_ex_rate": ("winners_ex", "points")}, "charter")
                        .assign(sample="Without the most prolific charter")])
    _save(c_ns_y, "yearly_charting_nonslam_by_charter_sample.csv")

    # is the break decline concentrated on hard courts? slope differences (year x surface), both windows
    import statsmodels.formula.api as smf
    sd = []
    for win, frame in (("whole period", full), ("2016-2025", recent)):
        for t in data.TOURS:
            x = frame[(frame["tour"] == t) & frame["surface"].isin(["Hard", "Clay", "Grass"])].copy()
            x["yr"] = x["year"] - x["year"].min()
            res = smf.wls("break_rate ~ yr * C(surface, Treatment('Hard'))", x, weights=x["service_games"]).fit(
                cov_type="cluster", cov_kwds={"groups": pd.factorize(x["tournament"])[0]})
            for s_ in ("Clay", "Grass"):
                k = f"yr:C(surface, Treatment('Hard'))[T.{s_}]"
                b_, se_ = float(res.params[k]), float(res.bse[k])
                sd.append({"window": win, "tour": t, "comparison": f"{s_} minus Hard slope", "per_decade": 1000 * b_,
                           "lo": 1000 * (b_ - 1.96 * se_), "hi": 1000 * (b_ + 1.96 * se_), "p": float(res.pvalues[k])})
    _save(pd.DataFrame(sd), "break_trend_surface_differences.csv")
    wt = pd.concat([trends(p, "gender", ("W", "M"), WIN_METRICS, "event", "C(slam)", "Slam pbp 2011-2024"),
                    trends(p[p["year"] >= 2016], "gender", ("W", "M"), WIN_METRICS, "event", "C(slam)", "Slam pbp 2016-2024"),
                    trends(p[p["year"] <= 2015], "gender", ("W", "M"), WIN_METRICS, "event", "C(slam)", "Slam pbp 2011-2015"),
                    trends(c[c["year"] < data.PARTIAL_YEAR], "gender", ("W", "M"), WIN_METRICS, "charter", "C(surface)",
                           "Match Charting 2016-2025")])
    _save(wt, "trends_winners.csv")
    # robustness: the two Slams with the same (IBM) feed in every year
    q = p[p["slam"].isin(["usopen", "wimbledon"])]
    _save(pd.concat([trends(q, "gender", ("W", "M"), WIN_METRICS, "event", "C(slam)", "Slam pbp 2011-2024, US Open + Wimbledon only"),
                     trends(q[q["year"] >= 2016], "gender", ("W", "M"), WIN_METRICS, "event", "C(slam)",
                            "Slam pbp 2016-2024, US Open + Wimbledon only")]), "trends_winners_uso_wimbledon.csv")
    # by Slam: is the decline shared, or carried by one event? (clustered by edition: one per year, t with G-1 df)
    bs = []
    for slam in ("ausopen", "frenchopen", "usopen", "wimbledon"):
        for g in ("W", "M"):
            s_ = p[(p["slam"] == slam) & (p["gender"] == g)]
            r = trend_per_decade(s_, "winners_ex_rate", weight="points", cluster="event", scale=100)
            bs.append({"slam": slam, "gender": g, "first_year": int(s_["year"].min()), "last_year": int(s_["year"].max()),
                       "winners_ex_per_100": 100 * s_["winners_ex"].sum() / s_["points"].sum(), **r})
    _save(pd.DataFrame(bs), "trends_winners_by_slam.csv")

    # ------------------------------------------------ source comparison and selection bias
    L = W.link_charting_to_pbp(c, p)
    comp_rows, rnd_rows = [], []
    for g in ("W", "M"):
        pg = p[p["gender"] == g]
        linked = L[L["pbp_match_id"].isin(pg["match_id"])]
        events = pg[pg["match_id"].isin(linked["pbp_match_id"])]["event"].unique()
        base = pg[pg["event"].isin(events)]                       # same events as the charted matches
        sub_p = pg[pg["match_id"].isin(linked["pbp_match_id"])]
        sub_c = c[c["match_id"].isin(linked["chart_match_id"])]
        for sample, df, cl in (("all_pbp", base, "event"), ("charted_pbp", sub_p, "event"), ("charted_chart", sub_c, "cluster")):
            for m, (num, den) in WIN_METRICS.items():
                r = ratio_ci(df[num], df[den], df[cl])
                comp_rows.append({"gender": g, "sample": sample, "metric": m, "rate": r["rate"], "lo": r["lo"],
                                  "hi": r["hi"], "n_matches": r["n"]})
        for sample, df in (("all_pbp", base), ("charted", sub_p)):
            shares = df["round"].value_counts(normalize=True)
            for rd in W.SLAM_ROUND.values():
                rnd_rows.append({"gender": g, "sample": sample, "round": rd, "share": float(shares.get(rd, 0.0))})
        for rd in W.SLAM_ROUND.values():
            s = base[base["round"] == rd]
            r = ratio_ci(s["winners_ex"], s["points"], s["event"])
            rnd_rows.append({"gender": g, "sample": "winners_ex_rate_all_pbp", "round": rd, "share": r["rate"]})
    comp = pd.DataFrame(comp_rows)
    _save(comp, "source_comparison.csv")
    _save(pd.DataFrame(rnd_rows), "round_mix_and_rates.csv")
    # round-reweighted charted subset: give each round its share among all Slam matches
    rw = []
    for g in ("W", "M"):
        pg = p[(p["gender"] == g) & p["match_id"].isin(L["pbp_match_id"])]
        base = p[(p["gender"] == g) & p["event"].isin(pg["event"].unique())]
        share = base["round"].value_counts(normalize=True)
        rates = pg.groupby("round").apply(lambda s: s["winners_ex"].sum() / s["points"].sum(), include_groups=False)
        ok = rates.index.intersection(share.index)
        rw.append({"gender": g, "charted_raw": float(pg["winners_ex"].sum() / pg["points"].sum()),
                   "charted_round_reweighted": float((rates[ok] * share[ok]).sum() / share[ok].sum()),
                   "all_matches": float(base["winners_ex"].sum() / base["points"].sum())})
    _save(pd.DataFrame(rw), "round_reweighting.csv")
    m = L.merge(c[["match_id", "points", "winners_ex", "aces", "ue"]].add_prefix("c_"), left_on="chart_match_id",
                right_on="c_match_id").merge(p[["match_id", "points", "winners_ex", "aces", "ue", "provider", "gender"]].add_prefix("p_"),
                                             left_on="pbp_match_id", right_on="p_match_id")
    agree = []
    for k in ("points", "winners_ex", "aces", "ue"):
        agree.append({"quantity": k, "charting_total": int(m[f"c_{k}"].sum()), "pbp_total": int(m[f"p_{k}"].sum()),
                      "correlation": float(m[f"c_{k}"].corr(m[f"p_{k}"])), "n_matches": len(m)})
    _save(pd.DataFrame(agree), "same_match_agreement.csv")

    sizes = {"tml_matches": int(len(d)), "tml_by_tour": d["tour"].value_counts().to_dict(),
             "slam_pbp_matches": int(len(p)), "charting_matches": int(len(c)),
             "charting_by_gender": c["gender"].value_counts().to_dict(), "linked_charting_pbp": int(len(L))}
    (RES / "sample_sizes.json").write_text(json.dumps(sizes, indent=1, sort_keys=True))

    # ------------------------------------------------ figures (main story: fig1-4; the rest is the appendix)
    for stale in FIG.glob("*.png"):
        stale.unlink()
    pick = lambda t, m: t[t["metric"] == m]  # noqa: E731
    wta_atp = lambda t: t.rename(columns={"gender": "tour"}).replace({"tour": {"W": "WTA", "M": "ATP"}})  # noqa: E731
    # Challenger grass: a handful of events a year (about 80 matches), too thin to draw as a trend line
    y_plot = y_surf[~((y_surf["tour"] == "Challenger") & (y_surf["surface"] == "Grass"))]
    plots.surface_panels(pick(y_plot, "ace_rate"), list(data.TOURS), "On the WTA and ATP tours, aces rose until the mid-2010s and have levelled off since",
                         "Aces per 100 serve points", FIG / "fig1_aces_by_surface.png", data.PARTIAL_YEAR)
    plots.surface_panels(pick(y_plot, "break_rate"), list(data.TOURS),
                         "Breaks of serve have slowly become rarer on the WTA and ATP tours",
                         "Breaks per 100 return games", FIG / "fig2_breaks_by_surface.png", data.PARTIAL_YEAR)
    plots.surface_panels(wta_atp(pick(p_y, "winners_ex_rate")), ["WTA", "ATP"],
                         "Slam winners (not counting aces) showed no clear change until about 2016, then edged down",
                         "Winners per 100 points", FIG / "fig3_winners_slams.png", None)
    plots.source_comparison(comp[comp["metric"] == "winners_ex_rate"], FIG / "fig4_source_comparison.png")
    plots.index_panels(idx, "Like for like, aces levelled off in the mid-2010s while breaks kept falling",
                       FIG / "figA1_like_for_like.png")
    plots.coverage_figure(pd.read_csv(RES / "coverage_serve_stats.csv"), data.START, FIG / "figA2_serve_stats_coverage.png")
    plots.surface_panels(wta_atp(pick(c_y, "winners_ex_rate")), ["WTA", "ATP"],
                         "In charted matches, clay courts show the most winners",
                         "Winners per 100 points", FIG / "figA3_winners_charting_by_surface.png", data.PARTIAL_YEAR)
    plots.charter_figure(c_ns_y, FIG / "figA4_charting_one_charter.png", data.PARTIAL_YEAR)
    plots.surface_panels(wta_atp(pick(p_y, "ue_rate")), ["WTA", "ATP"], "About a third of Slam points end in an unforced error",
                         "Unforced errors per 100 points", FIG / "figA5_unforced_slams.png", None)
    print(tr[tr["surface"] == "All"][["tour", "metric", "per_decade", "lo", "hi", "p"]].round(3).to_string(index=False))
    print(wt[wt["surface"] == "All"][["source", "gender", "metric", "per_decade", "lo", "hi", "p"]].round(3).to_string(index=False))
    print(comp[comp.metric == "winners_ex_rate"].round(4).to_string(index=False))


if __name__ == "__main__":
    np.random.seed(0)
    main()
