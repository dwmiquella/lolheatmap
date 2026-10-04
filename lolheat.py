"""Compatibility exports for scripts written against the original module."""

from heatmap.analysis import build_game, points, summarize, summarize_sums, sums
from heatmap.benchmark import bench_entry, bench_meta
from heatmap.config import CACHE, INTERVAL, KINDS, MAP, ROLES, ROUTES, TIERS
from heatmap.plots import density, fig_compare, fig_compare_pre, fig_grid
from heatmap.riot_client import Riot, RiotError, benchmark, collect

__all__ = [
    "build_game",
    "points",
    "summarize",
    "summarize_sums",
    "sums",
    "bench_entry",
    "bench_meta",
    "CACHE",
    "INTERVAL",
    "KINDS",
    "MAP",
    "ROLES",
    "ROUTES",
    "TIERS",
    "density",
    "fig_compare",
    "fig_compare_pre",
    "fig_grid",
    "Riot",
    "RiotError",
    "benchmark",
    "collect",
]
