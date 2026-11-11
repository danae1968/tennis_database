"""Per-player and tour-wide rates (with match-clustered bootstrap or Wilson CIs) from the long match table."""
from __future__ import annotations

import numpy as np
import pandas as pd

from analyses.top10_profiles.boot import boot_ci
from tennis.stats import ratio_ci, wilson_ci

SURFACES = ["Hard", "Clay", "Grass"]          # Carpet does not occur in 2025-26


def usable_games(L: pd.DataFrame) -> pd.DataFrame:
    """Rows with a score-based service-game count (drops matches without break-point stats)."""
    return L[L.svg.notna()]


def rate(num, den) -> tuple[float, float, float]:
    """Pooled rate with the cluster-robust 95% CI of ``tennis.stats.ratio_ci`` (one row = one match = one cluster)."""
    r = ratio_ci(np.asarray(num, float), np.asarray(den, float))
    return r["rate"], r["lo"], r["hi"]


def hold_break(L: pd.DataFrame, seed: int) -> dict:
    """Hold % and break % of the rows in ``L`` (one player, or a whole tour) with 95% CIs.

    Hold = 1 - breaks conceded / service games; break = breaks won / opponent's service games (return games).
    """
    G = usable_games(L)
    c = G[["conceded", "svg", "breaks", "o_svg"]].to_numpy(dtype=float)
    q, qlo, qhi = rate(c[:, 0], c[:, 1])           # share of service games broken
    h, hlo, hhi = 1 - q, 1 - qhi, 1 - qlo
    b, blo, bhi = rate(c[:, 2], c[:, 3])
    return dict(n_matches=len(G), svc_games=float(G.svg.sum()), ret_games=float(G.o_svg.sum()),
                hold=h, hold_lo=hlo, hold_hi=hhi, brk=b, brk_lo=blo, brk_hi=bhi)


def pressure(L: pd.DataFrame, seed: int) -> dict:
    """Break-point saved/converted vs own baselines, with match-clustered bootstrap CIs.

    BP saved % = bpSaved / bpFaced; baseline = all service points won %.  BP converted % = breaks / break
    points on return; baseline = all return points won %.  ``*_gap`` = pressure rate minus baseline, in
    percentage points per 100 points (CI from resampling matches jointly, so the overlap of BP points with
    all points is respected).
    """
    G = L[L.svpt.notna() & L.o_svpt.notna() & (L.svpt > 0)]
    c = G[["bpS", "bpF", "sv_won", "svpt", "breaks", "o_bpF", "ret_won", "ret_pts"]].to_numpy(dtype=float)
    r = {"n_matches": len(G), "bp_faced": int(G.bpF.sum()), "bp_chances": int(G.o_bpF.sum())}
    for name, (i, j) in (("bp_saved", (0, 1)), ("sv_base", (2, 3)), ("bp_conv", (4, 5)), ("ret_base", (6, 7))):
        r[name], r[name + "_lo"], r[name + "_hi"] = rate(c[:, i], c[:, j])
    for name, f in (("save_gap", lambda s: 100 * (s[..., 0] / s[..., 1] - s[..., 2] / s[..., 3])),
                    ("conv_gap", lambda s: 100 * (s[..., 4] / s[..., 5] - s[..., 6] / s[..., 7]))):
        e, lo, hi, sd = boot_ci(c, f, seed + hash_name(name), return_sd=True)
        r[name], r[name + "_lo"], r[name + "_hi"], r[name + "_sd"] = e, lo, hi, sd
    return r


def hash_name(s: str) -> int:
    """Small deterministic integer from a short string (Python's ``hash`` is salted per process)."""
    return sum((i + 1) * ord(ch) for i, ch in enumerate(s)) % 1000


def tb_deciding(L: pd.DataFrame) -> dict:
    """Tiebreaks won and deciding sets won, with Wilson CIs (matches are the units; small samples)."""
    tbk, tbn = int(L.tb_won.sum()), int(L.tb_played.sum())
    D = L[L.deciding & L.completed]
    dk, dn = int(D.won.sum()), len(D)
    tlo, thi = wilson_ci(tbk, tbn)
    dlo, dhi = wilson_ci(dk, dn)
    tp, dp = (tbk / tbn if tbn else np.nan), (dk / dn if dn else np.nan)
    tlo, thi, dlo, dhi = min(tlo, tp), max(thi, tp), min(dlo, dp), max(dhi, dp)   # Wilson can exclude k/n at 0 or n
    return dict(tb_won=tbk, tb_played=tbn, tb_pct=tbk / tbn if tbn else np.nan, tb_lo=tlo, tb_hi=thi,
                dec_won=dk, dec_played=dn, dec_pct=dk / dn if dn else np.nan, dec_lo=dlo, dec_hi=dhi)


