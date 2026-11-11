"""Estimation of P(win set | served first) from the point-by-point ground truth."""
from __future__ import annotations

import numpy as np
import pandas as pd

from tennis.stats import cluster_prop_ci, logit_cluster

UNRANKED = 1500.0   # rank imputed for unranked players (wild cards, protected ranking returns)


def serve_point_stats(P: pd.DataFrame) -> pd.DataFrame:
    """Serve points played / won per (match, set, server)."""
    d = P.assign(won=(P.PointWinner == P.PointServer).astype(int))
    return d.groupby(["match_id", "SetNo", "PointServer"]).agg(sv=("won", "size"), svw=("won", "sum")).reset_index()


def build_analysis_table(S: pd.DataFrame, P: pd.DataFrame, links: pd.DataFrame, T: pd.DataFrame) -> pd.DataFrame:
    """Per usable set: outcome and strength covariates, all from the first server's point of view.

    Covariates (antisymmetric, positive = favours the first server):
      d_logrank   ln(rank_opp) - ln(rank_fs), pre-tournament ranks from TML (unranked -> 1500)
      prev        +1 if the first server won the previous set, -1 if they lost it (0 in set 1)
      d_spw_loo   first server's minus opponent's serve-point win rate in the *other* sets of the match
                  (leave-this-set-out in-match form; NaN for one-set matches)
    """
    D = S[S.usable].copy()
    D["opp"] = 3 - D.fs
    D["y"] = D.fs_won.astype(int)
    # ranks
    lk = links[links.link_status == "linked"].merge(
        T[["tml_row", "winner_rank", "loser_rank", "winner_rank_points", "loser_rank_points"]], on="tml_row")
    r1 = np.where(lk.p1_is_tml_winner, lk.winner_rank, lk.loser_rank)
    r2 = np.where(lk.p1_is_tml_winner, lk.loser_rank, lk.winner_rank)
    rk = pd.DataFrame({"match_id": lk.match_id, "rank1": r1, "rank2": r2})
    D = D.merge(rk, on="match_id", how="left")
    D["linked"] = D.rank1.notna() | D.rank2.notna() | D.match_id.isin(lk.match_id)
    for c in ("rank1", "rank2"):
        D[c] = D[c].astype(float)
        D[c + "_imputed"] = D.linked & D[c].isna()
        D[c] = np.where(D[c + "_imputed"], UNRANKED, D[c])
    rank_fs = np.where(D.fs == 1, D.rank1, D.rank2)
    rank_op = np.where(D.fs == 1, D.rank2, D.rank1)
    D["d_logrank"] = np.log(rank_op) - np.log(rank_fs)
    D["fs_better_ranked"] = np.where(np.isnan(D.d_logrank), np.nan, (D.d_logrank > 0).astype(float))
    # previous set
    D["prev"] = np.where(D.set_no == 1, 0, np.where(D.prev_winner == D.fs, 1, np.where(D.prev_winner > 0, -1, np.nan)))
    D["prev_even"] = np.where(D.set_no == 1, np.nan, (D.prev_games % 2 == 0).astype(float))
    # leave-set-out serve-point win rates
    sp = serve_point_stats(P)
    tot = sp.groupby(["match_id", "PointServer"])[["sv", "svw"]].sum().rename(columns={"sv": "sv_tot", "svw": "svw_tot"})
    sp = sp.join(tot, on=["match_id", "PointServer"])
    sp["rate_loo"] = (sp.svw_tot - sp.svw) / (sp.sv_tot - sp.sv).replace(0, np.nan)
    piv = sp.pivot_table(index=["match_id", "SetNo"], columns="PointServer", values="rate_loo").rename(columns={1: "spw1", 2: "spw2"})
    D = D.join(piv, on=["match_id", "SetNo"])
    D["d_spw_loo"] = np.where(D.fs == 1, D.spw1 - D.spw2, D.spw2 - D.spw1)
    D["set_group"] = np.where(D.set_no == 1, "set 1", "sets 2+")
    return D


