"""Tests for tennis.paths and tennis.plotting."""
import hashlib

import matplotlib.pyplot as plt

from tennis import paths, plotting


def test_repo_root_and_data_locations():
    assert (paths.REPO_ROOT / "pyproject.toml").is_file()
    assert paths.TML_DIR == paths.DATA_ROOT / "tml-data"
    assert paths.PBP_SLAM_DIR == paths.DATA_ROOT / "pbp-data" / "slam"
    assert paths.CHARTING_DIR == paths.DATA_ROOT / "pbp-data" / "charting"
    assert set(paths.SLAM_ORDER) == set(paths.SLAM_NAMES) == set(paths.SLAM_SURFACE) == set(paths.SLAM_LABEL)


def test_analysis_dirs_creates_results_and_figures_only(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "ANALYSES_DIR", tmp_path)
    res, fig, cache = paths.analysis_dirs("demo")
    assert res.is_dir() and fig.is_dir() and not cache.exists()
    assert res.parent == tmp_path / "demo"


def test_house_colours():
    assert plotting.MEN == "#0072B2" and plotting.WOMEN == "#E69F00"
    assert set(plotting.OKABE_ITO.values()) == {"#0072B2", "#E69F00", "#D55E00", "#009E73", "#56B4E9", "#CC79A7",
                                               "#F0E442", "#000000"}


def test_save_figure_is_reproducible_and_closes(tmp_path):
    def draw(path):
        fig, ax = plotting.new_figure(figsize=(3, 2))
        ax.plot([0, 1], [0, 1], color=plotting.MEN, marker="o")
        ax.set_title("t")
        n_before = len(plt.get_fignums())
        plotting.save_figure(fig, path)
        assert len(plt.get_fignums()) == n_before - 1                  # figure closed
        return hashlib.md5(path.read_bytes()).hexdigest()
    assert draw(tmp_path / "a.png") == draw(tmp_path / "b.png")      # no timestamp / software stamp
    assert not list(tmp_path.glob("*.tmp.png"))


def test_wrap():
    assert max(len(line) for line in plotting.wrap("word " * 40, 30).splitlines()) <= 30


def test_reader_helpers(tmp_path):
    fig, ax = plotting.new_figure(figsize=(3, 2))
    ax.plot([0, 1], [0.4, 0.6])
    plotting.faint_band(ax, [0, 1], [0.35, 0.55], [0.45, 0.65], plotting.WOMEN)
    t = plotting.label_hline(ax, 0.5, "coin flip")
    plotting.label_vline(ax, 0.5, "rule change")
    plotting.percent_axis(ax)
    plotting.light_grid(ax)
    assert t.get_text() == "coin flip" and ax.collections[0].get_alpha() <= 0.15
    assert ax.yaxis.get_major_formatter().format_pct(0.5, 1) .startswith("50")
    plotting.save_figure(fig, tmp_path / "r.png")
