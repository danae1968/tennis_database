"""Top-10 profiles (WTA and ATP): hold/break, winners/unforced errors, pressure points.

    .venv/bin/python analyses/top10_profiles/run.py        (or: make top10_profiles)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from analyses.top10_profiles import data, metrics, plots  # noqa: E402
from tennis.paths import analysis_dirs  # noqa: E402

RES_DIR, FIG_DIR, _ = analysis_dirs("top10_profiles")
TOURS = ["WTA", "ATP"]
SEED = 20261111
MIN_CHARTED = 5
MIN_CHARTED_TEST = 10      # a match bootstrap is unreliable with fewer charted matches: those players are not tested
# Explicit, documented override of the staleness rule (decision of the user); nobody else is exempt.
FORCE_INCLUDE = {"Jannik Sinner": "user confirmed still top 10 as of Nov 2026; only matches up to his last one (July 2026) are in the window"}


def main() -> None:
    summary: dict = {"window_days": data.WINDOW_DAYS, "levels_included": sorted(data.TOUR_LEVELS),
                     "challengers_included": False, "qualifying_included": False}
    prof, surf_rows, tourwide, hb_ref, press_ref, kp_ref, tour_surf = [], [], {}, {}, {}, {}, []
    top_all, charted, regulars, sel = {}, {}, {}, {}
    for ti, tour in enumerate(TOURS):
        d = data.load_tour(tour)
        top, info = data.current_top10(d, FORCE_INCLUDE)
        asof = pd.Timestamp(info["as_of"])
        L = data.long_table(d, asof)
        summary[tour] = {**info, "window_start_exclusive": str((asof - pd.Timedelta(days=data.WINDOW_DAYS)).date()),
                         "matches_in_window": int(len(L) // 2),
                         "service_game_flags": L[L.id == L.id].flag.value_counts().div(2).round().astype(int).to_dict()}
        top["label"] = top.name.map(plots.short)
        regulars[tour] = (metrics.player_table(L), set(top.id))
        sel[tour] = metrics.selection_check(*regulars[tour])
        top_all[tour] = top
        # tour-wide references (all players, same window)
        hb_ref[tour] = metrics.hold_break(L, SEED)
        press_ref[tour] = metrics.pressure(L, SEED)
        for sf in metrics.SURFACES:
            S = L[L.surface == sf]
            if len(S):
                tour_surf.append({"tour": tour, "surface": sf, "matches": len(S) // 2,
                                  **metrics.hold_break(S, SEED), **{f"p_{k}": v for k, v in metrics.pressure(S, SEED).items()}})
        # per player
        for i, t in top.iterrows():
            P = L[L.id == t.id]
            rec = dict(tour=tour, pos=int(t.pos), name=t["name"], rank_at_last_match=int(t.rank_at_last_match),
                       last_match=str(t.last_match.date()), matches=len(P),
                       **metrics.hold_break(P, SEED + i), **{f"p_{k}": v for k, v in metrics.pressure(P, SEED + i).items()},
                       **metrics.tb_deciding(P))
            prof.append(rec)
            for sf in metrics.SURFACES:
                S = P[P.surface == sf]
                if len(S):
                    surf_rows.append(dict(tour=tour, name=t["name"], surface=sf, **metrics.hold_break(S, SEED + i)))
        # charting
        names = dict(zip(top.id, top.name))
        ov, ks, kr = data.charting_window(tour, asof, names)
        charted[tour] = (ov, ks, kr)
    P = pd.DataFrame(prof)
    P.to_csv(RES_DIR / "player_profiles.csv", index=False)
    pd.DataFrame(surf_rows).to_csv(RES_DIR / "hold_break_by_surface.csv", index=False)
    pd.DataFrame(tour_surf).to_csv(RES_DIR / "tourwide_by_surface.csv", index=False)
    pd.DataFrame([{"tour": t, **hb_ref[t], **{f"p_{k}": v for k, v in press_ref[t].items()}} for t in TOURS]).to_csv(
        RES_DIR / "tour_reference.csv", index=False)

    # ---- charting tables
    wue, kp = [], []
    kp_tour = {}
    for tour in TOURS:
        ov, ks, kr = charted[tour]
        for i, t in top_all[tour].iterrows():
            o = ov[ov.id == t.id]
            if o.empty:
                continue
            ids = set(o.match_id)
            w = metrics.winners_ue(o, SEED + i)
            wue.append(dict(tour=tour, name=t["name"], label=t["label"], **w, few=w["charted_matches"] < MIN_CHARTED))
            k = metrics.keypoints(o, ks[(ks.id == t.id) & ks.match_id.isin(ids)], kr[(kr.id == t.id) & kr.match_id.isin(ids)], SEED + i)
            kp.append(dict(tour=tour, name=t["name"], label=t["label"], few=k["n_matches"] < MIN_CHARTED, **k))
        # tour-wide charted reference (all charted players in the window)
        all_w = metrics.winners_ue(ov, SEED)
        kp_tour[tour] = metrics.keypoints(ov, ks[ks.match_id.isin(set(ov.match_id))], kr[kr.match_id.isin(set(ov.match_id))], SEED)
        kp_tour[tour]["w100"], kp_tour[tour]["u100"] = all_w["w100"], all_w["u100"]
        kp_tour[tour]["charted_player_matches"] = all_w["charted_matches"]
    # ---- pressure comparisons with the tour-average gap, Holm over ALL comparisons (TML break points + charted key points)
    rows = []
    for _, r in P.iterrows():
        for key, lab in (("save_gap", "BP saved vs serve points (TML)"), ("conv_gap", "BP converted vs return points (TML)")):
            rows.append(dict(tour=r.tour, name=r["name"], family="TML", measure=lab, gap=r[f"p_{key}"], tour_gap=press_ref[r.tour][key],
                             sd=r[f"p_{key}_sd"]))
    for _, r in pd.DataFrame(kp).iterrows():
        if r.n_matches < MIN_CHARTED_TEST:
            continue
        for rw in ("BP", "GP", "Deuce", "BPO", "GPF", "DeuceR"):
            rows.append(dict(tour=r.tour, name=r["name"], family="charted", measure=f"{rw} vs overall rate (charted)", gap=r[f"{rw}_gap"],
                             tour_gap=kp_tour[r.tour][f"{rw}_gap"], sd=r[f"{rw}_gap_sd"]))
    T = metrics.gap_tests(rows)
    T.to_csv(RES_DIR / "pressure_tests_holm.csv", index=False)
    summary["pressure_tests"] = {"n_comparisons": int(len(T)), "n_p_below_0.05_uncorrected": int((T.p < 0.05).sum()),
                                 "n_p_holm_below_0.05": int((T.p_holm < 0.05).sum()), "min_p_holm": float(T.p_holm.min()),
                                 "largest": T.reindex(T["diff"].abs().sort_values(ascending=False).index).head(5)[["tour", "name", "measure", "diff", "p", "p_holm"]].to_dict("records")}
    pd.DataFrame([{"tour": t, **sel[t]} for t in TOURS]).to_csv(RES_DIR / "selection_check.csv", index=False)
    W = pd.DataFrame(wue)
    K = pd.DataFrame(kp)
    summary["winners_unforced_corr"] = {}
    for t in TOURS:
        g = W[W.tour == t]
        r_ = float(g.w100.corr(g.u100))
        summary["winners_unforced_corr"][t] = dict(r=r_, ci=metrics.fisher_ci(r_, len(g)), n=int(len(g)))
    W.to_csv(RES_DIR / "winners_unforced_charted.csv", index=False)
    K.to_csv(RES_DIR / "charted_key_points.csv", index=False)
    pd.DataFrame([{"tour": t, **v} for t, v in kp_tour.items()]).to_csv(RES_DIR / "charted_tour_reference.csv", index=False)
    summary["charted_tour_reference"] = {t: {k: float(v) for k, v in kp_tour[t].items() if k in ("w100", "u100", "charted_player_matches")} for t in TOURS}

    # ---- figures
    fr = {t: P[P.tour == t].assign(label=lambda x: x.name.map(plots.short)).reset_index(drop=True) for t in TOURS}
    plots.scatter_two(fr, "hold", "brk", "Top players get there by different routes: some serve best, some return best",
                      "Service games held", "Return games won (breaks)",
                      {t: (hb_ref[t]["hold"], hb_ref[t]["brk"]) for t in TOURS}, ("tour average hold", "tour average break"), FIG_DIR / "hold_vs_break.png")
    surf = pd.DataFrame(surf_rows).merge(P[["name", "tour"]], on=["name", "tour"])
    surf_t = {t: surf[surf.tour == t] for t in TOURS}
    tsf = pd.DataFrame(tour_surf)
    ref = {(r.tour, r.surface): (r.hold, r.brk) for r in tsf.itertuples()}
    plots.surface_scatter(surf_t, metrics.SURFACES, ref, FIG_DIR / "hold_vs_break_by_surface.png")

    Wf = {t: W[W.tour == t].reset_index(drop=True) for t in TOURS}
    for t in TOURS:
        Wf[t]["label"] = [f"{plots.short(n)} ({k}){'*' if f else ''}" for n, k, f in zip(Wf[t].name, Wf[t].charted_matches, Wf[t].few)]
    plots.scatter_two(Wf, "u100", "w100", "Hitting more winners tends to come with more errors, but with ten players the link is loose",
                      "Unforced errors per 100 points", "Winners per 100 points",
                      {t: (kp_tour[t]["u100"], kp_tour[t]["w100"]) for t in TOURS}, ("all charted players", "all charted players"),
                      FIG_DIR / "winners_vs_unforced.png", scale=1.0, hollow_col="few", pct=False,
                      hollow_note=f"fewer than {MIN_CHARTED} charted matches")

    def rows_for(prefixes):
        return [[(fr[t], t, pre, press_ref[t][ref_key], f"{t}: {ttl}") for t in TOURS] for pre, ref_key, ttl in prefixes]
    gap = P.assign(save_gap=P.p_save_gap, save_gap_lo=P.p_save_gap_lo, save_gap_hi=P.p_save_gap_hi,
                   conv_gap=P.p_conv_gap, conv_gap_lo=P.p_conv_gap_lo, conv_gap_hi=P.p_conv_gap_hi)
    fr = {t: gap[gap.tour == t].assign(label=lambda x: x.name.map(plots.short)).reset_index(drop=True) for t in TOURS}
    plots.dotwhisker_grid(rows_for([("save_gap", "save_gap", "break points saved vs serve points won"),
                                    ("conv_gap", "conv_gap", "break points converted vs return points won")]),
                          "Most top players' break-point results sit close to the tour average once their own level is allowed for",
                          ["Break points saved minus serve points won overall (percentage points)",
                           "Break points converted minus return points won overall (percentage points)"],
                          FIG_DIR / "pressure_vs_baseline.png", xlim_pad=2.0)
    for t in TOURS:
        fr[t]["tbp"], fr[t]["tbp_lo"], fr[t]["tbp_hi"] = fr[t].tb_pct * 100, fr[t].tb_lo * 100, fr[t].tb_hi * 100
        fr[t]["dcp"], fr[t]["dcp_lo"], fr[t]["dcp_hi"] = fr[t].dec_pct * 100, fr[t].dec_lo * 100, fr[t].dec_hi * 100
        fr[t]["label"] = [f"{plots.short(n)} ({a}/{b})" for n, a, b in zip(fr[t].name, fr[t].tb_won, fr[t].tb_played)]
    f2 = {t: fr[t].assign(label=[f"{plots.short(n)} ({a}/{b})" for n, a, b in zip(fr[t].name, fr[t].dec_won, fr[t].dec_played)]) for t in TOURS}
    plots.dotwhisker_grid([[(fr[t], t, "tbp", None, f"{t}: tiebreaks won (won/played)") for t in TOURS],
                           [(f2[t], t, "dcp", None, f"{t}: deciding sets won (won/played)") for t in TOURS]],
                          "Most top players win more than half their tiebreaks and deciding sets, but the samples are small",
                          ["Tiebreaks won", "Deciding sets won"], FIG_DIR / "tiebreaks_deciding_sets.png",
                          xlim_pad=3.0, zero=50.0, zero_label="50%", pct_axis=True)

    plots.regulars_scatter(regulars, FIG_DIR / "hold_vs_break_all_players.png")

    # charted key points figure
    kfr = {t: K[K.tour == t].reset_index(drop=True) for t in TOURS}
    plots.keypoints_figure(kfr, kp_tour, MIN_CHARTED, FIG_DIR / "charted_key_points.png",
                           "Key-point results differ from players' usual level by a few points, mostly within the noise")

    summary["profiles_csv"] = "results/player_profiles.csv"
    (RES_DIR / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