def summarise(D: pd.DataFrame, by: list[str] | None = None, label: str = "") -> pd.DataFrame:
    """P(first server wins) with match-clustered Wilson CIs, for set 1 / sets 2+ / all sets."""
    rows = []
    groups = [((), D)] if not by else D.groupby(by, sort=True)
    for key, g in groups:
        key = key if isinstance(key, tuple) else (key,)
        for sg, gg in (("set 1", g[g.set_no == 1]), ("sets 2+", g[g.set_no > 1]), ("all sets", g)):
            if len(gg) == 0:
                continue
            r = cluster_prop_ci(gg.y.values, gg.match_id.values)
            row = {"table": label, "set_group": sg, **dict(zip(by or [], key)),
                   "p": r["p"], "lo": r["lo"], "hi": r["hi"], "n_sets": r["n"], "n_matches": r["n_clusters"]}
            rows.append(row)
    return pd.DataFrame(rows)


def by_set_number(D: pd.DataFrame) -> pd.DataFrame:
    """P(first server wins) for set 1..5 and the deciding set, by gender and overall."""
    rows = []
    for gname, g in [("All", D), ("Men", D[D.gender == "M"]), ("Women", D[D.gender == "W"])]:
        for k in sorted(g.set_no.unique()):
            gg = g[g.set_no == k]
            r = cluster_prop_ci(gg.y.values, gg.match_id.values)
            rows.append(dict(gender=gname, set_no=int(k), p=r["p"], lo=r["lo"], hi=r["hi"], n_sets=r["n"]))
    return pd.DataFrame(rows)


def strength_models(D: pd.DataFrame) -> pd.DataFrame:
    """Raw vs strength-adjusted P(first server wins) via clustered logistic regressions."""
    specs = [
        ("raw", []),
        ("pre-match rank", ["d_logrank"]),
        ("rank + previous set result", ["d_logrank", "prev"]),
        ("rank + in-match serve form (other sets)", ["d_logrank", "d_spw_loo"]),
        ("rank + previous set + in-match form", ["d_logrank", "prev", "d_spw_loo"]),
    ]
    rows = []
    base = D[D.linked]
    for gname, g in [("All", base), ("Men", base[base.gender == "M"]), ("Women", base[base.gender == "W"])]:
        for sg, gg in (("set 1", g[g.set_no == 1]), ("sets 2+", g[g.set_no > 1])):
            sub = gg.dropna(subset=["d_spw_loo"])   # identical sample for every model
            for name, xs in specs:
                if sg == "set 1" and "prev" in xs:
                    continue
                r = logit_cluster(sub, "y", xs, "match_id")
                rows.append(dict(gender=gname, set_group=sg, model=name, **r))
    return pd.DataFrame(rows)


def selection_table(D: pd.DataFrame) -> pd.DataFrame:
    """How the first server of later sets is selected: share who lost the previous set, share better
    ranked, by parity of the previous set, and P(win) in each cell."""
    rows = []
    later = D[(D.set_no > 1) & D.prev.notna() & (D.prev != 0)]
    for (sg, gg) in [("set 1", D[D.set_no == 1]), ("sets 2+", later)]:
        rows.append(dict(cell=f"{sg}: all", n=len(gg),
                         share_lost_prev=float((gg.prev == -1).mean()) if sg != "set 1" else np.nan,
                         share_better_ranked=float(gg.fs_better_ranked.mean()),
                         mean_d_logrank=float(gg.d_logrank.mean()), p_win=float(gg.y.mean())))
    for even in (1.0, 0.0):
        gg = later[later.prev_even == even]
        rows.append(dict(cell=f"sets 2+: previous set had {'even' if even else 'odd'} no. of games", n=len(gg),
                         share_lost_prev=float((gg.prev == -1).mean()), share_better_ranked=float(gg.fs_better_ranked.mean()),
                         mean_d_logrank=float(gg.d_logrank.mean()), p_win=float(gg.y.mean())))
    for pv, nm in ((1, "won"), (-1, "lost")):
        gg = later[later.prev == pv]
        r = cluster_prop_ci(gg.y.values, gg.match_id.values)
        rows.append(dict(cell=f"sets 2+: first server {nm} previous set", n=len(gg), share_lost_prev=float(pv == -1),
                         share_better_ranked=float(gg.fs_better_ranked.mean()), mean_d_logrank=float(gg.d_logrank.mean()),
                         p_win=r["p"], lo=r["lo"], hi=r["hi"]))
    return pd.DataFrame(rows)


