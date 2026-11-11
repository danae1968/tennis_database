"""P(win set | served first game of the set) -- ATP main tour (TML / Sackmann format).

Run:  python3 -P analysis.py   (writes results.json + tables to this folder)

Pipeline
1. Parse completed matches (no RET/W/O/DEF, no match-tiebreak/Fast4 formats) with serve stats.
2. Serve order: serve alternates every game across set boundaries; a tiebreak counts as ONE game
   for alternation, but (verified empirically) w_SvGms/l_SvGms EXCLUDE tiebreaks.
   For each hypothesis H in {winner served first, loser served first} compute the implied regular
   service games of each player; keep H iff it reproduces (w_SvGms, l_SvGms).
   -> "hard-identified" when exactly one H fits.
3. Extra hard information: breaks per player = bpFaced - bpSaved. Under H the net breaks per set
   are fixed by the score; break totals rule out H if infeasible.
4. Soft (posterior) assignment for all matches: P(H | score, breaks) under an iid game-level
   Markov model whose hold probabilities come from each player's in-match serve-point win rate
   (ordering-independent statistics). Prior P(H)=1/2 (coin toss). Identified matches get 0/1.
   This avoids the selection bias of using only identifiable matches (identifiability depends
   on set-score parity, which is correlated with whether the first server won).
5. Baselines: Markov-model expected P(first server wins) with the same hold probabilities
   (theory: under iid model the set-win probability does not depend on who serves first), and a
   simulation of the identification-selection effect under the null.
"""
import glob, json, math, os, re
from functools import lru_cache
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', '..', 'tml-data')
RNG = np.random.default_rng(12345)
SIM_REPS = 4

# ----------------------------------------------------------------------------- parsing
SET_RE = re.compile(r'^(\d+)-(\d+)(?:\((\d+)\))?$')


def parse_score(s):
    """list of (games_winner, games_loser, is_tb) or None if not a clean completed match."""
    if not isinstance(s, str):
        return None
    out = []
    for t in s.split():
        m = SET_RE.match(t)
        if not m:
            return None
        a, b = int(m[1]), int(m[2])
        hi, lo = max(a, b), min(a, b)
        if hi - lo == 1 and lo >= 6:
            tb = True                      # tiebreak at lo-lo (6-6, or 12-12 at Wimbledon 2019-21)
        elif hi >= 6 and hi - lo >= 2 and (hi == 6 or hi - lo == 2):
            tb = False
        else:
            return None                    # incomplete / non-standard set
        out.append((a, b, tb))
    # match winner must win the last set and the majority
    if not out or out[-1][0] < out[-1][1]:
        return None
    return out


def serve_plan(sets, first_is_w):
    """Per set: (w_serves_first, regular games served by W, by L). TB counts as 1 game for alternation."""
    w_first = first_is_w
    plan = []
    for a, b, tb in sets:
        n_reg = a + b - (1 if tb else 0)
        n_first = (n_reg + 1) // 2
        n_second = n_reg // 2
        sw, sl = (n_first, n_second) if w_first else (n_second, n_first)
        plan.append((w_first, sw, sl))
        if (a + b) % 2 == 1:               # odd total (TB counted as one game) -> other player starts next set
            w_first = not w_first
    return plan


# ----------------------------------------------------------------------------- Markov pieces
def hold_prob(p):
    q = 1 - p
    return p**4 * (1 + 4*q + 10*q**2) + 20 * p**3 * q**3 * p**2 / (1 - 2*p*q)


@lru_cache(maxsize=None)
def tb_win_prob(pa, pb, target=7):
    """P(A wins tiebreak), A serves point 1, then ABBAABB.. ; iid points. pa/pb = serve point win probs."""
    @lru_cache(maxsize=None)
    def f(x, y):
        if x >= target and x - y >= 2:
            return 1.0
        if y >= target and y - x >= 2:
            return 0.0
        if x >= target - 1 and y >= target - 1 and x == y:
            # deuce-like: two points, one served by each -> closed form
            w = pa * (1 - pb)
            l = (1 - pa) * pb
            return w / (w + l)
        k = x + y
        a_serves = (k % 4 == 0) or (k % 4 == 3)
        p = pa if a_serves else 1 - pb
        return p * f(x + 1, y) + (1 - p) * f(x, y + 1)
    return f(0, 0)


