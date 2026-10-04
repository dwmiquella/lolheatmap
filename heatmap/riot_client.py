import random
import time
from urllib.parse import quote

import requests

from .analysis import build_game
from .cache import _cached, slim_match, slim_timeline
from .config import INTERVAL, ROUTES, TIERS


class RiotError(Exception):
    pass


# --------------------------------------------------------------------------- #
# API client
# --------------------------------------------------------------------------- #
class Riot:
    def __init__(self, key, platform, status=None):
        self.platform, self.region = platform, ROUTES[platform]
        self.s = requests.Session()
        self.s.headers["X-Riot-Token"] = key.strip()
        self.last = 0.0
        self.status = status or (lambda message: None)

    def get(self, path, params=None, platform=False):
        """Throttled GET. Returns JSON, or None on 404."""
        url = f"https://{self.platform if platform else self.region}.api.riotgames.com{path}"
        for attempt in range(6):
            time.sleep(max(0, INTERVAL - (time.monotonic() - self.last)))
            self.last = time.monotonic()
            try:
                r = self.s.get(url, params=params, timeout=30)
            except requests.RequestException:
                time.sleep(2**attempt)
                continue
            if r.status_code == 200:
                return r.json()
            if r.status_code == 404:
                return None
            if r.status_code == 429:
                delay = float(r.headers.get("Retry-After", 10)) + 1
                self.status(f"Riot rate limit reached. Retrying in {delay:.0f} seconds…")
                time.sleep(delay)
                continue
            if r.status_code in (401, 403):
                raise RiotError(
                    "API key rejected. Dev keys expire every 24h; "
                    "regenerate yours at developer.riotgames.com."
                )
            if r.status_code >= 500:
                time.sleep(2**attempt)
                continue
            raise RiotError(f"HTTP {r.status_code} from {url}")
        raise RiotError(f"Gave up on {url} after repeated failures")

    def puuid(self, riot_id):
        if "#" not in riot_id:
            raise RiotError('Riot ID must look like "Name#TAG".')
        name, tag = riot_id.rsplit("#", 1)
        if not name.strip() or not tag.strip():
            raise RiotError("Enter both the name and tag, for example Name#TAG.")
        d = self.get(
            f"/riot/account/v1/accounts/by-riot-id/{quote(name.strip(), safe='')}/{quote(tag.strip(), safe='')}"
        )
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
                p = (self.get(f"/lol/summoner/v4/summoners/{e['summonerId']}", platform=True) or {}).get(
                    "puuid"
                )
            if p:
                out.append(p)
        return out

    def match(self, mid):
        return _cached("matches", mid, lambda: self.get(f"/lol/match/v5/matches/{mid}"), slim_match)

    def timeline(self, mid):
        return _cached(
            "timelines", mid, lambda: self.get(f"/lol/match/v5/matches/{mid}/timeline"), slim_timeline
        )


def collect(cl, puuid, ids, champ=None, role=None, tick=None, warnings=None):
    """Fetch one player's games (optionally only a champion/role). Skips remakes and non-SR maps."""
    games = []
    for i, mid in enumerate(ids):
        if tick:
            tick(i / max(len(ids), 1), f"Fetching games ({i}/{len(ids)})")
        try:
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
        except RiotError as exc:
            if not games:
                raise
            if warnings is not None:
                warnings.append(f"Loaded {len(games)} games before the request failed: {exc}")
            break
        finally:
            if tick:
                tick(
                    (i + 1) / max(len(ids), 1),
                    f"Processed {i + 1} of {len(ids)} matches; {len(games)} usable games",
                )
    return games


def benchmark(cl, champ, role, want, tick=None, players=50, per_player=20):
    """Collect `want` games of champ/role from Master+ players."""
    games, seen = [], set()
    pool = cl.high_elo(players)
    for i, pu in enumerate(pool):
        if len(games) >= want:
            break
        if tick:
            tick(
                max(i / len(pool), len(games) / want),
                f"Scanning high-elo players ({i + 1}/{len(pool)}) - {len(games)}/{want} games found",
            )
        ids = [x for x in cl.match_ids(pu, per_player) if x not in seen]
        seen.update(ids)
        games += collect(cl, pu, ids, champ, role)
    return games[:want]
