"""Core library: Riot API client, slim caching, stats and heatmaps for Summoner's Rift."""
import json
import os
import random
import time
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import requests
from scipy.ndimage import gaussian_filter

MAP = 14870  # Summoner's Rift coordinates run ~0..14870 on both axes
CACHE = Path(os.environ.get("LOLHEAT_CACHE", "cache"))
INTERVAL = float(os.environ.get("RIOT_MIN_INTERVAL", 1.25))  # dev key: 100 req / 2 min
ROLES = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]
KINDS = {  # key -> (label, colormap)
    "pos": ("Time spent", "inferno"),
    "k": ("Kills", "viridis"),
    "d": ("Deaths", "magma"),
    "a": ("Assists", "cividis"),
}
ROUTES = {  # platform (server) -> regional routing host for match/account APIs
    **dict.fromkeys(["na1", "br1", "la1", "la2"], "americas"),
    **dict.fromkeys(["euw1", "eun1", "tr1", "ru"], "europe"),
    **dict.fromkeys(["kr", "jp1"], "asia"),
    **dict.fromkeys(["oc1", "ph2", "sg2", "th2", "tw2", "vn2"], "sea"),
}


TIERS = ("challenger", "grandmaster", "master")


class RiotError(Exception):
    pass


# --------------------------------------------------------------------------- #
# API client
# --------------------------------------------------------------------------- #
class Riot:
    def __init__(self, key, platform):
        self.platform, self.region = platform, ROUTES[platform]
        self.s = requests.Session()
        self.s.headers["X-Riot-Token"] = key.strip()
        self.last = 0.0

    def get(self, path, params=None, platform=False):
        """Throttled GET. Returns JSON, or None on 404."""
        url = f"https://{self.platform if platform else self.region}.api.riotgames.com{path}"
        for attempt in range(6):
            time.sleep(max(0, INTERVAL - (time.time() - self.last)))
            self.last = time.time()
            try:
                r = self.s.get(url, params=params, timeout=30)
            except requests.RequestException:
                time.sleep(2 ** attempt)
                continue
            if r.status_code == 200:
                return r.json()
            if r.status_code == 404:
                return None
            if r.status_code == 429:
                time.sleep(int(r.headers.get("Retry-After", 10)) + 1)
                continue
            if r.status_code in (401, 403):
                raise RiotError("API key rejected. Dev keys expire every 24h; "
                                "regenerate yours at developer.riotgames.com.")
            if r.status_code >= 500:
                time.sleep(2 ** attempt)
                continue
            raise RiotError(f"HTTP {r.status_code} from {url}")
        raise RiotError(f"Gave up on {url} after repeated failures")

    def puuid(self, riot_id):
        if "#" not in riot_id:
            raise RiotError('Riot ID must look like "Name#TAG".')
        name, tag = riot_id.rsplit("#", 1)
        d = self.get(f"/riot/account/v1/accounts/by-riot-id/{quote(name.strip())}/{quote(tag.strip())}")
        if not d:
            raise RiotError(f"{riot_id} not found. Check the Riot ID and the server.")
        return d["puuid"]

    def match_ids(self, puuid, count, queue=420):
        ids, start = [], 0
        while len(ids) < count:
            n = min(100, count - len(ids))
            params = {"start": start, "count": n, **({"queue": queue} if queue else {})}
            page = self.get(f"/lol/match/v5/matches/by-puuid/{puuid}/ids", params) or []
            ids += page
            start += len(page)
            if len(page) < n:
                break
        return ids

    def high_elo(self, n=50, tiers=TIERS):
        """PUUIDs of n players sampled at random (fixed seed) from the apex tiers, default Master+."""
        entries = []
        for tier in tiers:
            d = self.get(f"/lol/league/v4/{tier}leagues/by-queue/RANKED_SOLO_5x5", platform=True)
            entries += (d or {}).get("entries", [])
        random.Random(0).shuffle(entries)
        out = []
        for e in entries[:n]:
            p = e.get("puuid")
            if not p and e.get("summonerId"):  # older response shape
                p = (self.get(f"/lol/summoner/v4/summoners/{e['summonerId']}", platform=True) or {}).get("puuid")
            if p:
                out.append(p)
        return out

    def match(self, mid):
        return _cached("matches", mid, lambda: self.get(f"/lol/match/v5/matches/{mid}"), slim_match)

    def timeline(self, mid):
        return _cached("timelines", mid, lambda: self.get(f"/lol/match/v5/matches/{mid}/timeline"), slim_timeline)


# --------------------------------------------------------------------------- #
# Slim caching: keep only the fields we use (~50x smaller than raw timelines)
# --------------------------------------------------------------------------- #
def _cached(kind, mid, fetch, slim):
    path = CACHE / kind / f"{mid}.json"
    if path.exists():
        return json.loads(path.read_text())
    raw = fetch()
    if raw is None:
        return None
    d = slim(raw)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(d))
    return d