@lru_cache(maxsize=None)
def set_win_prob(pa, pb, a_first):
    """P(A wins a tiebreak set) with A serving first iff a_first. pa, pb rounded serve-point probs."""
    ha, hb = hold_prob(pa), hold_prob(pb)
    @lru_cache(maxsize=None)
    def f(x, y):
        if x >= 6 and x - y >= 2:
            return 1.0
        if y >= 6 and y - x >= 2:
            return 0.0
        if x == 6 and y == 6:
            # TB first server = set first server
            return tb_win_prob(pa, pb) if a_first else 1 - tb_win_prob(pb, pa)
        a_serves = ((x + y) % 2 == 0) == a_first
        p = ha if a_serves else 1 - hb
        return p * f(x + 1, y) + (1 - p) * f(x, y + 1)
    return f(0, 0)


@lru_cache(maxsize=None)
def set_break_dist(f_games, s_games, tb, hf, hs):
    """Distribution over breaks made by set-first-server F, for paths that reach final regular
    score (f_games, s_games) [for TB sets: reach (m,m)] without the set ending earlier.
    hf/hs = hold probs of F and S (rounded). Returns tuple of probabilities indexed by #breaks."""
    if tb:
        m = min(f_games, s_games)
        tf, ts = m, m
    else:
        tf, ts = f_games, s_games

    def ended(x, y):
        return (x >= 6 and x - y >= 2) or (y >= 6 and y - x >= 2)

    maxb = (tf + ts) // 2 + 1
    # dp[(x,y)] = array over breaks-by-F
    dp = {(0, 0): np.zeros(maxb + 1)}
    dp[(0, 0)][0] = 1.0
    for g in range(tf + ts):
        f_serves = (g % 2 == 0)
        new = {}
        for (x, y), v in dp.items():
            if x + y != g:
                continue
            if (x, y) != (0, 0) and ended(x, y):
                continue
            # F wins game
            if x + 1 <= tf:
                if f_serves:
                    add = v * hf
                else:
                    add = np.roll(v, 1) * (1 - hs)
                new[(x + 1, y)] = new.get((x + 1, y), 0) + add
            if y + 1 <= ts:
                if f_serves:
                    add = v * (1 - hf)
                else:
                    add = v * hs
                new[(x, y + 1)] = new.get((x, y + 1), 0) + add
        dp = new
    return tuple(dp.get((tf, ts), np.zeros(maxb + 1)))


def rnd(p, step=0.01):
    return round(min(max(p, 0.30), 0.95) / step) * step


# ----------------------------------------------------------------------------- load
def load():
    fs = sorted(glob.glob(os.path.join(DATA, '[12][0-9][0-9][0-9].csv')))
    df = pd.concat([pd.read_csv(f, low_memory=False) for f in fs], ignore_index=True)
    df['year'] = df.tourney_date // 10000
    df['sets'] = df.score.map(parse_score)
    return df