def keypoints(ov: pd.DataFrame, ks: pd.DataFrame, kr: pd.DataFrame, seed: int) -> dict:
    """Charted key-point win rates vs the same player's overall serve / return points won.

    Inputs are the charting rows of ONE group (a player, or the whole tour) restricted to matches present in the
    Overview.  Serve: BP faced (row 'BP'), game points (GP), deuce points (Deuce) vs serve points won;
    return: break-point chances (BPO), game points faced (GPF), deuce (DeuceR) vs return points won.
    Gaps are in percentage points, CIs by match-clustered bootstrap.
    """
    m = ov[["match_id", "player", "serve_pts", "first_won", "second_won", "return_pts", "return_pts_won"]].copy()
    m["sv_won"] = m.first_won + m.second_won
    keys = ["match_id", "player"]
    cols = []
    for tag, tab, rows in (("S", ks, ("BP", "GP", "Deuce")), ("R", kr, ("BPO", "GPF", "DeuceR"))):
        for rw in rows:
            x = tab[tab.row == rw][keys + ["pts", "pts_won"]].rename(columns={"pts": f"{rw}_n", "pts_won": f"{rw}_k"})
            m = m.merge(x, on=keys, how="left")
            cols += [f"{rw}_n", f"{rw}_k"]
    m = m.fillna({c: 0 for c in cols})
    out: dict = {"n_matches": int(m.match_id.nunique())}
    for tag, base_k, base_n, rows in (("S", "sv_won", "serve_pts", ("BP", "GP", "Deuce")),
                                      ("R", "return_pts_won", "return_pts", ("BPO", "GPF", "DeuceR"))):
        for rw in rows:
            c = m[[f"{rw}_k", f"{rw}_n", base_k, base_n]].to_numpy(dtype=float)
            e, lo, hi, sd = boot_ci(c, lambda s: 100 * (s[..., 0] / s[..., 1] - s[..., 2] / s[..., 3]), seed + hash_name(rw), return_sd=True)
            r = rate(c[:, 0], c[:, 1])[0]
            out[f"{rw}_gap"], out[f"{rw}_gap_lo"], out[f"{rw}_gap_hi"], out[f"{rw}_gap_sd"] = e, lo, hi, sd
            out[f"{rw}_rate"] = r
            out[f"{rw}_pts"] = int(c[:, 1].sum())
        out[f"{tag}_base"] = float(m[base_k].sum() / m[base_n].sum())
    return out


def winners_ue(ov: pd.DataFrame, seed: int) -> dict:
    """Winners and unforced errors per 100 points (serve + return points) with match-bootstrap CIs."""
    o = ov.copy()
    o["pts"] = o.serve_pts + o.return_pts
    c = o[["winners", "unforced", "pts"]].dropna().to_numpy(dtype=float)
    w, wlo, whi = (100 * v for v in rate(c[:, 0], c[:, 2]))
    u, ulo, uhi = (100 * v for v in rate(c[:, 1], c[:, 2]))
    return dict(charted_matches=len(c), charted_points=int(c[:, 2].sum()), w100=w, w100_lo=wlo, w100_hi=whi,
                u100=u, u100_lo=ulo, u100_hi=uhi)


def player_table(L: pd.DataFrame, min_matches: int = 30) -> pd.DataFrame:
    """Hold % and break % of every player with at least ``min_matches`` usable matches in the window."""
    G = usable_games(L)
    g = G.groupby("id").agg(name=("name", "first"), matches=("match_id", "size"), conceded=("conceded", "sum"), svg=("svg", "sum"),
                            breaks=("breaks", "sum"), o_svg=("o_svg", "sum")).reset_index()
    g["hold"] = 1 - g.conceded / g.svg
    g["brk"] = g.breaks / g.o_svg
    return g[g.matches >= min_matches].reset_index(drop=True)


def fisher_ci(r: float, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    """95% CI of a correlation from Fisher's z transform (n >= 4)."""
    if n < 4 or not np.isfinite(r) or abs(r) >= 1:
        return (np.nan, np.nan)
    c, se = np.arctanh(r), 1 / np.sqrt(n - 3)
    return float(np.tanh(c - z * se)), float(np.tanh(c + z * se))


def selection_check(tab: pd.DataFrame, top_ids: set[str]) -> dict:
    """Correlation of hold with break among all regular players, among the tour's top 10, and among the 10 regular players with
    the highest hold + break (selection on the sum alone induces a negative correlation: Berkson's paradox)."""
    top = tab[tab.id.isin(top_ids)]
    best = tab.assign(s=tab.hold + tab.brk).nlargest(10, "s")
    r_all, r_top, r_best = tab.hold.corr(tab.brk), top.hold.corr(top.brk), best.hold.corr(best.brk)
    return dict(n_regulars=len(tab), corr_all=r_all, corr_all_lo=fisher_ci(r_all, len(tab))[0], corr_all_hi=fisher_ci(r_all, len(tab))[1],
                corr_top10=r_top, corr_top10_lo=fisher_ci(r_top, len(top))[0], corr_top10_hi=fisher_ci(r_top, len(top))[1], n_top10=len(top),
                corr_best10_by_sum=r_best)


def gap_tests(rows: list[dict]) -> pd.DataFrame:
    """Compare each player's pressure gap with the tour-average gap (z test on the bootstrap SD), with Holm adjustment over
    ALL comparisons passed in.  Each row needs ``gap``, ``tour_gap`` and ``sd``."""
    from scipy import stats as st
    from tennis.stats import holm
    t = pd.DataFrame(rows)
    t["diff"] = t.gap - t.tour_gap
    t["z"] = t["diff"] / t.sd
    t["p"] = 2 * st.norm.sf(np.abs(t.z))
    t["p_holm"] = holm(t.p.fillna(1.0).to_numpy())
    return t
