"""Static heatmaps with shared comparison scales and explicit empty states."""

from functools import lru_cache
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize
from matplotlib.ticker import PercentFormatter
from scipy.ndimage import gaussian_filter

from .analysis import points, time_buckets
from .benchmark import bench_meta
from .config import KINDS, MAP


@lru_cache(maxsize=1)
def map_image():
    path = Path(__file__).resolve().parent.parent / "assets" / "map11.png"
    return plt.imread(path) if path.exists() else None


def density(pts, bins=100, sigma=2.0):
    hist, _, _ = np.histogram2d(pts[:, 0], pts[:, 1], bins=bins, range=[[0, MAP], [0, MAP]])
    hist = gaussian_filter(hist, sigma)
    return hist / hist.sum() if hist.sum() else hist


def draw(ax, data, title, cmap="inferno", diverge=False, vmax=None, empty="No events in this window"):
    img = map_image()
    if img is not None:
        ax.imshow(img, extent=[0, MAP, 0, MAP], zorder=0)
    ax.set(xlim=(0, MAP), ylim=(0, MAP), aspect="equal", title=title)
    ax.axis("off")
    vmax = vmax or float(np.abs(data).max()) or 1.0
    norm = Normalize(-vmax if diverge else 0, vmax)
    palette = "coolwarm" if diverge else cmap
    if np.any(data):
        masked = np.ma.masked_where(np.abs(data) < vmax * 0.05, data)
        ax.imshow(
            masked.T,
            origin="lower",
            extent=[0, MAP, 0, MAP],
            cmap=palette,
            norm=norm,
            alpha=0.78,
            interpolation="bilinear",
        )
    else:
        ax.text(
            0.5,
            0.5,
            empty,
            transform=ax.transAxes,
            ha="center",
            va="center",
            color="white",
            bbox={"facecolor": "#18212e", "alpha": 0.9, "pad": 10},
        )
    return ScalarMappable(norm=norm, cmap=palette)


def sample_label(kind, n, interpolate=False):
    unit = (
        ("estimated samples" if interpolate else "recorded positions")
        if kind == "pos"
        else KINDS[kind][0].lower()
    )
    return f"{n:,} {unit}"


def colorbar(fig, scalar, axes, label):
    bar = fig.colorbar(scalar, ax=axes, shrink=0.72, pad=0.025, format=PercentFormatter(1))
    bar.set_label(label, fontsize=9)


def fig_single(games, kind, lo, hi, mirror, sigma, interpolate=False, bins=100):
    pts = points(games, kind, lo, hi, mirror, interpolate=interpolate)
    fig, ax = plt.subplots(figsize=(8, 7), layout="constrained")
    scalar = draw(
        ax,
        density(pts, bins, sigma),
        f"{KINDS[kind][0]} · {sample_label(kind, len(pts), interpolate)}",
        KINDS[kind][1],
        empty=f"No {KINDS[kind][0].lower()} in this window",
    )
    colorbar(fig, scalar, ax, "Share of selected samples per grid cell")
    return fig


def fig_grid(games, lo, hi, mirror, sigma, bins=100, interpolate=False):
    fig, axes = plt.subplots(2, 2, figsize=(11, 10), layout="constrained")
    for ax, kind in zip(axes.flat, KINDS):
        pts = points(games, kind, lo, hi, mirror, interpolate=interpolate)
        scalar = draw(
            ax,
            density(pts, bins, sigma),
            sample_label(kind, len(pts), interpolate),
            KINDS[kind][1],
            empty=f"No {KINDS[kind][0].lower()} in this window",
        )
        colorbar(fig, scalar, ax, "Share per cell")
    return fig


def comparison_figure(da, db, kind, na, nb, interpolate=False):
    fig, axes = plt.subplots(1, 3, figsize=(15, 5.4), layout="constrained")
    vmax = max(float(da.max()), float(db.max()), 1e-12)
    scalar = draw(axes[0], da, f"You · {sample_label(kind, na, interpolate)}", KINDS[kind][1], vmax=vmax)
    draw(axes[1], db, f"Reference · {sample_label(kind, nb, interpolate)}", KINDS[kind][1], vmax=vmax)
    colorbar(fig, scalar, list(axes[:2]), "Share per cell · shared scale")
    if na and nb:
        delta = draw(axes[2], da - db, "You minus reference", diverge=True, empty="Identical distributions")
        colorbar(fig, delta, axes[2], "Share difference · red: more / blue: less")
    else:
        draw(axes[2], np.zeros_like(da), "Difference unavailable", empty="Both groups need samples")
    return fig


def fig_compare(mine, bench, kind, lo, hi, mirror=True, sigma=2.0, bins=100, interpolate=False):
    a, b = (points(g, kind, lo, hi, mirror, interpolate=interpolate) for g in (mine, bench))
    return comparison_figure(
        density(a, bins, sigma), density(b, bins, sigma), kind, len(a), len(b), interpolate
    )


def fig_compare_pre(mine, entry, kind, lo, hi, sigma):
    meta = bench_meta()
    bins = meta["bins"]
    blur = sigma * bins / 100
    buckets, start, end = time_buckets(lo, hi)
    # Legacy bundles used interpolation. Match that method rather than silently
    # comparing recorded positions to a differently constructed distribution.
    interpolate = meta.get("position_method", "interpolated") == "interpolated"
    pts = points(mine, kind, start, end, mirror=True, interpolate=interpolate)
    raw = entry["grid"][list(KINDS).index(kind)][buckets].sum(0).astype(float)
    ref = gaussian_filter(raw, blur)
    ref = ref / ref.sum() if ref.sum() else ref
    return comparison_figure(density(pts, bins, blur), ref, kind, len(pts), int(raw.sum()), interpolate)