def build(df):
    n_all = len(df)
    d = df[df.sets.notna()].copy()
    n_clean = len(d)
    stat_cols = ['w_SvGms', 'l_SvGms', 'w_svpt', 'l_svpt', 'w_1stWon', 'w_2ndWon', 'l_1stWon', 'l_2ndWon',
                 'w_bpFaced', 'w_bpSaved', 'l_bpFaced', 'l_bpSaved']
    d = d[d[stat_cols].notna().all(axis=1) & (d.w_svpt > 0) & (d.l_svpt > 0)].copy()
    n_stats = len(d)
    info = dict(matches_total=n_all, matches_clean_score=n_clean, matches_with_stats=n_stats)

    rows = []           # per-set rows
    mrows = []          # per-match rows
    for i, r in enumerate(d.itertuples(index=False)):
        sets = r.sets
        pw = (r.w_1stWon + r.w_2ndWon) / r.w_svpt
        pl = (r.l_1stWon + r.l_2ndWon) / r.l_svpt
        pw_r, pl_r = rnd(pw), rnd(pl)
        hw, hl = rnd(hold_prob(pw_r), 0.01), rnd(hold_prob(pl_r), 0.01)
        brk_w = r.l_bpFaced - r.l_bpSaved          # breaks made by W
        brk_l = r.w_bpFaced - r.w_bpSaved
        fits, bfeas, lik = [], [], []
        plans = []
        for first_is_w in (True, False):
            plan = serve_plan(sets, first_is_w)
            plans.append(plan)
            sw = sum(p[1] for p in plan)
            sl = sum(p[2] for p in plan)
            fits.append(sw == r.w_SvGms and sl == r.l_SvGms)
            # break likelihood: convolve per-set distributions of breaks by W
            dist = np.array([1.0])
            net_ok = True
            for (a, b, tb), (wf, swk, slk) in zip(sets, plan):
                if wf:
                    v = np.array(set_break_dist(a, b, tb, hw, hl))       # breaks by F = W
                else:
                    vf = np.array(set_break_dist(b, a, tb, hl, hw))      # breaks by F = L
                    # breaks by W = (regular games served by L) - (L's regular games won) + breaks by L
                    a_reg, b_reg = (a, b) if not tb else (min(a, b), min(a, b))
                    shift = slk - b_reg
                    v = np.zeros(len(vf) + abs(shift) + 2)
                    for xf, pr in enumerate(vf):
                        xw = shift + xf
                        if pr > 0:
                            if xw < 0:
                                net_ok = False
                                continue
                            v[xw] += pr
                dist = np.convolve(dist, v)
            score_lik = dist.sum()
            b_lik = dist[int(brk_w)] if 0 <= brk_w < len(dist) else 0.0
            # consistency of the L-side break count is implied by the SvGms identity
            bfeas.append(b_lik > 0)
            lik.append((score_lik, b_lik))
        mrows.append(dict(idx=i, fit_w=fits[0], fit_l=fits[1], bfeas_w=bfeas[0], bfeas_l=bfeas[1],
                          slik_w=lik[0][0], slik_l=lik[1][0], blik_w=lik[0][1], blik_l=lik[1][1],
                          pw=pw, pl=pl, pw_r=pw_r, pl_r=pl_r, surface=r.surface, year=r.year,
                          best_of=r.best_of, level=r.tourney_level, nsets=len(sets),
                          tourney_id=r.tourney_id))
        for k, ((a, b, tb), pw_first, pl_first) in enumerate(zip(sets, plans[0], plans[1])):
            w_won = a > b
            # under H_w: first server of set k is W iff pw_first[0]
            fs_win_hw = (w_won == pw_first[0])
            fs_win_hl = (w_won == pl_first[0])
            # model prob that the H-implied first server wins this set (tiebreak-set model, serve order irrelevant in theory)
            pW = set_win_prob(pw_r, pl_r, True)
            e_hw = pW if pw_first[0] else 1 - pW
            e_hl = pW if pl_first[0] else 1 - pW
            rows.append(dict(m=i, set_no=k + 1, last=(k == len(sets) - 1), tb=tb, ngames=a + b,
                             fsw_hw=fs_win_hw, fsw_hl=fs_win_hl, e_hw=e_hw, e_hl=e_hl))
    M = pd.DataFrame(mrows)
    S = pd.DataFrame(rows)
    return d.reset_index(drop=True), M, S, info


# ----------------------------------------------------------------------------- estimation
def ratio_ci(y, n, cluster):
    """Ratio estimator sum(y)/sum(n) with cluster-robust (match) SE; y may be fractional."""
    g = pd.DataFrame(dict(y=y, n=n, c=cluster)).groupby('c').sum()
    p = g.y.sum() / g.n.sum()
    k = len(g)
    se = math.sqrt(((g.y - p * g.n) ** 2).sum() * k / (k - 1)) / g.n.sum()
    return p, se