def slim_match(m):
    i = m["info"]
    return {"map": i.get("mapId"), "dur": i.get("gameDuration", 0), "ver": i.get("gameVersion", ""), "players": [
        {"puuid": p["puuid"], "pid": p["participantId"], "team": p["teamId"],
         "champ": p["championName"], "role": p.get("teamPosition", ""), "win": p["win"],
         "k": p["kills"], "d": p["deaths"], "a": p["assists"],
         "cs": p["totalMinionsKilled"] + p.get("neutralMinionsKilled", 0),
         "vis": p.get("visionScore", 0), "dmg": p["totalDamageDealtToChampions"],
         "gold": p["goldEarned"], "kp": p.get("challenges", {}).get("killParticipation")}
        for p in i["participants"]]}


def slim_timeline(tl):
    pos, ev = {}, []
    for f in tl["info"]["frames"]:
        for pid, pf in f.get("participantFrames", {}).items():
            if "position" in pf:
                pos.setdefault(pid, []).append([f["timestamp"], pf["position"]["x"], pf["position"]["y"]])
        for e in f.get("events", []):
            if e.get("type") == "CHAMPION_KILL" and "position" in e:
                ev.append([e["timestamp"], e["position"]["x"], e["position"]["y"],
                           e.get("killerId", 0), e.get("victimId", 0), e.get("assistingParticipantIds", [])])
    return {"pos": pos, "ev": ev}


# --------------------------------------------------------------------------- #
# Collecting games
# --------------------------------------------------------------------------- #
def build_game(mid, m, tl, puuid):
    p = next((x for x in m["players"] if x["puuid"] == puuid), None)
    if not p:
        return None
    pid, ev = p["pid"], []
    for t, x, y, killer, victim, assists in tl["ev"]:
        kind = "k" if killer == pid else "d" if victim == pid else "a" if pid in assists else None
        if kind:
            ev.append([t, x, y, kind])
    return {**p, "id": mid, "dur": m["dur"], "pos": tl["pos"].get(str(pid), []), "ev": ev}


def collect(cl, puuid, ids, champ=None, role=None, tick=None):
    """Fetch one player's games (optionally only a champion/role). Skips remakes and non-SR maps."""
    games = []
    for i, mid in enumerate(ids):
        if tick:
            tick(i / max(len(ids), 1), f"Fetching games ({i}/{len(ids)})")
        m = cl.match(mid)
        if not m or m["map"] != 11 or m["dur"] < 300:
            continue
        p = next((x for x in m["players"] if x["puuid"] == puuid), None)
        if not p or (champ and p["champ"] != champ) or (role and p["role"] != role):
            continue
        tl = cl.timeline(mid)
        g = build_game(mid, m, tl, puuid) if tl else None
        if g:
            games.append(g)
    return games


def benchmark(cl, champ, role, want, tick=None, players=50, per_player=20):
    """Collect `want` games of champ/role from Master+ players."""
    games, seen = [], set()
    pool = cl.high_elo(players)
    for i, pu in enumerate(pool):
        if len(games) >= want:
            break
        if tick:
            tick(max(i / len(pool), len(games) / want),
                 f"Scanning high-elo players ({i + 1}/{len(pool)}) - {len(games)}/{want} games found")
        ids = [x for x in cl.match_ids(pu, per_player) if x not in seen]
        seen.update(ids)
        games += collect(cl, pu, ids, champ, role)
    return games


# --------------------------------------------------------------------------- #
# Stats and points
# --------------------------------------------------------------------------- #
SUM_KEYS = ["win", "k", "d", "a", "cs", "gold", "dmg", "vis", "dur"]


def sums(gs):
    kp = [g["kp"] for g in gs if g.get("kp") is not None]
    return {**{k: sum(g[k] for g in gs) for k in SUM_KEYS}, "n": len(gs), "kp": sum(kp), "kpn": len(kp)}


def summarize_sums(t):
    n = t["n"]
    if not n:
        return {}
    mins = t["dur"] / 60
    return {"Games": n, "Win rate %": 100 * t["win"] / n, "KDA": (t["k"] + t["a"]) / max(t["d"], 1),
            "Kills": t["k"] / n, "Deaths": t["d"] / n, "Assists": t["a"] / n,
            "CS/min": t["cs"] / mins, "Gold/min": t["gold"] / mins, "Damage/min": t["dmg"] / mins,
            "Vision/min": t["vis"] / mins,
            "Kill part. %": 100 * t["kp"] / t["kpn"] if t["kpn"] else float("nan")}


def summarize(gs):
    return summarize_sums(sums(gs)) if gs else {}


def points(games, kind, lo=0, hi=1e9, mirror=False, step=5):
    """Nx2 map coordinates. 'pos' is linearly interpolated between the per-minute samples."""
    out = []
    for g in games:
        if kind == "pos":
            a = np.array(g["pos"], dtype=float)
            if len(a) < 2:
                continue
            ts = np.arange(a[0, 0], a[-1, 0] + 1, step * 1000)
            xy = np.column_stack([np.interp(ts, a[:, 0], a[:, 1]), np.interp(ts, a[:, 0], a[:, 2])])
            xy = xy[(ts >= lo * 60000) & (ts <= hi * 60000)]
        else:
            xy = np.array([[x, y] for t, x, y, k in g["ev"] if k == kind and lo * 60000 <= t <= hi * 60000],
                          dtype=float).reshape(-1, 2)
        out.append(MAP - xy if mirror and g["team"] == 200 else xy)  # rotate red side onto blue
    return np.vstack(out) if out else np.empty((0, 2))


