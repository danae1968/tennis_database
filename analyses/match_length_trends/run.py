"""Match length trends: regenerates every table and figure of the match-length trend analysis.

    .venv/bin/python analyses/match_length_trends/run.py        (or: make match_length_trends)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

if __package__ in (None, ""):                       # run as a script: make ``analyses.*`` importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from analyses.match_length_trends import pbp, plots, tml, trends  # noqa: E402
from tennis.paths import PBP_SLAM_DIR as SLAM_DIR  # noqa: E402
from tennis.paths import analysis_dirs  # noqa: E402

RES_DIR, FIG_DIR, _ = analysis_dirs("match_length_trends")

PBP_YEARS = range(2011, 2025)
TML_YEARS = range(1995, 2027)
LAST_FULL_TML_YEAR = 2025            # 2026 is a partial season: plotted, not used in regressions
CORE = ("usopen", "wimbledon")       # the two Slams with a usable clock in every year 2011-2024
MIN_MINUTES, MAX_MINUTES = 20, 480
MIN_PPG, MAX_PPG = 3.9, 10.0


def build_slam_match_frame(S: pbp.Slam) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Match-level and set-level analysis frames from the processed Slam tables (complete matches only)."""
    m = S.matches[S.matches["gender"].notna() & S.matches["complete"]].copy()
    ok = S.points[S.points["dt_status"] == "ok"]
    dt = ok.groupby("match_id")["dt"].agg(sec_per_point="median", n_dt="size")
    g = S.games.copy()
    reg = g[~g["is_tiebreak"]]
    ppg = reg.groupby("match_id")["n_points"].agg(points_per_game="mean", n_reg_games="size")
    gd = g.dropna(subset=["duration"]).groupby("match_id")["duration"].agg(game_sec="median", n_game_dur="size")
    tb = g.groupby("match_id")["is_tiebreak"].sum().rename("n_tiebreaks")
    m = m.join(dt, on="match_id").join(ppg, on="match_id").join(gd, on="match_id").join(tb, on="match_id")
    m.loc[m["n_dt"] < 30, "sec_per_point"] = np.nan
    m.loc[m["n_game_dur"] < 5, "game_sec"] = np.nan
    m["minutes"] = m["duration"] / 60
    m["points"] = m["n_points"]
    m["edition"] = m["slam"] + m["year"].astype(str)
    s = S.sets.merge(m[["match_id", "n_sets", "edition", "complete"]], on="match_id")
    s["set_minutes"] = s["duration"] / 60
    return m, s


def slam_cleaning_table(S: pbp.Slam, m_all: pd.DataFrame, m: pd.DataFrame, sets: pd.DataFrame) -> pd.DataFrame:
    """Rows in -> rows out accounting for the point-by-point data."""
    cov = S.coverage
    used = cov[cov["used"]]
    n_files_excl = len(list(SLAM_DIR.glob("*points-doubles.csv"))) + len(list(SLAM_DIR.glob("*points-mixed.csv")))
    rows = [
        (f"point rows in singles files {PBP_YEARS.start}-{PBP_YEARS.stop - 1}", int(cov["raw_rows"].sum())),
        ("  removed: AO/FO 2018-21 files (no clock, no games-won or set-winner columns)", int(cov.loc[~cov["used"], "raw_rows"].sum())),
        ("  removed: 0X/0Y non-point rows (files used)", int(used["raw_rows"].sum() - used["points"].sum())),
        ("point rows used", int(len(S.points))),
        ("  within-game cycle times: first point of game / missing clock", int((S.points["dt_status"] == "na").sum())),
        ("  within-game cycle times: zero or negative gap (removed)", int((S.points["dt_status"] == "zero_or_neg").sum())),
        (f"  within-game cycle times: gap > {pbp.MAX_POINT_CYCLE_S}s (removed)", int((S.points["dt_status"] == "too_long").sum())),
        ("  within-game cycle times kept", int((S.points["dt_status"] == "ok").sum())),
        ("doubles/mixed point files not read", n_files_excl),
        ("singles matches in used files", int(len(m_all))),
        ("  removed: gender not identifiable", int(m_all["gender"].isna().sum())),
        ("  removed: incomplete (retired/walkover/unfinished)", int((m_all["gender"].notna() & ~m_all["complete"]).sum())),
        ("complete men's + women's matches (analysis frame)", int(len(m))),
        ("  of which with clean clock duration", int(m["duration"].notna().sum())),
        (f"  of which interrupted (gap > {pbp.INTERRUPTION_S}s) or missing clock: duration dropped", int(m["duration"].isna().sum())),
        ("games in used files", int(len(S.games))),
        ("  tiebreak games (excluded from points-per-game)", int(S.games["is_tiebreak"].sum())),
        ("  games with usable duration (no changeover, <=15 min)", int(S.games["duration"].notna().sum())),
        ("sets in analysis frame", int(len(sets))),
        ("  with usable duration", int(sets["duration"].notna().sum())),
    ]
    return pd.DataFrame(rows, columns=["step", "count"])


