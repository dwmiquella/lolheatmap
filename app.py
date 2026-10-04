"""Run with: python -m streamlit run app.py."""

import io
import os
import threading

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from heatmap import analysis, benchmark, plots
from heatmap.config import KINDS, QUEUE_NAMES, ROLE_NAMES, ROLES, ROUTES, SERVER_NAMES
from heatmap.demo import demo_games
from heatmap.riot_client import Riot, RiotError, collect

load_dotenv()
st.set_page_config(page_title="LoL Heatmaps", page_icon="🗺️", layout="wide")
ss = st.session_state


@st.cache_resource
def plot_lock():
    return threading.RLock()


@st.cache_data(show_spinner=False, max_entries=32)
def render_chart(mode, games, kind, lo, hi, mirror, sigma, interpolate, champion="", role=""):
    with plot_lock():
        if mode == "compare":
            fig = plots.fig_compare_pre(games, benchmark.bench_entry(champion, role), kind, lo, hi, sigma)
        elif mode == "grid":
            fig = plots.fig_grid(games, lo, hi, mirror, sigma, interpolate=interpolate)
        else:
            fig = plots.fig_single(games, kind, lo, hi, mirror, sigma, interpolate)
        output = io.BytesIO()
        fig.savefig(output, format="png", dpi=130, facecolor="white")
        plt.close(fig)
        return output.getvalue()


def reset_filters():
    for name in ("champ", "role", "result", "side", "window", "mirror", "sigma", "interpolate"):
        ss.pop(name, None)


def activate(games, name, platform, queue, demo=False, warnings=None):
    ss.games = games
    ss.context = {"name": name, "platform": platform, "queue": queue, "demo": demo}
    ss.load_warnings = warnings or []
    reset_filters()
    for name in ("compare_champ", "compare_role", "compare_window"):
        ss.pop(name, None)


st.title("LoL Heatmaps")
st.write("See where you play, where fights happen, and how your patterns compare with a high-elo reference.")
# Never put the server's secret into a browser widget.
server_key = os.environ.get("RIOT_API_KEY", "")
if not server_key:
    try:
        server_key = st.secrets.get("RIOT_API_KEY", "")
    except FileNotFoundError:
        pass
with st.expander("Connect your account", expanded="games" not in ss):
    with st.form("player_search"):
        col1, col2, col3 = st.columns([2, 1, 1])
        rid = col1.text_input("Riot ID", placeholder="Name#TAG")
        platform = col2.selectbox("Server", list(ROUTES), format_func=SERVER_NAMES.get)
        queue = col3.selectbox("Queue", list(QUEUE_NAMES), format_func=QUEUE_NAMES.get)
        count = st.slider("Recent matches to check", 10, 100, 30, step=10)
        user_key = ""
        if not server_key:
            user_key = st.text_input(
                "Riot API key",
                type="password",
                help="For local use, get a key at developer.riotgames.com or set RIOT_API_KEY in .env.",
            )
        else:
            st.caption("API access is configured by the app host.")
        go = st.form_submit_button("Analyze player", type="primary")
    if st.button("Explore demo", help="12 fictional matches. No API key needed."):
        activate(demo_games(), "Demo player", "na1", 420, demo=True)

if go:
    key = server_key or user_key
    if not key or "#" not in rid:
        st.error("Enter a Riot ID in Name#TAG format and configure an API key.")
    else:
        progress = st.progress(0.0, "Looking up player…")
        status = st.empty()
        try:
            client = Riot(key, platform, status=status.info)
            puuid = client.puuid(rid)
            ids = client.match_ids(puuid, count, queue)
            warnings = []
            games = collect(client, puuid, ids, tick=lambda f, t: progress.progress(f, t), warnings=warnings)
            activate(games, rid.strip(), platform, queue, warnings=warnings)
        except RiotError as exc:
            st.error(str(exc))
            if "games" in ss:
                st.info("Your previous results are still shown below.")
        finally:
            progress.empty()
            status.empty()

