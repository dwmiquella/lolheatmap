import numpy as np

from .config import MAP


def build_game(mid, m, tl, puuid):
    p = next((x for x in m["players"] if x["puuid"] == puuid), None)
    if not p:
        return None
    pid, ev = p["pid"], []
    for t, x, y, killer, victim, assists in tl["ev"]:
        kind = "k" if killer == pid else "d" if victim == pid else "a" if pid in assists else None
        if kind:
            ev.append([t, x, y, kind])
    return {
        **p,
        "id": mid,
        "dur": m["dur"],
        "queue": m.get("queue"),
        "patch": m.get("ver", ""),
        "pos": tl["pos"].get(str(pid), []),
        "ev": ev,
    }


SUM_KEYS = ["win", "k", "d", "a", "cs", "gold", "dmg", "vis", "dur"]


def sums(gs):
    kp = [g["kp"] for g in gs if g.get("kp") is not None]
    return {**{k: sum(g[k] for g in gs) for k in SUM_KEYS}, "n": len(gs), "kp": sum(kp), "kpn": len(kp)}


def summarize_sums(t):
    n = t["n"]
    if not n:
        return {}
    mins = t["dur"] / 60
    return {
        "Games": n,
        "Win rate %": 100 * t["win"] / n,
        "KDA": (t["k"] + t["a"]) / max(t["d"], 1),
        "Kills": t["k"] / n,
        "Deaths": t["d"] / n,
        "Assists": t["a"] / n,
        "CS/min": t["cs"] / mins,
        "Gold/min": t["gold"] / mins,
        "Damage/min": t["dmg"] / mins,
        "Vision/min": t["vis"] / mins,
        "Kill part. %": 100 * t["kp"] / t["kpn"] if t["kpn"] else float("nan"),
    }


def summarize(gs):
    return summarize_sums(sums(gs)) if gs else {}


def points(games, kind, lo=0, hi=1e9, mirror=False, step=5, interpolate=False):
    """Coordinates in [lo, hi); optionally interpolate position samples."""
    if hi <= lo:
        return np.empty((0, 2))
    out = []
    for g in games:
        if kind == "pos":
            a = np.array(g["pos"], dtype=float)
            if len(a) == 0:
                continue
            ts = np.arange(a[0, 0], a[-1, 0] + 1, step * 1000) if interpolate else a[:, 0]
            xy = np.column_stack([np.interp(ts, a[:, 0], a[:, 1]), np.interp(ts, a[:, 0], a[:, 2])])
            xy = xy[(ts >= lo * 60000) & (ts < hi * 60000)]
        else:
            xy = np.array(
                [[x, y] for t, x, y, k in g["ev"] if k == kind and lo * 60000 <= t < hi * 60000], dtype=float
            ).reshape(-1, 2)
        out.append(MAP - xy if mirror and g["team"] == 200 else xy)  # rotate red side onto blue
    return np.vstack(out) if out else np.empty((0, 2))


def filter_games(games, champ="All", role="All", result="All", side="All", queue=None):
    return [
        g
        for g in games
        if (champ == "All" or g["champ"] == champ)
        and (role == "All" or g["role"] == role)
        and (result == "All" or g["win"] == (result == "Win"))
        and (side == "All" or g["team"] == (100 if side == "Blue" else 200))
        and (queue is None or g.get("queue") == queue)
    ]


def time_buckets(lo, hi):
    """Return overlapping half-open 5-minute buckets; bucket 8 covers 40+ minutes."""
    if lo < 0 or hi <= lo:
        raise ValueError("Choose an end time later than the start time.")
    buckets = [b for b in range(9) if (float("inf") if b == 8 else (b + 1) * 5) > lo and b * 5 < hi]
    return buckets, buckets[0] * 5, float("inf") if buckets[-1] == 8 else (buckets[-1] + 1) * 5