def final_set_check(S: pbp.Slam) -> pd.DataFrame:
    """How the deciding set of complete matches ended, by Slam-year.

    Set scores come from game counts and tiebreaks are games with two servers (see ``pbp``).
    Columns: counts by kind, number of tiebreaks, and the share of those tiebreaks with fewer than
    10 points (a 10-point tiebreak cannot have fewer than 10 points, a 7-point one usually does).
    """
    m = S.matches[S.matches["complete"] & S.matches["gender"].notna()][["match_id", "n_sets", "best_of"]]
    last = S.sets.merge(m, on="match_id").sort_values(["match_id", "set_no"]).groupby("match_id").tail(1)
    deciding = last[last["n_sets"] == last["best_of"]].copy()
    tb = S.games[S.games["is_tiebreak"]][["match_id", "set_no", "n_points"]].rename(columns={"n_points": "tb_points"})
    deciding = deciding.merge(tb, on=["match_id", "set_no"], how="left")
    tot = deciding["g1"] + deciding["g2"]
    deciding["kind"] = np.select([deciding["tb_points"].notna() & (tot == 13), deciding["tb_points"].notna() & (tot == 25), tot > 12],
                                 ["tiebreak at 6-6", "tiebreak at 12-12", "no tiebreak (advantage set)"], "ended before 6-6")
    out = deciding.groupby(["slam", "year", "kind"]).size().unstack(fill_value=0)
    for c in ("tiebreak at 6-6", "tiebreak at 12-12", "no tiebreak (advantage set)", "ended before 6-6"):
        if c not in out:
            out[c] = 0
    out["share_tb_under_10_points"] = deciding.groupby(["slam", "year"]).apply(
        lambda d: float((d["tb_points"].dropna() < 10).mean()) if d["tb_points"].notna().any() else np.nan, include_groups=False)
    return out.reset_index()


def prep_tml(d: pd.DataFrame) -> pd.DataFrame:
    """Filter to completed matches with plausible minutes and points; derive per-match metrics."""
    d = d[d["level_group"] != "Other/team"].copy()
    d["group"] = np.where(d["tour"] == "ATP", "ATP bo" + d["best_of"].fillna(0).astype(int).astype(str), d["tour"])
    d.loc[d["tour"] == "WTA", "group"] = "WTA"
    d.loc[(d["tour"] == "WTA") & (d["best_of"] == 5), "group"] = np.nan    # a handful of mislabelled rows
    d = d[d["group"].notna() & d["valid"].fillna(False).astype(bool)].copy()
    d = tml.restrict_to_reliable(d)
    d["games_per_set"] = d["n_games"] / d["n_sets"]
    d["sec_per_point"] = 60 * d["minutes"] / d["points"]
    d["points_per_game"] = d["points"] / d["n_games"]
    d["minutes_per_set"] = d["minutes"] / d["n_sets"]
    d["minutes_per_game"] = d["minutes"] / d["n_games"]
    d["sets"] = d["n_sets"]
    return d