if "games" not in ss:
    st.info("Analyze your recent matches or choose Explore demo to try the app immediately.")
    st.markdown("**1. Load matches** · **2. Explore your map** · **3. Compare the same champion and role**")
    st.stop()

games = ss.games
ctx = ss.context
st.subheader(ctx["name"])
st.caption(
    f"Loaded results · {SERVER_NAMES[ctx['platform']]} · {QUEUE_NAMES[ctx['queue']]} · {len(games)} games"
)
if ctx["demo"]:
    st.info(
        "Demo mode: these matches are fictional and illustrate the interface, not real player performance."
    )
for warning in ss.load_warnings:
    st.warning(warning)
if not games:
    st.warning("No eligible Summoner’s Rift games found. Try another queue or check more recent matches.")
    st.stop()

with st.sidebar:
    st.header("Explore filters")
    st.caption("Applies to Your heatmap and Champions. Comparison has its own controls.")
    st.button("Reset filters", on_click=reset_filters)
    champ = st.selectbox("Champion", ["All"] + sorted({g["champ"] for g in games}), key="champ")
    role = st.selectbox("Role", ["All"] + ROLES, format_func=ROLE_NAMES.get, key="role")
    result = st.radio("Result", ["All", "Win", "Loss"], horizontal=True, key="result")
    side = st.radio("Side", ["All", "Blue", "Red"], horizontal=True, key="side")
    lo, end = st.slider(
        "Game window (minutes)",
        0,
        60,
        (0, 60),
        key="window",
        help="60 means through the end of the game. Applies to maps only.",
    )
    with st.expander("Advanced"):
        mirror = st.checkbox("Rotate red side onto blue", True, key="mirror")
        sigma = st.slider("Smoothing", 1.0, 5.0, 2.0, 0.5, key="sigma")
        interpolate = st.checkbox(
            "Estimate positions between samples",
            False,
            key="interpolate",
            help="Straight-line estimates can cross terrain, recalls, and teleports.",
        )
hi = float("inf") if end == 60 else end
filtered = analysis.filter_games(games, champ, role, result, side)
tab = st.radio(
    "View", ["Your heatmap", "Compare", "Champions"], horizontal=True, label_visibility="collapsed"
)

if tab != "Compare":
    st.caption(
        f"{len(filtered)} of {len(games)} games · {champ} · {ROLE_NAMES[role]} · {result} results · {side} side"
    )
    if not filtered:
        st.warning("No games match these filters. Use Reset filters to start again.")
        st.stop()
    st.markdown("**Full-game statistics**")
    stats = analysis.summarize(filtered)
    metrics = [
        ("Games", "{:.0f}"),
        ("Win rate %", "{:.0f}%"),
        ("KDA", "{:.2f}"),
        ("CS/min", "{:.1f}"),
        ("Vision/min", "{:.2f}"),
        ("Kill part. %", "{:.0f}%"),
    ]
    for offset in (0, 3):
        for col, (name, fmt) in zip(st.columns(3), metrics[offset : offset + 3]):
            col.metric(name.rstrip(" %"), fmt.format(stats[name]))
    if tab == "Champions":
        rows = [
            {"Champion": c, **analysis.summarize([g for g in filtered if g["champ"] == c])}
            for c in sorted({g["champ"] for g in filtered})
        ]
        frame = pd.DataFrame(rows).sort_values("Games", ascending=False).round(2)
        st.dataframe(frame, hide_index=True, width="stretch")
        st.download_button(
            "Download statistics (CSV)", frame.to_csv(index=False), "champion-stats.csv", "text/csv"
        )
    elif end <= lo:
        st.warning("Choose an end time later than the start time.")
    else:
        kind = st.selectbox("Map layer", list(KINDS), format_func=lambda k: KINDS[k][0])
        overview = st.checkbox("Show all four maps")
        chart = render_chart(
            "grid" if overview else "single", filtered, kind, lo, hi, mirror, sigma, interpolate
        )
        st.image(chart, width="stretch")
        st.caption(
            "Positions are recorded about once per minute. Colors show relative density, not a continuous route. "
            + (
                "Interpolation is enabled: paths are approximate."
                if interpolate
                else "Showing recorded positions only."
            )
        )
        st.download_button("Download heatmap (PNG)", chart, "heatmap.png", "image/png")
