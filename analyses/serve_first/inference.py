"""The earlier first-server *inference* method (``set_first_serve/opus/analysis.py``), ported so it
can be validated against the point-by-point ground truth.

Match-level TML data has no serve order.  The earlier analysis inferred it as follows:

1. Hypotheses H_w ("match winner served first") and H_l.  Under each, serve alternation (tiebreak
   counted as one game) implies each player's number of *regular* service games; tiebreaks are not
   counted in ``w_SvGms`` / ``l_SvGms``.  A hypothesis "fits" if it reproduces both SvGms values.
   Exactly one fit = identified; both = ambiguous; none = data error.
2. Estimator A ("posterior"): identified matches get P(H_w) = 0/1; ambiguous ones get a posterior
   from an iid game-level Markov model (hold probabilities from each player's in-match serve-point
   win rate) using the set scores and the break counts (bpFaced - bpSaved), prior 1/2.
3. Estimator B: identified matches only (selection-biased).
4. Estimator B*: B corrected by a null simulation of the same identification selection.

Score parsing and the serve plan now live in :mod:`tennis.scores`; the remaining functions are
copied from that script with type hints and a seeded RNG argument; the logic is unchanged.
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np

from tennis.scores import parse_score as _parse_score
from tennis.scores import serve_plan  # noqa: F401  (re-exported; used by validation)

SetScore = tuple[int, int, bool]


def parse_score(s: object) -> list[SetScore] | None:
    """TML score string -> list of (winner games, loser games, is_tiebreak) or None if not a clean
    completed match.  Thin wrapper around :func:`tennis.scores.parse_score` (match tiebreaks rejected)."""
    sets = _parse_score(s, allow_match_tiebreak=False)
    return None if sets is None else [(x.w, x.l, x.tiebreak) for x in sets]


def svgms_fit(sets: list[SetScore], w_svgms: float, l_svgms: float) -> tuple[bool, bool]:
    """Whether H_w and H_l reproduce the observed (w_SvGms, l_SvGms)."""
    fits = []
    for first_is_w in (True, False):
        plan = serve_plan(sets, first_is_w)
        fits.append(sum(p[1] for p in plan) == w_svgms and sum(p[2] for p in plan) == l_svgms)
    return fits[0], fits[1]


def hold_prob(p: float) -> float:
    """P(server holds) for iid serve-point win probability p."""
    q = 1 - p
    return p**4 * (1 + 4 * q + 10 * q**2) + 20 * p**3 * q**3 * p**2 / (1 - 2 * p * q)


def rnd(p: float, step: float = 0.01) -> float:
    return round(min(max(p, 0.30), 0.95) / step) * step


@lru_cache(maxsize=None)
def set_break_dist(f_games: int, s_games: int, tb: bool, hf: float, hs: float) -> tuple[float, ...]:
    """Distribution of breaks made by the set's first server F over paths reaching the final regular
    score (for TB sets: m-m) without ending earlier.  hf/hs = hold probabilities of F and S."""
    if tb:
        m = min(f_games, s_games)
        tf, ts = m, m
    else:
        tf, ts = f_games, s_games

    def ended(x: int, y: int) -> bool:
        return (x >= 6 and x - y >= 2) or (y >= 6 and y - x >= 2)

    maxb = (tf + ts) // 2 + 1
    dp = {(0, 0): np.zeros(maxb + 1)}
    dp[(0, 0)][0] = 1.0
    for g in range(tf + ts):
        f_serves = g % 2 == 0
        new: dict = {}
        for (x, y), v in dp.items():
            if x + y != g or ((x, y) != (0, 0) and ended(x, y)):
                continue
            if x + 1 <= tf:
                add = v * hf if f_serves else np.roll(v, 1) * (1 - hs)
                new[(x + 1, y)] = new.get((x + 1, y), 0) + add
            if y + 1 <= ts:
                add = v * (1 - hf) if f_serves else v * hs
                new[(x, y + 1)] = new.get((x, y + 1), 0) + add
        dp = new
    return tuple(dp.get((tf, ts), np.zeros(maxb + 1)))


def posterior_w_first(sets: list[SetScore], pw: float, pl: float, brk_w: float) -> tuple[float, float, float, float]:
    """Score-only and score+break likelihoods of H_w and H_l under the iid Markov model.

    Returns (slik_w, slik_l, blik_w, blik_l).  pw/pl are W's/L's serve-point win rates; brk_w is the
    number of breaks W made (L's bpFaced - bpSaved).
    """
    hw, hl = rnd(hold_prob(rnd(pw)), 0.01), rnd(hold_prob(rnd(pl)), 0.01)
    res = []
    for first_is_w in (True, False):
        plan = serve_plan(sets, first_is_w)
        dist = np.array([1.0])
        for (a, b, tb), (wf, _swk, slk) in zip(sets, plan):
            if wf:
                v = np.array(set_break_dist(a, b, tb, hw, hl))
            else:
                vf = np.array(set_break_dist(b, a, tb, hl, hw))
                b_reg = min(a, b) if tb else b
                shift = slk - b_reg
                v = np.zeros(len(vf) + abs(shift) + 2)
                for xf, pr in enumerate(vf):
                    xw = shift + xf
                    if pr > 0 and xw >= 0:
                        v[xw] += pr
            dist = np.convolve(dist, v)
        b_lik = dist[int(brk_w)] if 0 <= brk_w < len(dist) else 0.0
        res.append((dist.sum(), b_lik))
    return res[0][0], res[1][0], res[0][1], res[1][1]


def posterior_from_fit(fit_w: bool, fit_l: bool, slik_w: float, slik_l: float,
                       blik_w: float, blik_l: float) -> float:
    """Estimator-A probability that the match winner served first (NaN if unusable)."""
    n_fit = int(fit_w) + int(fit_l)
    if n_fit == 1:
        return 1.0 if fit_w else 0.0
    if n_fit == 0:
        return float("nan")
    lw, ll = blik_w, blik_l
    if lw + ll == 0:
        lw, ll = slik_w, slik_l
    if lw + ll == 0:
        return float("nan")
    return lw / (lw + ll)


def simulate_identification_null(pw: np.ndarray, pl: np.ndarray, best_of: np.ndarray, reps: int,
                                 rng: np.random.Generator) -> list[tuple[int, int, bool, bool]]:
    """Null simulation (iid point model, random first server, TB at 6-6 in every set) with the same
    SvGms identification rule.  Returns (sim_match, set_no, identified, first_server_won)."""
    recs = []
    ha_all = np.array([hold_prob(x) for x in pw])
    hb_all = np.array([hold_prob(x) for x in pl])
    for rep in range(reps):
        for j in range(len(pw)):
            pa, pb = pw[j], pl[j]
            need = 3 if best_of[j] == 5 else 2
            a_first = rng.random() < 0.5
            sa = sb = 0
            res = []
            nreg_a = nreg_b = 0
            while sa < need and sb < need:
                x = y = g = 0
                set_first_a = a_first
                while True:
                    a_serves = (g % 2 == 0) == set_first_a
                    if x == 6 and y == 6:
                        tx = ty = k = 0
                        while not ((tx >= 7 or ty >= 7) and abs(tx - ty) >= 2):
                            if (k % 4 in (0, 3)) == set_first_a:
                                if rng.random() < pa:
                                    tx += 1
                                else:
                                    ty += 1
                            else:
                                if rng.random() < pb:
                                    ty += 1
                                else:
                                    tx += 1
                            k += 1
                        x, y = (x + 1, y) if tx > ty else (x, y + 1)
                        g += 1
                        break
                    h = ha_all[j] if a_serves else hb_all[j]
                    srv_wins = rng.random() < h
                    if a_serves:
                        nreg_a += 1
                        x, y = (x + 1, y) if srv_wins else (x, y + 1)
                    else:
                        nreg_b += 1
                        x, y = (x, y + 1) if srv_wins else (x + 1, y)
                    g += 1
                    if (x >= 6 and x - y >= 2) or (y >= 6 and y - x >= 2):
                        break
                res.append((set_first_a, x > y))
                sa, sb = (sa + 1, sb) if x > y else (sa, sb + 1)
                if g % 2 == 1:
                    a_first = not a_first
            ident = nreg_a != nreg_b
            for k, (fa, aw) in enumerate(res):
                recs.append((rep * len(pw) + j, k + 1, ident, fa == aw))
    return recs