def coin_toss_balance(D: pd.DataFrame) -> pd.DataFrame:
    """Is the set-1 first server a random draw with respect to strength?  Share of set-1 first servers
    who are the better-ranked player (0.5 under pure randomisation), by gender."""
    from tennis.stats import wilson_ci
    rows = []
    s1 = D[(D.set_no == 1) & D.linked & (D.d_logrank != 0)]
    for gname, g in [("All", s1), ("Men", s1[s1.gender == "M"]), ("Women", s1[s1.gender == "W"])]:
        k, n = float(g.fs_better_ranked.sum()), len(g)
        lo, hi = wilson_ci(k, n)
        rows.append(dict(gender=gname, n=n, share_fs_better_ranked=k / n, lo=lo, hi=hi,
                         mean_d_logrank=float(g.d_logrank.mean())))
    return pd.DataFrame(rows)


def set_endings(D: pd.DataFrame, G: pd.DataFrame) -> pd.DataFrame:
    """How sets end (winner holds / breaks / tiebreak) and how often the next set is then opened by
    the loser of this set.  Uses consecutive usable sets."""
    last = G.sort_values(["match_id", "SetNo", "GameNo"]).groupby(["match_id", "SetNo"]).last()
    E = D[["match_id", "SetNo", "set_winner", "fs"]].join(last[["first_server", "is_tb"]], on=["match_id", "SetNo"])
    nxt = D[["match_id", "SetNo", "fs"]].assign(SetNo=lambda d: d.SetNo - 1).rename(columns={"fs": "next_fs"})
    E = E.merge(nxt, on=["match_id", "SetNo"], how="inner")
    E["ending"] = np.where(E.is_tb, "tiebreak", np.where(E.first_server == E.set_winner, "winner held serve to close",
                                                          "winner broke serve to close"))
    E["next_fs_is_loser"] = E.next_fs != E.set_winner
    out = E.groupby("ending").agg(n=("ending", "size"), next_fs_is_loser=("next_fs_is_loser", "mean")).reset_index()
    out["share"] = out.n / out.n.sum()
    tot = pd.DataFrame([dict(ending="all", n=len(E), next_fs_is_loser=E.next_fs_is_loser.mean(), share=1.0)])
    return pd.concat([out, tot], ignore_index=True)


def previous_winner_contrast(D: pd.DataFrame) -> pd.DataFrame:
    """Model-free check for sets 2+: does the previous-set winner win this set more often when they
    serve first than when they receive first?  No strength model needed: the comparison holds the
    previous-set result fixed and varies only the serve order."""
    later = D[(D.set_no > 1) & D.prev.isin([1, -1])].copy()
    later["prev_winner_serves_first"] = later.prev == 1
    later["prev_winner_wins"] = np.where(later.prev == 1, later.y, 1 - later.y)
    # rank gap from the previous winner's point of view
    later["prev_winner_d_logrank"] = np.where(later.prev == 1, later.d_logrank, -later.d_logrank)
    rows = []
    for gname, g in [("All", later), ("Men", later[later.gender == "M"]), ("Women", later[later.gender == "W"])]:
        for serves, nm in ((True, "serves first"), (False, "receives first")):
            gg = g[g.prev_winner_serves_first == serves]
            r = cluster_prop_ci(gg.prev_winner_wins.values, gg.match_id.values)
            rows.append(dict(gender=gname, previous_set_winner=nm, p_wins=r["p"], lo=r["lo"], hi=r["hi"], n_sets=r["n"],
                             mean_prev_winner_d_logrank=float(gg.prev_winner_d_logrank.mean())))
    return pd.DataFrame(rows)


def heterogeneity_tests(D: pd.DataFrame) -> pd.DataFrame:
    """Joint Wald tests (match-clustered logit) that P(first server wins) is the same across Slams,
    years and genders, separately for set 1 and sets 2+.  Raw outcome, no strength controls."""
    import statsmodels.formula.api as smf
    rows = []
    for sg, g in (("set 1", D[D.set_no == 1]), ("sets 2+", D[D.set_no > 1])):
        g = g.assign(year_c=g.year.astype(str))
        for factor in ("slam", "year_c", "gender"):
            res = smf.glm(f"y ~ C({factor})", g, family=__import__("statsmodels.api").api.families.Binomial()).fit(
                cov_type="cluster", cov_kwds={"groups": pd.factorize(g.match_id)[0]})
            names = [c for c in res.params.index if c.startswith(f"C({factor})")]
            w = res.wald_test(", ".join(f"{c} = 0" for c in names), scalar=True)
            rows.append(dict(set_group=sg, factor=factor.replace("_c", ""), chi2=float(w.statistic), df=len(names),
                             p=float(w.pvalue), n_sets=len(g)))
    return pd.DataFrame(rows)
