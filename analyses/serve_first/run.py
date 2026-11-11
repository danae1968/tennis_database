"""Serve first: regenerates every table in results/ and every figure in figures/.

    .venv/bin/python analyses/serve_first/run.py        (or: make serve_first)

Question: what is the probability that a player wins a set, given that they served the first game
of that set?  Ground truth from Grand Slam point-by-point data (2011-2024, singles).
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

if __package__ in (None, ""):                       # run as a script: make ``analyses.*`` importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from analyses.serve_first import plots as F  # noqa: E402
from analyses.serve_first.estimate import (build_analysis_table, by_set_number, coin_toss_balance,  # noqa: E402
                                           heterogeneity_tests, previous_winner_contrast, selection_table,
                                           set_endings, strength_models, summarise)
from analyses.serve_first.linking import link_matches, load_tml_slams  # noqa: E402
from analyses.serve_first.sets import add_match_context, build_games, build_sets, flag_usable, renumber_games  # noqa: E402
from analyses.serve_first.validation import (accuracy_table, build_validation_frame, calibration_table,  # noqa: E402
                                             compare_estimators, svgms_truth_check)
from tennis.load import load_slam_matches, load_slam_points  # noqa: E402
from tennis.paths import analysis_dirs  # noqa: E402

RESULTS_DIR, FIG_DIR, CACHE_DIR = analysis_dirs("serve_first")
SEED = 20261110
SIM_REPS = 4
GOOD_SVGMS_YEARS = [2011, 2012, 2013, 2014, 2015, 2024]


def _save(df: pd.DataFrame, name: str) -> None:
    df.to_csv(RESULTS_DIR / name, index=False, float_format="%.5f")


def main() -> None:
    t0 = time.time()
    np.random.seed(SEED)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------------- load + clean
    M = load_slam_matches()
    P, load_info = load_slam_points(cache_dir=CACHE_DIR)
    P = renumber_games(P)
    G = build_games(P)
    S = flag_usable(add_match_context(build_sets(P, G), M))
    T = load_tml_slams(sorted(M.year.unique()))
    L = link_matches(M, T)
    D = build_analysis_table(S, P, L, T)

    # ---------------------------------------------------------------- data quality
    nxt = S[S.usable & (S.predicted_fs > 0)]
    fs_known = S.fs > 0
    dq = {
        **load_info,
        "matches_in_files": int(len(M)),
        "matches_with_points": int(P.match_id.nunique()),
        "matches_without_points": int(len(M) - P.match_id.nunique()),
        "matches_cumulative_game_numbering (Infosys AO/FO 2018-21)": int(S[S.cumulative].match_id.nunique()),
        "sets_total": int(len(S)),
        "sets_usable": int(S.usable.sum()),
        "sets_excluded_by_reason": S[~S.usable].exclude_reason.value_counts().to_dict(),
        "matches_incomplete (retired or truncated)": int((~S.groupby("match_id").complete_match.first()).sum()),
        "games_with_server_change_outside_tiebreak": int(G.server_error.sum()),
        "regular_games_with_<4_points (missing points)": int(G.short_game.sum()),
        "sets_with_gaps_in_game_numbers": int((S.n_missing_games > 0).sum()),
        "sets_game1_missing_first_server_from_parity": int(((S.fs_direct == 0) & fs_known).sum()),
        "sets_with_parity_vote_conflicts": int((S.parity_conflicts > 0).sum()),
        "sets_where_file_SetWinner_disagrees_with_counted_games": int(S.sw_disagree.sum()),
        "cross_set_rule_agreement": float((nxt.predicted_fs == nxt.fs).mean()),
        "cross_set_rule_n": int(len(nxt)),
        "within_set_rule_agreement (games whose server matches odd/even rule)":
            float(1 - S.parity_conflicts.sum() / G[~G.server_error].shape[0]),
        "pbp_matches_linked_to_tml": L.link_status.value_counts().to_dict(),
        "linked_sets_with_imputed_rank": int((D.rank1_imputed | D.rank2_imputed).sum()),
    }
    fmt = S[S.usable & S.is_final_set].assign(hi=lambda d: d[["g1", "g2"]].max(axis=1), lo=lambda d: d[["g1", "g2"]].min(axis=1))
    final_fmt = fmt.groupby(["slam", "year"]).apply(lambda d: pd.Series({
        "deciding_sets": len(d), "tb_7_6": int(((d.hi == 7) & (d.lo == 6)).sum()),
        "tb_13_12": int(((d.hi == 13) & (d.lo == 12)).sum()), "advantage_beyond_7_5": int(((d.hi > 7) & (d.hi - d.lo == 2)).sum()),
        "longest": f"{int(d.hi.max())}-{int(d.lo[d.hi.idxmax()])}"}), include_groups=False).reset_index()
    _save(final_fmt, "final_set_formats.csv")

    # ---------------------------------------------------------------- task 1: direct estimates
    tabs = [summarise(D, None, "overall"), summarise(D, ["gender"], "gender"), summarise(D, ["slam"], "slam"),
            summarise(D, ["surface"], "surface"), summarise(D, ["gender", "slam"], "gender x slam"),
            summarise(D, ["year"], "year"), summarise(D, ["gender", "year"], "gender x year")]
    est = pd.concat(tabs, ignore_index=True)
    _save(est, "estimates_by_group.csv")
    bs = by_set_number(D)
    _save(bs, "by_set_number.csv")
    sens = summarise(D[D.complete_match], ["gender"], "complete matches only")
    _save(sens, "sensitivity_complete_matches.csv")

    # ---------------------------------------------------------------- task 2: strength
    ct = coin_toss_balance(D)
    _save(ct, "coin_toss_balance.csv")
    sm = strength_models(D)
    _save(sm, "strength_models.csv")
    sel = selection_table(D)
    _save(sel, "selection.csv")
    pwc = previous_winner_contrast(D)
    _save(pwc, "previous_winner_contrast.csv")
    _save(heterogeneity_tests(D), "heterogeneity_tests.csv")
    ends = set_endings(D, G)
    _save(ends, "set_endings.csv")

    # ---------------------------------------------------------------- task 3: validation
    V = build_validation_frame(S, L, T)
    acc = pd.concat([accuracy_table(V).assign(years="all"),
                     accuracy_table(V[V.year.isin(GOOD_SVGMS_YEARS)]).assign(years="2011-15, 2024"),
                     accuracy_table(V[V.year.between(2016, 2023)]).assign(years="2016-23")], ignore_index=True)
    _save(acc, "validation_accuracy.csv")
    _save(calibration_table(V), "validation_posterior_calibration.csv")
    X = svgms_truth_check(V, G, L, T, P)
    era = np.where(X.year.between(2016, 2023), "2016-23", "2011-15, 2024")
    svpt = X.assign(era=era, svgms=np.where(X.svgms_exact, "SvGms correct", "SvGms wrong")).groupby(["era", "svgms"]).agg(
        n=("svpt_exact", "size"), svpt_exact=("svpt_exact", "mean"), svpt_within3=("svpt_within3", "mean"),
        svpt_swapped=("svpt_swapped", "mean")).reset_index()
    _save(svpt, "svpt_pairing_check.csv")
    svyear = X.groupby(["gender", "year"]).agg(n=("svgms_exact", "size"), svgms_exact=("svgms_exact", "mean")).reset_index()
    _save(svyear, "svgms_exact_by_year.csv")
    _save(X.groupby(["gender", "error_type"]).size().rename("n").reset_index(), "svgms_error_types.csv")
    cmp_all = compare_estimators(V, SIM_REPS, SEED).assign(years="all")
    cmp_good = compare_estimators(V[V.year.isin(GOOD_SVGMS_YEARS)], SIM_REPS, SEED).assign(years="2011-15, 2024")
    cmp = pd.concat([cmp_all, cmp_good], ignore_index=True)
    _save(cmp, "validation_estimators.csv")

    # ---------------------------------------------------------------- figures
    for stale in FIG_DIR.glob("*.png"):           # figure names follow README order; drop old names
        stale.unlink()
    F.fig_raw_vs_adjusted(sm, FIG_DIR / "fig1_raw_vs_adjusted.png")
    F.fig_by_set_number(bs[bs.gender != "All"], FIG_DIR / "fig2_by_set_number.png")
    F.fig_gender_slam(est[est.table == "gender x slam"], FIG_DIR / "fig3_gender_slam.png")
    F.fig_how_sets_end(ends, FIG_DIR / "fig4_how_sets_end.png")
    F.fig_prev_set(sel, pwc, FIG_DIR / "fig5_previous_set.png")
    F.fig_validation(V, svyear, cmp_all, FIG_DIR / "fig6_validation.png")
    F.fig_over_time(est[est.table == "year"], FIG_DIR / "figA1_over_time.png")

    # ---------------------------------------------------------------- headline
    def pick(df, **kw):
        m = np.ones(len(df), bool)
        for k, v in kw.items():
            m &= (df[k] == v).values
        r = df[m].iloc[0]
        return {k: (float(r[k]) if isinstance(r[k], (float, np.floating)) else int(r[k]))
                for k in r.index if k in ("p", "lo", "hi", "n_sets", "n_matches", "p_adj", "n")}
    head = {
        "raw": {sg: pick(est[est.table == "overall"], set_group=sg) for sg in ("set 1", "sets 2+", "all sets")},
        "raw_by_gender": {g: {sg: pick(est[est.table == "gender"], gender=g, set_group=sg) for sg in ("set 1", "sets 2+")}
                          for g in ("M", "W")},
        "rank_adjusted": {sg: pick(sm, gender="All", set_group=sg, model="pre-match rank") for sg in ("set 1", "sets 2+")},
        "rank_and_previous_set_adjusted_sets2plus": pick(sm, gender="All", set_group="sets 2+", model="rank + previous set result"),
        "coin_toss_share_fs_better_ranked": pick(ct, gender="All"),
        "validation_accuracy": acc.to_dict(orient="records"),
        "data_quality": dq,
    }
    with open(RESULTS_DIR / "headline.json", "w") as fh:
        json.dump(head, fh, indent=2, default=lambda o: o.item() if hasattr(o, "item") else str(o))

    pd.set_option("display.width", 200)
    print(est[est.table == "overall"].round(4).to_string(index=False))
    print(sm[sm.gender == "All"][["set_group", "model", "p_adj", "lo", "hi", "n"]].round(4).to_string(index=False))
    print(acc[["years", "gender", "n_with_stats", "n_identified", "identified_accuracy", "n_neither"]].round(4).to_string(index=False))
    print(cmp[cmp.gender == "Men"][["years", "set_group", "estimator", "p", "lo", "hi"]].round(4).to_string(index=False))
    print(f"done in {time.time() - t0:.1f} s")   # not written to headline.json, so outputs stay reproducible


if __name__ == "__main__":
    main()