def summarize(S, weight_col, outcome_hw, outcome_hl, label, mask=None):
    T = S if mask is None else S[mask]
    w = T[weight_col].values                               # P(H_w)
    y = w * T[outcome_hw].astype(float).values + (1 - w) * T[outcome_hl].astype(float).values
    keep = ~np.isnan(w)
    p, se = ratio_ci(y[keep], np.ones(keep.sum()), T.m.values[keep])
    return dict(label=label, n_sets=int(keep.sum()), n_matches=int(T.m[keep].nunique()),
                est=p, lo=p - 1.96 * se, hi=p + 1.96 * se)


def simulate_selection(M, reps=2):
    """Under the iid Markov null (point-level), simulate each match with its serve-point probs and a random
    first server, apply SvGms identification, and return P(first server wins set) in all vs identified sets."""
    recs = []
    ha_all = np.array([hold_prob(x) for x in M.pw.values]); hb_all = np.array([hold_prob(x) for x in M.pl.values])
    pw = M.pw.values; pl = M.pl.values; bo = M.best_of.values
    for rep in range(reps):
        for j in range(len(M)):
            pa, pb = pw[j], pl[j]
            need = 3 if bo[j] == 5 else 2
            a_first = RNG.random() < 0.5
            sa = sb = 0
            res = []
            nreg_a = nreg_b = 0
            while sa < need and sb < need:
                x = y = 0
                g = 0
                set_first_a = a_first
                while True:
                    a_serves = (g % 2 == 0) == set_first_a
                    if x == 6 and y == 6:
                        # tiebreak, point level
                        tx = ty = 0; k = 0
                        while not ((tx >= 7 or ty >= 7) and abs(tx - ty) >= 2):
                            srv_a = ((k % 4 in (0, 3)) == set_first_a)
                            if srv_a:
                                if RNG.random() < pa: tx += 1
                                else: ty += 1
                            else:
                                if RNG.random() < pb: ty += 1
                                else: tx += 1
                            k += 1
                        if tx > ty: x += 1
                        else: y += 1
                        g += 1
                        break
                    h = ha_all[j] if a_serves else hb_all[j]
                    srv_wins = RNG.random() < h
                    if a_serves:
                        nreg_a += 1
                        if srv_wins: x += 1
                        else: y += 1
                    else:
                        nreg_b += 1
                        if srv_wins: y += 1
                        else: x += 1
                    g += 1
                    if (x >= 6 and x - y >= 2) or (y >= 6 and y - x >= 2):
                        break
                res.append((set_first_a, x > y))
                if x > y: sa += 1
                else: sb += 1
                if g % 2 == 1:
                    a_first = not a_first
            ident = (nreg_a != nreg_b)  # same rule as data: hypotheses differ only if counts differ
            for k, (fa, aw) in enumerate(res):
                recs.append((rep * len(M) + j, k + 1, ident, fa == aw))
    return pd.DataFrame(recs, columns=['m', 'set_no', 'ident', 'win'])


