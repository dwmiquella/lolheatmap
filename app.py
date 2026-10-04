"""Streamlit UI. Run with:  streamlit run app.py"""
import os
from collections import Counter

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

import lolheat as lh

load_dotenv()
st.set_page_config(page_title="LoL Heatmaps", layout="wide")
ss = st.session_state
ss.setdefault("bench", {})


def show(fig):
    st.pyplot(fig)
    plt.close(fig)


# ------------------------------- sidebar: player ------------------------------- #
with st.sidebar:
    st.header("Player")
    key = st.text_input("Riot API key", os.environ.get("RIOT_API_KEY", ""), type="password",
                        help="Get one at developer.riotgames.com, or set RIOT_API_KEY in a .env file.")
    rid = st.text_input("Riot ID", placeholder="Name#TAG")
    plat = st.selectbox("Server", list(lh.ROUTES))
    queue = st.selectbox("Queue", [420, 440, 400, 0],
                         format_func={420: "Ranked solo", 440: "Ranked flex", 400: "Normal draft", 0: "Any"}.get)
    count = st.slider("Recent games", 10, 100, 30)
    go = st.button("Analyze", type="primary", use_container_width=True)

if go:
    if not key or not rid:
        st.error("Enter your API key and Riot ID in the sidebar.")
        st.stop()
    try:
        cl = lh.Riot(key, plat)
        bar = st.progress(0.0, "Looking up player...")
        puuid = cl.puuid(rid)
        ids = cl.match_ids(puuid, count, queue)
        ss.games = lh.collect(cl, puuid, ids, tick=lambda f, t: bar.progress(min(f, 1.0), t))
        ss.name, ss.bench = rid, {}
        bar.empty()
    except lh.RiotError as e:
        st.error(str(e))
        st.stop()

games = ss.get("games")
st.title(ss.get("name", "League heatmaps"))
if not games:
    st.info("Enter your API key and Riot ID, then press Analyze. "
            "The first run takes a few minutes on a dev key; results are cached after that."
            if games is None else "No Summoner's Rift games found for that queue.")
    st.stop()

# ------------------------------- sidebar: filters ------------------------------- #
with st.sidebar:
    st.header("Filters")
    champ = st.selectbox("Champion", ["All"] + sorted({g["champ"] for g in games}))
    role = st.selectbox("Role", ["All"] + lh.ROLES)
    result = st.radio("Result", ["All", "Win", "Loss"], horizontal=True)
    side = st.radio("Side", ["All", "Blue", "Red"], horizontal=True)
    lo, hi = st.slider("Game window (min, 40 = end)", 0, 40, (0, 40))
    hi = 1e9 if hi == 40 else hi
    mirror = st.checkbox("Mirror red side onto blue", True)
    sigma = st.slider("Blur", 1.0, 5.0, 2.0, 0.5)

f = [g for g in games
     if (champ == "All" or g["champ"] == champ) and (role == "All" or g["role"] == role)
     and (result == "All" or g["win"] == (result == "Win"))
     and (side == "All" or g["team"] == (100 if side == "Blue" else 200))]
if not f:
    st.warning("No games match these filters.")
    st.stop()

S = lh.summarize(f)
for c, (k, fmt) in zip(st.columns(6), [("Games", "{:.0f}"), ("Win rate %", "{:.0f}%"), ("KDA", "{:.2f}"),
                                       ("CS/min", "{:.1f}"), ("Vision/min", "{:.2f}"),
                                       ("Kill part. %", "{:.0f}%")]):
    c.metric(k.rstrip(" %"), fmt.format(S[k]))

t1, t2, t3 = st.tabs(["Heatmaps", "Vs high elo", "Champions"])

with t1:
    show(lh.fig_grid(f, lo, hi, mirror, sigma))
    st.caption("Riot records one position per minute; time spent is interpolated between samples, so treat it as an estimate.")

with t2:
    if champ == "All":
        st.info("Pick a champion in the sidebar to compare against Master+ players.")
    else:
        brole = role if role != "All" else Counter(g["role"] for g in f).most_common(1)[0][0]
        entry = lh.bench_entry(champ, brole)
        if entry:
            meta = lh.bench_meta()
            st.write(f"Benchmark: **{entry['stats']['n']} high-elo {champ} {brole}** games "
                     f"(patch {', '.join(meta['patches'])}, built {meta['built']}).")
            kind = st.radio("Heatmap", list(lh.KINDS), format_func=lambda k: lh.KINDS[k][0], horizontal=True)
            show(lh.fig_compare_pre(f, entry, kind, lo, hi, sigma))
            st.dataframe(pd.DataFrame({"You": S, "High elo": lh.summarize_sums(entry["stats"])}).round(2),
                         use_container_width=True)
            st.caption("Both sides are mirrored onto blue and the window snaps to 5-minute blocks. "
                       "Heatmaps are normalised, so they compare shape, not volume.")
        else:
            st.warning("No shipped benchmark for this champion/role, so this uses a slow live scan.")
            st.write(f"Benchmark: top-ladder **{champ} {brole or '(any role)'}** games on {plat}.")
            want = st.slider("High-elo games to collect", 5, 40, 15)
            bk = (plat, champ, brole)
            if st.button("Fetch high-elo games"):
                bar = st.progress(0.0, "Finding top players...")
                try:
                    ss.bench[bk] = lh.benchmark(lh.Riot(key, plat), champ, brole, want,
                                                tick=lambda p, t: bar.progress(min(p, 1.0), t))
                except lh.RiotError as e:
                    st.error(str(e))
                bar.empty()
            if bk in ss.bench:
                b = ss.bench[bk]
                if not b:
                    st.warning("No matching high-elo games found. Try a more popular champion or role.")
                else:
                    kind = st.radio("Heatmap", list(lh.KINDS), format_func=lambda k: lh.KINDS[k][0], horizontal=True)
                    show(lh.fig_compare(f, b, kind, lo, hi, mirror, sigma))
                    st.dataframe(pd.DataFrame({"You": S, "High elo": lh.summarize(b)}).round(2),
                                 use_container_width=True)
                    st.caption(f"{len(b)} high-elo games from {len({g['puuid'] for g in b})} players. "
                               "Heatmaps are normalised, so they compare shape, not volume.")


with t3:
    rows = [{"Champion": c, **lh.summarize([g for g in games if g["champ"] == c])}
            for c in sorted({g["champ"] for g in games})]
    st.dataframe(pd.DataFrame(rows).sort_values("Games", ascending=False).round(2),
                 hide_index=True, use_container_width=True)
