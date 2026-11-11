"""Validate the SvGms-based first-server inference against the point-by-point ground truth."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .inference import (parse_score, posterior_from_fit, posterior_w_first, serve_plan,
                        simulate_identification_null, svgms_fit)
from tennis.stats import cluster_prop_ci


def build_validation_frame(S: pd.DataFrame, links: pd.DataFrame, T: pd.DataFrame) -> pd.DataFrame:
    """One row per linked pbp match whose set 1 first server is known.

    truth_w_first: the TML match winner served the first point of the match (from pbp).
    score_agrees:  pbp set scores equal the TML score (sanity check of the link and of the pbp parse).
    category:      'identified' / 'ambiguous' / 'neither' by the SvGms rule, 'no score/stats' otherwise.
    """
    s1 = S[(S.SetNo == 1) & S.usable][["match_id", "fs"]]
    pbp_scores = (S.sort_values(["match_id", "SetNo"]).groupby("match_id")
                  .apply(lambda g: [(int(a), int(b)) for a, b in zip(g.g1, g.g2)], include_groups=False)
                  .rename("pbp_sets"))
    lk = links[links.link_status == "linked"].merge(T, on="tml_row").merge(s1, on="match_id")
    lk = lk.join(pbp_scores, on="match_id")
    rows = []
    for r in lk.itertuples():
        truth = (r.fs == 1) == bool(r.p1_is_tml_winner)
        sets = parse_score(r.score)
        rec = dict(match_id=r.match_id, gender=r.gender, year=r.year, slam=r.slam, truth_w_first=truth,
                   score=r.score, category="no score/stats", score_agrees=False, post=np.nan)
        if sets is not None:
            # pbp sets from the TML winner's point of view
            pb = [(a, b) if r.p1_is_tml_winner else (b, a) for a, b in r.pbp_sets]
            rec["score_agrees"] = pb == [(a, b) for a, b, _ in sets]
        stats_ok = sets is not None and all(pd.notna(getattr(r, c)) for c in
                                            ("w_SvGms", "l_SvGms", "w_svpt", "l_svpt", "w_bpFaced", "l_bpFaced")) \
            and r.w_svpt > 0 and r.l_svpt > 0
        if stats_ok:
            fw, fl = svgms_fit(sets, r.w_SvGms, r.l_SvGms)
            rec["category"] = {2: "ambiguous", 1: "identified", 0: "neither"}[int(fw) + int(fl)]
            rec["fit_w"], rec["fit_l"] = fw, fl
            pw = (r.w_1stWon + r.w_2ndWon) / r.w_svpt
            pl = (r.l_1stWon + r.l_2ndWon) / r.l_svpt
            brk_w = r.l_bpFaced - r.l_bpSaved
            sl_w, sl_l, bl_w, bl_l = posterior_w_first(sets, pw, pl, brk_w)
            rec["post"] = posterior_from_fit(fw, fl, sl_w, sl_l, bl_w, bl_l)
            rec["post_model_only"] = bl_w / (bl_w + bl_l) if bl_w + bl_l > 0 else np.nan
            rec["pw"], rec["pl"], rec["best_of"] = pw, pl, int(r.best_of)
            rec["sets"] = sets
        rows.append(rec)
    V = pd.DataFrame(rows)
    V["inferred_w_first"] = np.where(V.category == "identified", V.get("fit_w", False), np.nan)
    return V


def accuracy_table(V: pd.DataFrame) -> pd.DataFrame:
    """Per gender: counts per category and accuracy of the identified calls and of the posterior."""
    rows = []
    for gname, g in [("Men", V[V.gender == "M"]), ("Women", V[V.gender == "W"]), ("All", V)]:
        idf = g[g.category == "identified"]
        amb = g[g.category == "ambiguous"]
        ok_post = amb.post_model_only.notna()
        pa = amb.post_model_only[ok_post]
        ta = amb.truth_w_first[ok_post].astype(float)
        rows.append(dict(
            gender=gname, n_linked=len(g), n_with_stats=int((g.category != "no score/stats").sum()),
            score_agrees=float(g.score_agrees[g.category != "no score/stats"].mean()) if len(g) else np.nan,
            n_identified=len(idf), n_ambiguous=len(amb), n_neither=int((g.category == "neither").sum()),
            identified_accuracy=float((idf.fit_w == idf.truth_w_first).mean()) if len(idf) else np.nan,
            identified_wrong=int((idf.fit_w != idf.truth_w_first).sum()),
            ambiguous_posterior_accuracy=float(((pa > 0.5) == (ta > 0.5))[pa != 0.5].mean()) if len(pa) else np.nan,
            ambiguous_posterior_brier=float(((pa - ta) ** 2).mean()) if len(pa) else np.nan,
            ambiguous_truth_share_w_first=float(ta.mean()) if len(ta) else np.nan,
            ambiguous_mean_posterior=float(pa.mean()) if len(pa) else np.nan))
    return pd.DataFrame(rows)


def calibration_table(V: pd.DataFrame, bins: int = 10) -> pd.DataFrame:
    """Calibration of the model posterior (score + breaks, SvGms ignored) on all matches with stats."""
    d = V[V.post_model_only.notna()]
    edges = np.linspace(0, 1, bins + 1)
    idx = np.clip(np.digitize(d.post_model_only, edges) - 1, 0, bins - 1)
    out = d.assign(bin=idx).groupby("bin").agg(mean_pred=("post_model_only", "mean"),
                                                obs=("truth_w_first", "mean"), n=("truth_w_first", "size"))
    out["bin_lo"] = edges[out.index]
    return out.reset_index(drop=True)


def _per_set(V: pd.DataFrame, weight: str) -> pd.DataFrame:
    """Expand matches to sets; y = P(first server of set wins) under weight P(H_w) in column ``weight``."""
    recs = []
    for r in V.itertuples():
        w = getattr(r, weight)
        if r.category in ("no score/stats", "neither") or pd.isna(w):
            continue
        pw_, pl_ = serve_plan(r.sets, True), serve_plan(r.sets, False)
        for k, ((a, b, _), hw, hl) in enumerate(zip(r.sets, pw_, pl_)):
            w_won = a > b
            y = w * float(w_won == hw[0]) + (1 - w) * float(w_won == hl[0])
            recs.append((r.match_id, k + 1, y))
    return pd.DataFrame(recs, columns=["match_id", "set_no", "y"])


def compare_estimators(V: pd.DataFrame, sim_reps: int, seed: int) -> pd.DataFrame:
    """On the same matches (complete, with stats, not 'neither'): truth vs estimators A, B and B*."""
    rng = np.random.default_rng(seed)
    rows = []
    for gname, g in [("Men", V[V.gender == "M"]), ("Women", V[V.gender == "W"])]:
        g = g[g.category.isin(["identified", "ambiguous"])].copy()
        if len(g) == 0:
            continue
        g["truth_w"] = g.truth_w_first.astype(float)
        g["ident_w"] = np.where(g.category == "identified", g.fit_w.astype(float), np.nan)
        per = {"truth (pbp)": _per_set(g, "truth_w"), "A: posterior (all matches)": _per_set(g, "post"),
               "B: SvGms-identified only": _per_set(g, "ident_w")}
        # null simulation for B*
        sim = pd.DataFrame(simulate_identification_null(g.pw.values, g.pl.values, g.best_of.values, sim_reps, rng),
                           columns=["m", "set_no", "ident", "win"])
        for sg, f in (("set 1", lambda d: d.set_no == 1), ("sets 2+", lambda d: d.set_no > 1), ("all sets", lambda d: d.set_no > 0)):
            res = {}
            for name, d in per.items():
                dd = d[f(d)]
                r = cluster_prop_ci(dd.y.values, dd.match_id.values)
                res[name] = r
                rows.append(dict(gender=gname, set_group=sg, estimator=name, p=r["p"], lo=r["lo"], hi=r["hi"],
                                 n_sets=r["n"], n_matches=r["n_clusters"]))
            ss = sim[f(sim)]
            null_all = ss.win.mean()
            null_id = ss[ss.ident].win.mean()
            b = res["B: SvGms-identified only"]["p"]
            rows.append(dict(gender=gname, set_group=sg, estimator="B*: B minus null selection bias",
                             p=b - null_id + null_all, lo=np.nan, hi=np.nan,
                             n_sets=res["B: SvGms-identified only"]["n"], n_matches=res["B: SvGms-identified only"]["n_clusters"]))
    return pd.DataFrame(rows)


def svgms_truth_check(V: pd.DataFrame, G: pd.DataFrame, links: pd.DataFrame, T: pd.DataFrame,
                      P: pd.DataFrame | None = None) -> pd.DataFrame:
    """Compare TML (w_SvGms, l_SvGms) with the true numbers of regular service games from the pbp.

    Returns one row per match with stats: true counts, TML counts and an error type.  If the points
    ``P`` are given, TML serve points (w_svpt, l_svpt) are also compared with pbp serve-point counts:
    this tests whether a wrong SvGms comes from a mis-paired / swapped stats row (svpt would then be
    wrong or swapped too) or from the SvGms column itself (svpt still right).
    """
    reg = G[~G.is_tb].groupby(["match_id", "first_server"]).size().unstack(fill_value=0)
    reg = reg.reindex(columns=[1, 2], fill_value=0).rename(columns={1: "sv1", 2: "sv2"})
    ntb = G[G.is_tb].groupby("match_id").size().rename("n_tb")
    X = (V[V.category != "no score/stats"][["match_id", "gender", "year", "slam", "category"]]
         .merge(links[["match_id", "tml_row", "p1_is_tml_winner"]], on="match_id")
         .merge(T[["tml_row", "w_SvGms", "l_SvGms"]], on="tml_row").join(reg, on="match_id").join(ntb, on="match_id"))
    X["n_tb"] = X.n_tb.fillna(0).astype(int)
    X["true_w"] = np.where(X.p1_is_tml_winner, X.sv1, X.sv2)
    X["true_l"] = np.where(X.p1_is_tml_winner, X.sv2, X.sv1)
    dw, dl = X.w_SvGms - X.true_w, X.l_SvGms - X.true_l
    X["svgms_exact"] = (dw == 0) & (dl == 0)
    if P is not None:
        sp = P.groupby(["match_id", "PointServer"]).size().unstack(fill_value=0).reindex(columns=[1, 2], fill_value=0)
        sp = sp.rename(columns={1: "pts1", 2: "pts2"})
        X = X.join(sp, on="match_id").merge(T[["tml_row", "w_svpt", "l_svpt"]], on="tml_row")
        pw = np.where(X.p1_is_tml_winner, X.pts1, X.pts2)
        pl = np.where(X.p1_is_tml_winner, X.pts2, X.pts1)
        X["svpt_exact"] = (X.w_svpt == pw) & (X.l_svpt == pl)
        X["svpt_within3"] = ((X.w_svpt - pw).abs() <= 3) & ((X.l_svpt - pl).abs() <= 3)
        X["svpt_swapped"] = (X.w_svpt == pl) & (X.l_svpt == pw) & (pw != pl)
    X["error_type"] = np.select(
        [X.svgms_exact, (dw + dl == 0), (dw + dl == X.n_tb) & (X.n_tb > 0), (dw + dl) > 0],
        ["exact", "same total, one game moved between players", "tiebreaks counted as service games",
         "total too high (other)"], "total too low")
    return X
