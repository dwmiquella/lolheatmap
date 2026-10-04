import json
import os
import tempfile

from .config import CACHE


def _cached(kind, mid, fetch, slim):
    path = CACHE / kind / f"{mid}.json"
    if path.exists():
        try:
            d = json.loads(path.read_text())
            if kind != "matches" or "queue" in d:
                return d
        except (OSError, ValueError):
            pass
    raw = fetch()
    if raw is None:
        return None
    d = slim(raw)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False) as f:
        tmp = f.name
        json.dump(d, f)
    try:
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return d


def slim_match(m):
    i = m["info"]
    return {
        "map": i.get("mapId"),
        "queue": i.get("queueId"),
        "dur": i.get("gameDuration", 0),
        "ver": i.get("gameVersion", ""),
        "players": [
            {
                "puuid": p["puuid"],
                "pid": p["participantId"],
                "team": p["teamId"],
                "champ": p["championName"],
                "role": p.get("teamPosition", ""),
                "win": p["win"],
                "k": p["kills"],
                "d": p["deaths"],
                "a": p["assists"],
                "cs": p["totalMinionsKilled"] + p.get("neutralMinionsKilled", 0),
                "vis": p.get("visionScore", 0),
                "dmg": p["totalDamageDealtToChampions"],
                "gold": p["goldEarned"],
                "kp": p.get("challenges", {}).get("killParticipation"),
            }
            for p in i["participants"]
        ],
    }


def slim_timeline(tl):
    pos, ev = {}, []
    for f in tl["info"]["frames"]:
        for pid, pf in f.get("participantFrames", {}).items():
            if "position" in pf:
                pos.setdefault(pid, []).append([f["timestamp"], pf["position"]["x"], pf["position"]["y"]])
        for e in f.get("events", []):
            if e.get("type") == "CHAMPION_KILL" and "position" in e:
                ev.append(
                    [
                        e["timestamp"],
                        e["position"]["x"],
                        e["position"]["y"],
                        e.get("killerId", 0),
                        e.get("victimId", 0),
                        e.get("assistingParticipantIds", []),
                    ]
                )
    return {"pos": pos, "ev": ev}