else:
    st.subheader("Compare a matching champion and role")
    st.caption(
        "Comparison uses its own selection: all results, both sides, and the reference queue. "
        "Explore filters do not apply here. Both maps rotate red side onto blue."
    )
    meta = benchmark.bench_meta()
    if not meta:
        st.info("No benchmark installed. See the README for how to build one.")
        st.stop()
    c1, c2 = st.columns(2)
    champion = c1.selectbox("Comparison champion", sorted({g["champ"] for g in games}), key="compare_champ")
    roles = sorted({g["role"] for g in games if g["champ"] == champion and g["role"] in ROLES})
    if not roles:
        st.info("No known roles for this champion in the loaded matches.")
        st.stop()
    if ss.get("compare_role") not in roles:
        ss.compare_role = roles[0]
    comparison_role = c2.selectbox("Comparison role", roles, format_func=ROLE_NAMES.get, key="compare_role")
    reference_queue = meta.get("queue", 420)
    mine = analysis.filter_games(games, champion, comparison_role, queue=reference_queue)
    entry = benchmark.bench_entry(champion, comparison_role)
    if not mine or not entry:
        st.info(
            "No matching reference or player games for this champion, role, and queue. "
            "Try another selection or rebuild the reference; no slow scan starts automatically."
        )
        st.stop()
    st.write(
        f"**You:** {len(mine)} games · **Reference:** {entry['stats']['n']} player-games · "
        f"{QUEUE_NAMES.get(reference_queue, str(reference_queue))}"
    )
    population = meta.get(
        "population", "Players in matches sampled from Master+ accounts; individual ranks were not verified"
    )
    st.caption(f"{population}. Built {meta['built']} · patches {', '.join(meta['patches'])}.")
    regions = meta.get("regions")
    st.caption(
        "Reference regions: "
        + (", ".join(regions) if regions else "not recorded in this legacy bundle")
        + ". Patches and regions may differ from your games."
    )
    if min(len(mine), entry["stats"]["n"]) < 20:
        st.warning("Small sample: patterns can change substantially with more games.")
    start, stop = st.select_slider(
        "Comparison window", options=list(range(0, 45, 5)) + ["End"], value=(0, "End"), key="compare_window"
    )
    if start == "End" or (stop != "End" and stop <= start):
        st.warning("Choose an end time later than the start time.")
        st.stop()
    end_time = float("inf") if stop == "End" else stop
    kind = st.selectbox("Comparison layer", list(KINDS), format_func=lambda k: KINDS[k][0])
    smooth = st.slider("Comparison smoothing", 1.0, 5.0, 2.0, 0.5)
    method = meta.get("position_method", "interpolated")
    st.caption(
        f"Effective window: {start}–{stop} minutes · five-minute blocks · "
        f"positions: {method} on both sides · shared color scale."
    )
    chart = render_chart(
        "compare",
        mine,
        kind,
        start,
        end_time,
        True,
        smooth,
        method == "interpolated",
        champion,
        comparison_role,
    )
    st.image(chart, width="stretch")
    st.caption(
        "Red means more relative activity than the reference; blue means less. Neither means better or worse. "
        "Longer games contribute more position samples. The time window only changes the maps."
    )
    st.markdown("**Full-game statistics**")
    st.dataframe(
        pd.DataFrame(
            {"You": analysis.summarize(mine), "Reference": analysis.summarize_sums(entry["stats"])}
        ).round(2),
        width="stretch",
    )
    st.download_button("Download comparison (PNG)", chart, "comparison.png", "image/png")

st.caption("Unofficial fan project. Not endorsed by Riot Games.")