def main():
    df = load()
    d, M, S, info = build(df)

    # ---------------- SvGms convention validation
    def tot(sets, incl_tb):
        return sum(a + b - (0 if incl_tb else int(tb)) for a, b, tb in sets)
    sv = d.w_SvGms + d.l_SvGms
    G_excl = d.sets.map(lambda s: tot(s, False))
    G_incl = d.sets.map(lambda s: tot(s, True))
    has_tb = d.sets.map(lambda s: any(t for _, _, t in s))
    info['svgms_eq_regular_games'] = float((sv == G_excl).mean())
    info['svgms_eq_regular_games_tbmatches'] = float((sv[has_tb] == G_excl[has_tb]).mean())
    info['svgms_eq_games_incl_tb_tbmatches'] = float((sv[has_tb] == G_incl[has_tb]).mean())

    # ---------------- identification categories
    M['n_fit'] = M.fit_w.astype(int) + M.fit_l.astype(int)
    M['hard'] = M.n_fit == 1
    info['hyp_fit_counts'] = {'exactly_one': int((M.n_fit == 1).sum()), 'both': int((M.n_fit == 2).sum()),
                             'neither (data error)': int((M.n_fit == 0).sum())}
    hard = M[M.hard]
    truth_w = hard.fit_w
    # break-data validation on hard-identified matches
    true_feas = np.where(truth_w, hard.bfeas_w, hard.bfeas_l)
    false_feas = np.where(truth_w, hard.bfeas_l, hard.bfeas_w)
    info['bp_valid_true_hyp_feasible'] = float(true_feas.mean())
    info['bp_false_hyp_ruled_out'] = float(1 - false_feas.mean())
    # calibration of break+score posterior (ignoring SvGms) on hard-identified matches
    pb = hard.blik_w / (hard.blik_w + hard.blik_l)
    ok = np.isfinite(pb)
    tw = truth_w[ok].astype(float); pbo = pb[ok]
    info['posterior_validation'] = dict(
        n=int(ok.sum()), brier=float(((pbo - tw) ** 2).mean()),
        accuracy=float(((pbo > 0.5) == (tw > 0.5))[(pbo != 0.5)].mean()),
        calib=[dict(bin=f'{lo:.1f}-{lo+0.1:.1f}', n=int(m.sum()), mean_pred=float(pbo[m].mean()), obs=float(tw[m].mean()))
               for lo in np.arange(0, 1, 0.1) for m in [((pbo >= lo) & (pbo < lo + 0.1 + (1e-9 if lo > 0.85 else 0)))] if m.sum() > 0])
    ps = hard.slik_w / (hard.slik_w + hard.slik_l)
    info['posterior_validation_score_only_brier'] = float(((ps - truth_w.astype(float)) ** 2).mean())

    # ---------------- posterior P(H_w) per match
    def post(row):
        if row.n_fit == 1:
            return 1.0 if row.fit_w else 0.0
        if row.n_fit == 0:
            return np.nan
        lw, ll = row.blik_w, row.blik_l
        if lw + ll == 0:                      # break data inconsistent -> score-only
            lw, ll = row.slik_w, row.slik_l
        if lw + ll == 0:
            return np.nan
        return lw / (lw + ll)
    M['post'] = M.apply(post, axis=1)
    # hard-identification including break feasibility (deterministic, no model needed)
    def hard2(row):
        if row.n_fit == 1:
            return 1.0 if row.fit_w else 0.0
        if row.n_fit == 2 and row.bfeas_w != row.bfeas_l:
            return 1.0 if row.bfeas_w else 0.0
        return np.nan
    M['hard2'] = M.apply(hard2, axis=1)
    M['hard1'] = np.where(M.hard, M.fit_w.astype(float), np.nan)
    info['n_hard1'] = int(M.hard1.notna().sum()); info['n_hard2'] = int(M.hard2.notna().sum())
    info['n_post'] = int(M.post.notna().sum())

    S = S.merge(M[['idx', 'post', 'hard1', 'hard2', 'surface', 'year', 'best_of', 'level']], left_on='m', right_on='idx')
    S['first_set'] = S.set_no == 1

    results = []
    def block(mask_name, mask):
        for col, nm in [('post', 'A: posterior, all matches'), ('hard1', 'B: SvGms-identified only'),
                        ('hard2', 'C: SvGms+break-identified')]:
            r = summarize(S, col, 'fsw_hw', 'fsw_hl', nm, mask)
            e = summarize(S, col, 'e_hw', 'e_hl', nm, mask)
            r.update(subset=mask_name, markov_expected=e['est'], excess=r['est'] - e['est'])
            results.append(r)
    block('all sets', None)
    block('set 1', S.set_no == 1)
    block('sets 2+', S.set_no > 1)
    for k in range(2, 6):
        block(f'set {k}', S.set_no == k)
    block('deciding set', S['last'] & (((S.best_of == 3) & (S.set_no == 3)) | ((S.best_of == 5) & (S.set_no == 5))))
    for sf in ['Hard', 'Clay', 'Grass', 'Carpet']:
        block(f'surface={sf}', S.surface == sf)
        block(f'surface={sf}, set 1', (S.surface == sf) & (S.set_no == 1))
    block('best of 3', S.best_of == 3); block('best of 5', S.best_of == 5)
    block('Grand Slam', S.level == 'G')
    for a, b in [(1991, 1999), (2000, 2009), (2010, 2019), (2020, 2026)]:
        block(f'{a}-{b}', S.year.between(a, b))
    block('tiebreak sets', S.tb); block('non-TB sets', ~S.tb)
    R = pd.DataFrame(results)

    # Pure theory check: set-win prob independent of who serves first
    grid = [(pa, pb) for pa in np.arange(0.50, 0.81, 0.05) for pb in np.arange(0.50, 0.81, 0.05)]
    maxdiff = max(abs(set_win_prob(round(pa, 2), round(pb, 2), True) - set_win_prob(round(pa, 2), round(pb, 2), False))
                  for pa, pb in grid)
    info['markov_max_abs_diff_first_vs_second'] = maxdiff
    # Markov expectation for the identified selection (simulation)
    # Null simulation: same matches/serve-point probs, iid model, random first server, same identification rule.
    simM = M[M.n_fit >= 1].reset_index(drop=True)
    sim = simulate_selection(simM, reps=SIM_REPS)
    nullrows = []
    groups = {'all sets': lambda T: np.ones(len(T), bool), 'set 1': lambda T: T.set_no == 1,
              'sets 2+': lambda T: T.set_no > 1, 'set 2': lambda T: T.set_no == 2, 'set 3': lambda T: T.set_no == 3}
    for gname, gf in groups.items():
        for sel in ['all', 'ident']:
            T = sim[gf(sim) & (sim.ident if sel == 'ident' else True)]
            p, se = ratio_ci(T.win.astype(float).values, np.ones(len(T)), T.m.values)
            nullrows.append(dict(subset=gname, selection=sel, null_p=p, null_se=se, n=len(T)))
    NR = pd.DataFrame(nullrows)
    info['null_simulation'] = NR.to_dict(orient='records')
    # selection-corrected estimate for B: obs_B - null_ident + null_all
    corr = []
    for gname in groups:
        rb = R[(R.subset == gname) & (R.label.str.startswith('B'))].iloc[0]
        ni = NR[(NR.subset == gname) & (NR.selection == 'ident')].iloc[0]
        na = NR[(NR.subset == gname) & (NR.selection == 'all')].iloc[0]
        se_b = (rb.hi - rb.lo) / 3.92
        est = rb.est - ni.null_p + na.null_p
        se = math.sqrt(se_b**2 + ni.null_se**2 + na.null_se**2)
        corr.append(dict(subset=gname, obs_identified=rb.est, null_identified=ni.null_p, null_all=na.null_p,
                         excess=rb.est - ni.null_p, excess_lo=rb.est - ni.null_p - 1.96 * se,
                         excess_hi=rb.est - ni.null_p + 1.96 * se, corrected=est, lo=est - 1.96 * se, hi=est + 1.96 * se))
    CR = pd.DataFrame(corr)
    CR.to_csv(os.path.join(HERE, 'selection_corrected.csv'), index=False)

    R.to_csv(os.path.join(HERE, 'results_table.csv'), index=False)
    with open(os.path.join(HERE, 'results.json'), 'w') as f:
        json.dump(info, f, indent=2, default=float)
    pd.set_option('display.width', 200)
    print(json.dumps(info, indent=1, default=float))
    print(R.round(4).to_string())
    print(NR.round(4).to_string())
    print(CR.round(4).to_string())


if __name__ == '__main__':
    main()