def tml_cleaning_table(raw: pd.DataFrame, d: pd.DataFrame) -> pd.DataFrame:
    """Row accounting for the tour-level match files."""
    r = raw[raw["level_group"] != "Other/team"]
    v = r[r["valid"].fillna(False).astype(bool)]
    n_before_start = len(v) - len(d)
    ok_min = d["minutes"].between(MIN_MINUTES, MAX_MINUTES)
    ok_pts = d["points_per_game"].between(MIN_PPG, MAX_PPG)
    return pd.DataFrame([
        (f"match rows {TML_YEARS.start}-{TML_YEARS.stop - 1} (ATP, WTA, Challenger)", len(raw)),
        ("  removed: Davis/Fed Cup, Olympics, Finals etc.", len(raw) - len(r)),
        ("  removed: retirement / walkover / unparseable score", len(r) - len(v)),
        ("  removed: before the first usable year of the group (ATP bo3 1995, ATP bo5 2000, Challenger 2010, WTA 2009) or format not assignable", n_before_start),
        ("completed matches", len(d)),
        ("  with minutes", int(d["minutes"].notna().sum())),
        (f"  minutes outside [{MIN_MINUTES},{MAX_MINUTES}] (dropped from minute metrics)", int((d["minutes"].notna() & ~ok_min).sum())),
        ("  with serve points", int(d["points"].notna().sum())),
        (f"  points/game outside [{MIN_PPG},{MAX_PPG}] (dropped from point metrics)", int((d["points"].notna() & ~ok_pts).sum())),
    ], columns=["step", "count"])


def apply_tml_trims(d: pd.DataFrame) -> pd.DataFrame:
    """Blank out implausible minutes/points rather than dropping whole matches."""
    d = d.copy()
    bad_min = ~d["minutes"].between(MIN_MINUTES, MAX_MINUTES)
    bad_pts = ~d["points_per_game"].between(MIN_PPG, MAX_PPG)
    for c in ("minutes", "sec_per_point", "minutes_per_set", "minutes_per_game"):
        d.loc[bad_min, c] = np.nan
    for c in ("points", "sec_per_point", "points_per_game"):
        d.loc[bad_pts, c] = np.nan
    return d


def trend_row(label: str, sample: str, d: pd.DataFrame, value: str, cluster: str, controls: str, **kw) -> dict:
    """One row of the trend table (plus a sensitivity row excluding 2020)."""
    out = []
    for tag, dd in (("all years", d), ("excl. 2020", d[d["year"] != 2020])):
        try:
            r = trends.trend_per_decade(dd, value, cluster, controls, **kw)
        except Exception as e:           # too few observations / singular design
            r = {"n": len(dd), "per_decade": np.nan, "error": str(e)}
        out.append({"source": sample, "group": label, "outcome": value, "years": tag, **r})
    return out


def slam_trend_rows(core_m: pd.DataFrame, core_s: pd.DataFrame, m: pd.DataFrame) -> list[dict]:
    """Trend rows for the Slam point-by-point data: whole period, the two sub-periods around the 2014-15 low, round fixed effects."""
    rows = []
    src = "Slam pbp (USO+Wimb)"
    for g in ("women", "men"):
        gm = core_m[core_m["gender"] == g]; gs = core_s[core_s["gender"] == g]
        specs = [(gm, "sec_per_point", "C(slam)"), (gm, "points_per_game", "C(slam)"), (gm, "game_sec", "C(slam)"),
                 (gs, "set_minutes", "C(slam) + C(set_no)"), (gs, "n_points", "C(slam) + C(set_no)"),
                 (gm, "points", "C(slam) + C(n_sets)"), (gm, "minutes", "C(slam) + C(n_sets)"), (gm, "n_sets", "C(slam)")]
        for df, v, ctrl in specs:
            rows += trend_row(g, f"{src}, {PBP_YEARS.start}-{PBP_YEARS.stop - 1}", df, v, "edition", ctrl)
            if v in ("sec_per_point", "game_sec", "minutes", "points_per_game", "points"):
                rows += trend_row(g, f"{src}, {PBP_YEARS.start}-{SLAM_LOW_YEAR}", df[df["year"] <= SLAM_LOW_YEAR], v, "edition", ctrl)
                rows += trend_row(g, f"{src}, {SLAM_LOW_YEAR + 1}-{PBP_YEARS.stop - 1}", df[df["year"] > SLAM_LOW_YEAR], v, "edition", ctrl)
        for v, ctrl in (("sec_per_point", "C(slam) + C(round_no)"), ("points_per_game", "C(slam) + C(round_no)"), ("game_sec", "C(slam) + C(round_no)"),
                        ("points", "C(slam) + C(n_sets) + C(round_no)"), ("minutes", "C(slam) + C(n_sets) + C(round_no)")):
            rows += trend_row(g, f"{src}, + round fixed effects", gm.dropna(subset=["round_no"]), v, "edition", ctrl)
        rows += trend_row(g, "Slam pbp (all Slams with scores)", m[m["gender"] == g], "points_per_game", "edition", "C(slam)")
    return rows