# --------------------------------------------------------------------------- #
# Plotting
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=1)
def map_image():
    p = CACHE / "map11.png"
    if not p.exists():
        try:
            v = requests.get("https://ddragon.leagueoflegends.com/api/versions.json", timeout=15).json()[0]
            r = requests.get(f"https://ddragon.leagueoflegends.com/cdn/{v}/img/map/map11.png", timeout=15)
            r.raise_for_status()
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(r.content)
        except Exception:
            return None
    return plt.imread(p)


def density(pts, bins=100, sigma=2.0):
    """Blurred 2D histogram normalised to sum to 1, so different sample sizes are comparable."""
    H, _, _ = np.histogram2d(pts[:, 0], pts[:, 1], bins=bins, range=[[0, MAP], [0, MAP]])
    H = gaussian_filter(H, sigma)
    return H / H.sum() if H.sum() else H


def draw(ax, D, title, cmap="inferno", diverge=False):
    img = map_image()
    if img is not None:
        ax.imshow(img, extent=[0, MAP, 0, MAP], zorder=0)
    else:
        ax.add_patch(plt.Rectangle((0, 0), MAP, MAP, color="#10151c", zorder=0))
    ax.set_title(title, fontsize=11)
    ax.set_xlim(0, MAP)
    ax.set_ylim(0, MAP)
    ax.set_aspect("equal")
    ax.axis("off")
    if not np.any(D):
        return
    if diverge:
        v = np.abs(D).max()
        M, kw = np.ma.masked_inside(D, -0.1 * v, 0.1 * v), dict(cmap="coolwarm", vmin=-v, vmax=v)
    else:
        M, kw = np.ma.masked_less(D, D.max() * 0.05), dict(cmap=cmap)
    ax.imshow(M.T, origin="lower", extent=[0, MAP, 0, MAP], alpha=0.7,
              interpolation="bilinear", zorder=1, **kw)


def fig_grid(games, lo, hi, mirror, sigma, bins=100):
    fig, axes = plt.subplots(2, 2, figsize=(10, 10))
    for ax, (k, (name, cmap)) in zip(axes.flat, KINDS.items()):
        pts = points(games, k, lo, hi, mirror)
        draw(ax, density(pts, bins, sigma), f"{name} ({len(pts)} pts)", cmap)
    fig.tight_layout()
    return fig


def fig_compare(mine, bench, kind, lo, hi, mirror, sigma, bins=100):
    a, b = (points(g, kind, lo, hi, mirror) for g in (mine, bench))
    Da, Db = density(a, bins, sigma), density(b, bins, sigma)
    name, cmap = KINDS[kind]
    fig, axes = plt.subplots(1, 3, figsize=(16, 5.6))
    draw(axes[0], Da, f"You - {name} ({len(a)} pts)", cmap)
    draw(axes[1], Db, f"High elo - {name} ({len(b)} pts)", cmap)
    draw(axes[2], Da - Db, "Difference (red = you, blue = high elo)", diverge=True)
    fig.tight_layout()
    return fig


# --------------------------------------------------------------------------- #
# Shipped high-elo benchmark (built by build_benchmark.py)
# --------------------------------------------------------------------------- #
BENCH = Path(__file__).parent / "data" / "benchmark.npz"


@lru_cache(maxsize=1)
def _bench():
    if not BENCH.exists():
        return None, {}
    z = np.load(BENCH)
    return z, json.loads(str(z["meta"]))


def bench_meta():
    return _bench()[1]


def bench_entry(champ, role):
    z, meta = _bench()
    key = f"{champ}_{role}"
    if z is None or key not in meta.get("stats", {}):
        return None
    return {"grid": z[key], "stats": meta["stats"][key]}


def fig_compare_pre(mine, entry, kind, lo, hi, sigma):
    """Your points vs the shipped grid. Both mirrored to blue; window snaps to 5-minute blocks."""
    B, sg = bench_meta()["bins"], sigma * 0.6          # coarser grid -> smaller blur in cells
    bs = [b for b in range(9) if (b + 1) * 5 > lo and b * 5 < hi]
    a = points(mine, kind, bs[0] * 5, 1e9 if bs[-1] == 8 else (bs[-1] + 1) * 5, mirror=True)
    raw = entry["grid"][list(KINDS).index(kind)][bs].sum(0).astype(float)
    Gb = gaussian_filter(raw, sg)
    Da, Db = density(a, B, sg), (Gb / Gb.sum() if Gb.sum() else Gb)
    name, cmap = KINDS[kind]
    fig, axes = plt.subplots(1, 3, figsize=(16, 5.6))
    draw(axes[0], Da, f"You - {name} ({len(a)} pts)", cmap)
    draw(axes[1], Db, f"High elo - {name} ({int(raw.sum())} pts)", cmap)
    draw(axes[2], Da - Db, "Difference (red = you, blue = high elo)", diverge=True)
    fig.tight_layout()
    return fig
