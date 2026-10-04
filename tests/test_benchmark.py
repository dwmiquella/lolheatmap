import json
import sys

import matplotlib.pyplot as plt
import numpy as np
import pytest

import build_benchmark
from heatmap import plots
from heatmap.analysis import points
from heatmap.demo import demo_games


@pytest.mark.parametrize("method,expected", [("sampled", 5), ("interpolated", 60)])
def test_prebuilt_comparison_matches_reference_sampling(monkeypatch, method, expected):
    monkeypatch.setattr(plots, "bench_meta", lambda: {"bins": 60, "position_method": method})
    game = demo_games()[0]
    assert len(points([game], "pos", 0, 5, interpolate=method == "interpolated")) == expected
    grid = np.zeros((4, 9, 60, 60), dtype=np.uint32)
    grid[0, 0, 10, 10] = expected
    fig = plots.fig_compare_pre([game], {"grid": grid}, "pos", 0, 5, 2)
    assert str(expected) in fig.axes[0].get_title()
    plt.close(fig)


def test_builder_records_provenance_and_no_duplicate_matches(tmp_path, monkeypatch):
    game = demo_games()[0]
    output = tmp_path / "reference.npz"

    class Client:
        def __init__(self, *args):
            pass

        def high_elo(self, *args):
            return [game["puuid"]]

        def match_ids(self, *args):
            return ["one", "one"]

        def match(self, mid):
            return {"map": 11, "dur": game["dur"], "ver": "16.19.1", "queue": 420, "players": [game]}

        def timeline(self, mid):
            return {"pos": {"1": game["pos"]}, "ev": []}

    monkeypatch.setattr(build_benchmark.lh, "Riot", Client)
    monkeypatch.setenv("RIOT_API_KEY", "test-only")
    monkeypatch.setattr(sys, "argv", ["build_benchmark.py", "--min-games", "1", "--out", str(output)])
    build_benchmark.main()
    with np.load(output) as bundle:
        meta = json.loads(str(bundle["meta"]))
        assert meta["matches"] == 1
        assert meta["unique_players"] == 1
        assert meta["cohort_unique_players"] == {"Ahri_MIDDLE": 1}
        assert meta["patch_counts"] == {"16.19": 1}
        assert meta["region_matches"] == {"na1": 1}
        assert meta["position_method"] == "sampled"
        assert meta["queue"] == 420
        assert bundle["Ahri_MIDDLE"][0].sum() == len(game["pos"])