def tour_trend_rows(dfull: pd.DataFrame) -> list[dict]:
    """Trend rows for the tour/Challenger files: whole period (with a 2013 step allowed for the files that have one),
    and the periods before / from 2013."""
    rows = []
    for gname in GROUPS:
        gd = dfull[dfull["group"] == gname]
        ctrl_sets = "C(n_sets)" + (" + C(level_group)" if gname != "Challenger" else "")
        first = int(gd["year"].min())
        for v in ("minutes", "points", "sec_per_point", "points_per_game", "games_per_set", "minutes_per_set", "sets"):
            ctrl = ctrl_sets if v != "sets" else ("C(level_group)" if gname != "Challenger" else "")
            for log in ((False, True) if v in ("minutes", "points", "sec_per_point") else (False,)):
                src = f"tour/Challenger files ({first}-{LAST_FULL_TML_YEAR})" + (", log" if log else "")
                if gname in STEP_GROUPS and v in ("minutes", "sec_per_point", "minutes_per_set"):
                    # one-off drop in 2013 (ATP stricter 25-second rule enforcement): allow a level shift in the whole-period trend
                    d2 = gd.assign(step=(gd["year"] >= tml.RULE_STEP_YEAR).astype(int))
                    res = {"whole (2013 step allowed)": trends.trend_per_decade(d2, v, "edition", (ctrl + " + " if ctrl else "") + "step", y0=first, log=log)}
                    res["whole, no step term"] = trends.trend_per_decade(gd, v, "edition", ctrl, y0=first, log=log)
                else:
                    res = {"whole": trends.trend_per_decade(gd, v, "edition", ctrl, y0=first, log=log)}
                for lab, part in (("before 2013", gd[gd["year"] < tml.RULE_STEP_YEAR]), ("since 2013", gd[gd["year"] >= tml.RULE_STEP_YEAR])):
                    try:
                        res[lab] = trends.trend_per_decade(part, v, "edition", ctrl, y0=int(part.dropna(subset=[v])["year"].min()), log=log)
                    except Exception as e:             # no data (WTA minutes before 2016) or too few years
                        res[lab] = {"n": int(part[v].notna().sum()), "per_decade": np.nan, "error": str(e)}
                for lab, r in res.items():
                    rows.append({"source": src, "group": gname, "outcome": v, "years": lab, **r})
    for gname in ("ATP bo5", "WTA"):                             # Slams only (cross-check against the point-by-point clock)
        gd = dfull[(dfull["group"] == gname) & (dfull["level_group"] == "Slam")]
        for v in ("minutes", "points", "sec_per_point"):
            for tag, dd in (("all years", gd), ("excl. 2020", gd[gd["year"] != 2020])):
                rows.append({"source": "tour files, Slams only", "group": gname + " (Slams only)", "outcome": v, "years": tag,
                             **trends.trend_per_decade(dd, v, "edition", "C(n_sets)", y0=int(dd["year"].min()))})
    return rows


GROUPS = ["WTA", "ATP bo3", "ATP bo5", "Challenger"]       # display order
STEP_GROUPS = ("ATP bo3", "ATP bo5", "Challenger")        # tour-file match times show the 2013 drop (clearest in best-of-3 and Challenger)
RULE_STEP = tml.RULE_STEP_YEAR
SLAM_LOW_YEAR = 2015                                        # end of the 2011-15 fall in time per point at the Slams


