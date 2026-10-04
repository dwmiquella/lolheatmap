"""Build data/benchmark.npz: aggregated high-elo heatmaps + stats per (champion, role).

Usage (run once per patch or two, then commit data/benchmark.npz):
    python build_benchmark.py --platform na1 --platform euw1 --platform kr --matches 2000

It finds Master+ players, collects their recent ranked games, and credits
all participants of each sampled match (individual ranks are not verified), so each match yields
up to 10 player-games. Cached downloads are reused when you rerun; aggregation restarts;
Ctrl+C also saves whatever has been processed so far.
"""

import argparse
import json
import os
import random
from collections import Counter
from datetime import date
from pathlib import Path

import numpy as np
from dotenv import load_dotenv

import lolheat as lh

BINS, BUCKETS = 60, 9  # 60x60 grid; 5-minute time buckets (0-5, ..., 35-40, 40+)
KINDS = list(lh.KINDS)


def add_game(g, grids, stats):
    key = f"{g['champ']}_{g['role']}"
    G = grids.setdefault(key, np.zeros((len(KINDS), BUCKETS, BINS, BINS), dtype=np.uint32))
    for ki, kind in enumerate(KINDS):
        for b in range(BUCKETS):
            hi = 1e9 if b == BUCKETS - 1 else (b + 1) * 5
            pts = lh.points([g], kind, b * 5, hi, mirror=True)  # everything mirrored onto blue side
            if len(pts):
                H, _, _ = np.histogram2d(pts[:, 0], pts[:, 1], bins=BINS, range=[[0, lh.MAP]] * 2)
                G[ki, b] += H.astype(np.uint32)
    s = stats.setdefault(key, {})
    for k, v in lh.sums([g]).items():
        s[k] = s.get(k, 0) + v


def main():
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--platform", action="append", help="e.g. na1 (repeatable). Default: na1")
    ap.add_argument("--players", type=int, default=200, help="top players to sample match lists from")
    ap.add_argument("--per-player", type=int, default=30, help="recent games listed per player")
    ap.add_argument("--matches", type=int, default=2000, help="max matches to process per platform")
    ap.add_argument("--min-games", type=int, default=20, help="drop champion/role combos below this")
    ap.add_argument(
        "--top-only",
        action="store_true",
        help="only count the sampled top players, not everyone in their lobbies",
    )
    ap.add_argument(
        "--tiers",
        default="challenger,grandmaster,master",
        help="comma-separated apex tiers to sample (default Master+)",
    )
    ap.add_argument("--queue", type=int, choices=[420, 440, 400], default=420)
    ap.add_argument("--out", default="data/benchmark.npz")
    args = ap.parse_args()
    if any(v <= 0 for v in (args.players, args.per_player, args.matches, args.min_games)):
        ap.error("Counts must be positive.")
    platforms = list(dict.fromkeys(args.platform or ["na1"]))
    if any(p not in lh.ROUTES for p in platforms):
        ap.error("Unknown platform.")
    if any(t not in lh.TIERS for t in args.tiers.split(",")):
        ap.error("Unknown tier.")
    key = os.environ.get("RIOT_API_KEY")
    if not key:
        raise SystemExit("Set RIOT_API_KEY first.")

    grids, stats, patches, n_matches = {}, {}, Counter(), 0
    unique_players, cohort_players, processed = set(), {}, set()
    region_matches = Counter()
    interrupted = False
    try:
        for plat in platforms:
            cl = lh.Riot(key, plat)
            pool = cl.high_elo(args.players, tuple(args.tiers.split(",")))
            poolset = set(pool)
            print(f"[{plat}] {len(pool)} top players; listing matches...")
            ids = []
            for pu in pool:
                ids += cl.match_ids(pu, args.per_player, args.queue)
            ids = sorted(set(ids))
            random.Random(0).shuffle(ids)  # spread coverage across players
            ids = ids[: args.matches]
            print(f"[{plat}] {len(ids)} unique matches (~{2 * len(ids) * lh.INTERVAL / 60:.0f} min uncached)")
            for n, mid in enumerate(ids, 1):
                if mid in processed:
                    continue
                m = cl.match(mid)
                if not m or m["map"] != 11 or m["dur"] < 300:
                    continue
                tl = cl.timeline(mid)
                if not tl:
                    continue
                processed.add(mid)
                n_matches += 1
                region_matches[plat] += 1
                patches[".".join(m.get("ver", "").split(".")[:2])] += 1
                for p in m["players"]:
                    if p["role"] and (not args.top_only or p["puuid"] in poolset):
                        g = lh.build_game(mid, m, tl, p["puuid"])
                        if g:
                            add_game(g, grids, stats)
                            unique_players.add(p["puuid"])
                            cohort_players.setdefault(f"{p['champ']}_{p['role']}", set()).add(p["puuid"])
                if n % 50 == 0:
                    print(f"[{plat}] {n}/{len(ids)} matches, {len(grids)} champion/role combos")
    except KeyboardInterrupt:
        interrupted = True
        print("\nInterrupted; saving what we have...")

    keep = {k for k, s in stats.items() if s["n"] >= args.min_games}
    if not keep:
        raise SystemExit("No eligible cohorts collected; existing benchmark left unchanged.")
    meta = {
        "schema_version": 2,
        "built": str(date.today()),
        "matches": n_matches,
        "bins": BINS,
        "tiers": args.tiers,
        "patches": [p for p, _ in patches.most_common() if p],
        "patch_counts": dict(patches),
        "regions": platforms,
        "region_matches": dict(region_matches),
        "queue": args.queue,
        "position_method": "sampled",
        "interrupted": interrupted,
        "unique_players": len(unique_players),
        "cohort_unique_players": {k: len(cohort_players[k]) for k in keep},
        "sampling": {
            "players_per_region": args.players,
            "matches_per_player": args.per_player,
            "max_matches_per_region": args.matches,
            "seed": 0,
            "top_only": args.top_only,
            "minimum_games": args.min_games,
        },
        "population": (
            "Sampled apex-tier accounts (rank at collection time)"
            if args.top_only
            else "Players in matches sampled from apex-tier accounts; individual ranks not verified"
        ),
        "stats": {k: stats[k] for k in keep},
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    temporary = str(args.out) + ".tmp"
    with open(temporary, "wb") as output:
        np.savez_compressed(output, meta=json.dumps(meta), **{k: grids[k] for k in sorted(keep)})
    os.replace(temporary, args.out)
    size = Path(args.out).stat().st_size / 1e6
    print(f"Saved {args.out}: {len(keep)} combos from {n_matches} matches ({size:.1f} MB)")


if __name__ == "__main__":
    main()
