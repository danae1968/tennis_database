"""Tests for tennis.load (on small synthetic files, so they run without the raw data)."""
import pandas as pd
import pytest

from tennis import load


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def test_tml_paths_and_year_files(tmp_path):
    assert load.tml_path(2020, "ATP", tmp_path).name == "2020.csv"
    assert load.tml_path(2020, "WTA", tmp_path).name == "2020_wta.csv"
    assert load.tml_path(2020, "Challenger", tmp_path).name == "2020_challenger.csv"
    for name in ("2019.csv", "2020.csv", "2020_wta.csv", "2020_challenger.csv", "ATP_Database.csv", "1990_wta.csv"):
        _write(tmp_path / name, "a\n1\n")
    assert [y for y, _ in load.tml_year_files("ATP", tmp_path)] == [2019, 2020]
    assert [y for y, _ in load.tml_year_files("WTA", tmp_path)] == [1990, 2020]
    assert [y for y, _ in load.tml_year_files("Challenger", tmp_path)] == [2020]


def test_load_tml_years_order_text_and_missing(tmp_path):
    _write(tmp_path / "2020.csv", "winner_id,minutes\n007,90\n")
    _write(tmp_path / "2020_wta.csv", "winner_id,minutes\n200001,80\n")
    _write(tmp_path / "2021.csv", "winner_id,minutes\n008,100\n")
    d = load.load_tml_years([2020, 2021, 2022], kinds=("ATP", "WTA"), tml_dir=tmp_path)
    assert d[["year", "tour"]].values.tolist() == [[2020, "ATP"], [2020, "WTA"], [2021, "ATP"]]
    assert d.winner_id.tolist() == ["007", "200001", "008"]               # text: leading zeros kept
    d2 = load.load_tml_years([2020], kinds=("ATP",), text=False, tml_dir=tmp_path)
    assert d2.minutes.dtype.kind in "if"


@pytest.mark.parametrize("num,expected", [("1101", "M"), ("2405", "W"), ("MS204", "M"), ("WS701", "W"),
                                          ("ms204", "M"), ("3101", None), ("", None)])
def test_gender_from_match_num(num, expected):
    assert load.gender_from_match_num(num) == expected


def test_gender_from_match_id_vectorised():
    g = load.gender_from_match_id(pd.Series(["2023-usopen-1101", "2023-usopen-2101", "2021-ausopen-MS101", "x-y-3101"]))
    assert g.tolist()[:3] == ["M", "W", "M"] and pd.isna(g.iloc[3])


def _slam_fixture(tmp_path):
    _write(tmp_path / "2020-usopen-matches.csv", "match_id,match_num,player1,player2\n2020-usopen-1101,1101,A,B\n2020-usopen-2101,2101,C,D\n")
    _write(tmp_path / "2020-usopen-points.csv",
           "match_id,SetNo,GameNo,PointNumber,PointServer,PointWinner,GameWinner,SetWinner,P1GamesWon,P2GamesWon\n"
           "2020-usopen-1101,1,1,0X,0,0,0,0,0,0\n"
           "2020-usopen-1101,1,1,0Y,0,0,0,0,0,0\n"
           "2020-usopen-1101,1,1,2,1,1,0,0,0,0\n"
           "2020-usopen-1101,1,1,1,1,2,0,0,0,0\n"
           "2020-usopen-2101,1,1,1,2,2,0,0,0,0\n")
    _write(tmp_path / "2020-usopen-matches-doubles.csv", "match_id\nx\n")
    _write(tmp_path / "2020-usopen-points-doubles.csv", "match_id\nx\n")
    _write(tmp_path / "2019-wimbledon-matches.csv", "match_id,match_num,player1,player2\n")   # no points file
    return tmp_path


def test_slam_singles_files_and_matches(tmp_path):
    d = _slam_fixture(tmp_path)
    files = load.slam_singles_files(d)
    assert [(y, s) for y, s, _, _ in files] == [(2020, "usopen")]          # doubles and points-less events skipped
    M = load.load_slam_matches(d)
    assert M.gender.tolist() == ["M", "W"] and M.best_of.tolist() == [5, 3] and (M.surface == "Hard").all()


def test_clean_and_cached_slam_points(tmp_path):
    d = _slam_fixture(tmp_path)
    P, info = load.load_slam_points(cache_dir=tmp_path / "cache", pbp_dir=d)
    assert info["placeholder_rows"] == 2 and len(P) == 3
    first = P[P.match_id == "2020-usopen-1101"]
    assert first.PointNumber.tolist() == [1, 2]                           # sorted by point number
    assert P.dtypes["PointServer"] == "int64"
    assert (tmp_path / "cache" / "points_clean.pkl").exists()
    P2, info2 = load.load_slam_points(cache_dir=tmp_path / "cache", pbp_dir=d)
    pd.testing.assert_frame_equal(P, P2) and info == info2


def test_player_tables(tmp_path):
    atp = _write(tmp_path / "ATP_Database.csv", "id,player,birthdate,ioc\n000001,A B,19930316,TGO\n")
    wta = _write(tmp_path / "players.csv", "player_id,first_name,last_name,hand,birth_date,country_code\n200001,Martina,Hingis,R,19800930,SUI\n")
    a = load.load_atp_players(atp)
    w = load.load_wta_players(wta)
    assert a.iloc[0].tolist() == ["000001", "A B", "19930316", "TGO", "ATP"]
    assert w.iloc[0].tolist() == ["200001", "Martina Hingis", "19800930", "SUI", "WTA"]


def test_charting_paths_and_loader(tmp_path):
    assert load.charting_path("w", "stats-Overview", tmp_path).name == "charting-w-stats-Overview.csv"
    with pytest.raises(ValueError):
        load.charting_path("x", "matches", tmp_path)
    with pytest.raises(ValueError):
        load.charting_path("m", "points", tmp_path)
    _write(tmp_path / "charting-m-matches.csv", "match_id,Player 1\nm1,Nadal\n")
    _write(tmp_path / "charting-w-matches.csv", "match_id,Player 1\nw1,Gauff\n")
    d = load.load_charting("matches", charting_dir=tmp_path)
    assert d.gender.tolist() == ["M", "W"] and d.match_id.tolist() == ["m1", "w1"]