def main() -> None:
    FIG_DIR.mkdir(exist_ok=True); RES_DIR.mkdir(exist_ok=True)
    # ---------------- point-by-point Slam data ----------------
    S = pbp.process_slam_files(PBP_YEARS)
    m, sets = build_slam_match_frame(S)
    S.coverage.to_csv(RES_DIR / "slam_file_coverage.csv", index=False)
    cl = slam_cleaning_table(S, S.matches, m, sets); cl.to_csv(RES_DIR / "cleaning_slam_pbp.csv", index=False)
    final_set_check(S).to_csv(RES_DIR / "final_set_tiebreak_check.csv", index=False)
    core_m = m[m["slam"].isin(CORE)]; core_s = sets[sets["slam"].isin(CORE)]

    ys = {}
    for name, df, val in (("sec_per_point", core_m, "sec_per_point"), ("points_per_game", core_m, "points_per_game"),
                          ("game_sec", core_m, "game_sec"), ("set_minutes", core_s, "set_minutes"),
                          ("set_points", core_s, "n_points"), ("match_minutes", core_m, "minutes"), ("match_points", core_m, "points")):
        ys[name] = trends.yearly_summary(df, val, ["gender"]); ys[name].to_csv(RES_DIR / f"yearly_pbp_{name}.csv", index=False)
    trends.yearly_summary(core_m, "points", ["gender", "n_sets"]).to_csv(RES_DIR / "yearly_pbp_match_points_by_sets.csv", index=False)
    bysets_min = trends.yearly_summary(core_m, "minutes", ["gender", "n_sets"]); bysets_min.to_csv(RES_DIR / "yearly_pbp_match_minutes_by_sets.csv", index=False)
    bysets_pts = trends.yearly_summary(core_m, "points", ["gender", "n_sets"])
    SLAM_LABEL = {"usopen": "US Open", "wimbledon": "Wimbledon", "ausopen": "Australian Open", "frenchopen": "French Open"}
    byslam = trends.yearly_summary(m.assign(slam=m["slam"].map(SLAM_LABEL)), "sec_per_point", ["gender", "slam"]); byslam.to_csv(RES_DIR / "yearly_pbp_sec_per_point_by_slam.csv", index=False)
    byslam_ppg = trends.yearly_summary(m, "points_per_game", ["gender", "slam"]); byslam_ppg.to_csv(RES_DIR / "yearly_pbp_points_per_game_by_slam.csv", index=False)
    all_ppg = trends.yearly_summary(m, "points_per_game", ["gender"])

    def tab(t: pd.DataFrame, **flt) -> pd.DataFrame:
        for k, v in flt.items():
            t = t[t[k] == v]
        return t

    sub = "Grand Slam singles (US Open + Wimbledon), point-by-point data"
    WM = ("women", "men")
    plots.series_figure({g: tab(ys["sec_per_point"], gender=g) for g in WM},
        "At the Slams, time between points fell until 2014-15 and has risen since", "Seconds per point (median of match medians)", FIG_DIR / "fig1_seconds_per_point.png")
    plots.series_figure({g: tab(all_ppg, gender=g) for g in WM},
        "Points per game at the Slams have stayed at about 6.1 (men) and 6.4 (women)", "Points per game (median of match means)", FIG_DIR / "figA1_points_per_game.png")
    plots.series_figure({g: tab(ys["game_sec"], gender=g) for g in WM},
        "Slam games are longer than at the 2014-15 low, but not longer than in 2011", "Seconds per game", FIG_DIR / "figA10_game_duration.png")
    plots.panel_figure({"Set duration (minutes)": {g: tab(ys["set_minutes"], gender=g) for g in WM},
                        "Points per set": {g: tab(ys["set_points"], gender=g) for g in WM}},
        "Slam sets took less time until 2014-15 and have lasted longer since; points per set are flat", "median per set", FIG_DIR / "figA2_set_duration_points.png")
    for name, t, lab in (("points", bysets_pts, "Points per match"), ("minutes", bysets_min, "Minutes per match (clock)")):
        panels = {"Women (best of 3)": {f"women {int(k)} sets": tab(t, gender="women", n_sets=k) for k in (2, 3)},
                  "Men (best of 5)": {f"men {int(k)} sets": tab(t, gender="men", n_sets=k) for k in (3, 4, 5)}}
        title = ("With the same number of sets, Slam matches are longer than in 2014-15 but not than in 2011" if name == "minutes"
                 else "Points per Slam match, by number of sets played, show no clear change")
        plots.panel_figure(panels, title, lab, FIG_DIR / (f"figA9_{name}_per_match_by_format.png" if name == "minutes" else f"figA3_{name}_per_match_by_format.png"))
    plots.panel_figure({"Women": {s: tab(byslam, gender="women", slam=s) for s in SLAM_LABEL.values()},
                        "Men": {s: tab(byslam, gender="men", slam=s) for s in SLAM_LABEL.values()}},
        "Seconds per point by Slam (the Australian and French Open clock exists only to 2017)", "Seconds per point",
        FIG_DIR / "figA4_seconds_per_point_by_slam.png")

    rows = slam_trend_rows(core_m, core_s, m)
    # ---------------- tour-level and Challenger files ----------------
    raw = tml.load_tml(TML_YEARS)
    d = prep_tml(raw)
    tml_cleaning_table(raw, d).to_csv(RES_DIR / "cleaning_tml.csv", index=False)
    d = apply_tml_trims(d)
    d = tml.blank_low_coverage(d, ["minutes", "minutes_per_set", "minutes_per_game", "sec_per_point"], ["group", "year"])
    cov = (d.groupby(["group", "year"]).agg(matches=("year", "size"), with_minutes=("minutes", lambda s: s.notna().mean()),
                                            with_points=("points", lambda s: s.notna().mean())).reset_index())
    cov.round(3).to_csv(RES_DIR / "tml_minutes_points_coverage.csv", index=False)
    metrics = ["minutes", "points", "sec_per_point", "points_per_game", "games_per_set", "sets", "minutes_per_set", "minutes_per_game"]
    yt = {}
    for k in metrics:
        yt[k] = trends.yearly_summary(d, k, ["group"]); yt[k].to_csv(RES_DIR / f"yearly_tml_{k}.csv", index=False)
    bs = {k: trends.yearly_summary(d, k, ["group", "n_sets"]) for k in ("minutes", "points")}
    for k, t in bs.items():
        t.to_csv(RES_DIR / f"yearly_tml_{k}_by_sets.csv", index=False)
    slam_tml = d[d["level_group"] == "Slam"]
    for k in ("minutes", "points", "sec_per_point"):
        trends.yearly_summary(slam_tml, k, ["group"]).to_csv(RES_DIR / f"yearly_tml_slam_{k}.csv", index=False)
    surf = trends.yearly_summary(d[(d["year"] <= LAST_FULL_TML_YEAR) & d["tour"].isin(["ATP", "WTA"]) & d["surface"].isin(["Hard", "Clay", "Grass"])].assign(g2=lambda x: x["tour"] + " " + x["surface"]), "sec_per_point", ["g2"])
    surf.to_csv(RES_DIR / "yearly_tml_sec_per_point_by_surface.csv", index=False)

    step_rows = []                                   # evidence on the 2013 drop in tour-level match times
    chk = d[d["year"].between(RULE_STEP - 2, RULE_STEP + 1)]
    def _row(lab: str, xx: pd.DataFrame, y: int) -> dict:
        return {"subset": lab, "year": y, "n": len(xx), "median_minutes": xx["minutes"].median(), "median_points": xx["points"].median(),
                "median_sec_per_point": xx["sec_per_point"].median()}
    for (g, sf), x in chk[chk["group"].isin(["ATP bo3", "Challenger"]) & chk["surface"].isin(["Hard", "Clay", "Grass"])].groupby(["group", "surface"]):
        for y, xx in x.groupby("year"):
            step_rows.append(_row(f"{g}, {sf}", xx, y))
    slam_atp = chk[(chk["group"] == "ATP bo5") & (chk["level_group"] == "Slam")]
    for k in (3, 4, 5):
        for y, xx in slam_atp[slam_atp["n_sets"] == k].groupby("year"):
            step_rows.append(_row(f"ATP Slam matches, {k} sets", xx, y))
    for nm, pat in (("Australian Open", "australian"), ("French Open", "roland|french"), ("US Open", "us open"), ("Wimbledon", "wimbledon")):
        s = slam_atp[slam_atp["tourney_name"].astype(str).str.lower().str.contains(pat)]
        for y, xx in s.groupby("year"):
            step_rows.append(_row(f"ATP Slam: {nm}", xx, y))
    pd.DataFrame(step_rows).to_csv(RES_DIR / "tml_2013_step_check.csv", index=False)
    # within tournaments: tournaments played in both 2012 and 2013 (name-matched)
    import statsmodels.formula.api as smf
    wt = []
    for g in ("ATP bo3", "Challenger"):
        x = d[(d["group"] == g) & d["year"].isin([RULE_STEP - 1, RULE_STEP]) & d["sec_per_point"].notna()].copy()
        x["tn"] = x["tourney_name"].astype(str).str.lower().str.replace(r"[^a-z0-9]", "", regex=True)
        both = x.groupby("tn")["year"].nunique(); x = x[x["tn"].isin(both[both == 2].index)]
        med = x.groupby(["tn", "year"])["sec_per_point"].median().unstack()
        x["post"] = (x["year"] == RULE_STEP).astype(int)
        res = smf.ols("sec_per_point ~ post + C(tn)", x).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(x["tn"])[0]})
        lo_, hi_ = res.conf_int().loc["post"]
        wt.append({"group": g, "tournaments": int(len(med)), "tournaments_lower_in_2013": int((med[RULE_STEP] < med[RULE_STEP - 1]).sum()),
                   "median_change_s": float((med[RULE_STEP] - med[RULE_STEP - 1]).median()), "step_s": float(res.params["post"]),
                   "ci_lo": float(lo_), "ci_hi": float(hi_)})
    pd.DataFrame(wt).to_csv(RES_DIR / "tml_2013_within_tournament.csv", index=False)
    groups = GROUPS
    tab_y = lambda t: t[t["year"] <= LAST_FULL_TML_YEAR]      # 2026 is a part season: left out of the main tour figures
    plots.series_figure({g: tab(tab_y(yt["sec_per_point"]), group=g) for g in groups},
        "Time per point has been rising since the late 1990s, and faster since 2013", "Seconds per point (median match)",
        FIG_DIR / "fig2_tour_seconds_per_point.png", tour=True)
    plots.series_figure({g: tab(tab_y(yt["points"]), group=g) for g in groups},
        "Points per match have stayed about the same for 30 years", "Points per match (median match)",
        FIG_DIR / "fig3_tour_points_per_match.png", tour=True)
    plots.series_figure({g: tab(tab_y(yt["minutes"]), group=g) for g in groups},
        "Matches last longer than in the 1990s, and the rise has been steeper since 2013", "Minutes per match (median match)",
        FIG_DIR / "fig4_tour_minutes_per_match.png", tour=True)
    for name, t, lab, fn in (("minutes", bs["minutes"], "Minutes per match", "figA5_tml_minutes_by_sets.png"),
                             ("points", bs["points"], "Points per match", "figA6_tml_points_by_sets.png")):
        panels = {}
        for gname in groups:
            panels[gname] = {f"{gname} {int(k)} sets": tab(t, group=gname, n_sets=k) for k in sorted(t[t.group == gname].n_sets.unique())}
        ttl = ("For the same number of sets, matches last longer than in earlier years on every tour (2026 is a part season)" if name == "minutes"
               else "For the same number of sets, points per match show no clear change (2026 is a part season)")
        plots.panel_figure(panels, ttl, lab, FIG_DIR / fn, None, tour=True)
    bo3 = ["WTA", "ATP bo3", "Challenger"]
    plots.panel_figure({"Sets per match: best-of-3": {g: tab(yt["sets"], group=g) for g in bo3},
                        "Sets per match: ATP best-of-5": {"ATP bo5": tab(yt["sets"], group="ATP bo5")},
                        "Games per set": {g: tab(yt["games_per_set"], group=g) for g in groups},
                        "Points per game": {g: tab(yt["points_per_game"], group=g) for g in groups}},
        "Sets per match, games per set and points per game change very little (tour-level and Challenger matches)", "mean per match",
        FIG_DIR / "figA11_tml_composition.png", None, stat="mean", tour=True)
    plots.panel_figure({"WTA": {k.replace("WTA ", ""): tab(surf, g2=k) for k in ("WTA Hard", "WTA Clay", "WTA Grass")},
                        "ATP": {k.replace("ATP ", ""): tab(surf, g2=k) for k in ("ATP Hard", "ATP Clay", "ATP Grass")}},
        "Time per point has risen on hard, clay and grass courts alike", "Seconds per point", FIG_DIR / "figA8_tml_seconds_per_point_by_surface.png",
        None, tour=True)

    dfull = d[d["year"] <= LAST_FULL_TML_YEAR]
    rows += tour_trend_rows(dfull)
    tt = pd.DataFrame(rows); tt.to_csv(RES_DIR / "trend_tests.csv", index=False)
    json.dump({"slam_pbp_matches_used": int(len(core_m)), "tml_matches_used": int(len(d))}, open(RES_DIR / "sample_sizes.json", "w"))
    pd.set_option("display.width", 200)
    print(cl.to_string(index=False)); print(tml_cleaning_table(raw, prep_tml(raw)).to_string(index=False))
    print(tt[tt.years.isin(["all years", "whole", "whole (2013 step allowed)", "before", "since"])][["source", "group", "outcome", "years", "n", "per_decade", "ci_lo", "ci_hi", "p"]].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
