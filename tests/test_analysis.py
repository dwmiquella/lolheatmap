import matplotlib.pyplot as plt
import numpy as np
import pytest

from heatmap.analysis import filter_games, points, time_buckets
from heatmap.config import MAP
from heatmap.demo import demo_games
from heatmap.plots import comparison_figure, density


def test_comparison_selection_excludes_other_roles_queues_and_champions():
    base = demo_games()[0]
    games = [base, {**base, "role": "UTILITY"}, {**base, "queue": 440}, {**base, "champ": "Lux"}]
    assert filter_games(games, "Ahri", "MIDDLE", queue=420) == [base]


def test_result_and_side_filters():
    gs = demo_games()
    expected = [g for g in gs if g["win"] and g["team"] == 100]
    assert filter_games(gs, result="Win", side="Blue") == expected


def test_positions_default_to_samples_and_rotate_red():
    g = {"team": 200, "pos": [[0, 100, 200], [60000, 300, 400]]}
    actual = points([g], "pos", mirror=True)
    np.testing.assert_array_equal(actual, MAP - np.array([[100, 200], [300, 400]]))
    assert len(points([g], "pos", interpolate=True)) == 13


def test_events_use_half_open_windows_without_double_counting():
    g = {"team": 100, "ev": [[300000, 500, 600, "k"]]}
    assert len(points([g], "k", 0, 5)) == 0
    assert len(points([g], "k", 5, 10)) == 1


@pytest.mark.parametrize("lo,hi", [(5, 5), (10, 5), (-1, 5)])
def test_invalid_comparison_windows(lo, hi):
    with pytest.raises(ValueError, match="end time"):
        time_buckets(lo, hi)


def test_buckets_include_late_game_and_snap_outward():
    assert time_buckets(6, 9) == ([1], 5, 10)
    assert time_buckets(45, 55) == ([8], 40, float("inf"))


def test_density_is_normalized_and_empty_is_finite():
    pts = np.array([[1000, 2000], [3000, 4000]])
    assert density(pts).sum() == pytest.approx(1)
    np.testing.assert_allclose(density(pts), density(np.tile(pts, (5, 1))))
    assert np.isfinite(density(np.empty((0, 2)))).all()
    assert density(np.empty((0, 2))).sum() == 0


def test_comparison_uses_shared_color_scale():
    da, db = np.zeros((3, 3)), np.zeros((3, 3))
    da[0, 0], da[1, 1], db[0, 0] = 0.5, 0.5, 1
    fig = comparison_figure(da, db, "k", 2, 1)
    assert fig.axes[0].images[-1].norm.vmax == fig.axes[1].images[-1].norm.vmax == 1
    plt.close(fig)


def test_missing_samples_do_not_create_misleading_difference():
    fig = comparison_figure(np.zeros((3, 3)), np.ones((3, 3)) / 9, "d", 0, 9)
    assert fig.axes[2].get_title() == "Difference unavailable"
    plt.close(fig)
