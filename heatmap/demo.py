"""Deterministic, fictional examples. No player identifiers or API calls."""

import random


def demo_games():
    rng = random.Random(42)
    games = []
    for i in range(12):
        champ, role = [("Ahri", "MIDDLE"), ("Jinx", "BOTTOM"), ("Lux", "UTILITY")][i % 3]
        team = 100 if i % 2 == 0 else 200
        dur = (25 + i) * 60
        pos = []
        for minute in range(dur // 60 + 1):
            x = max(500, min(14000, 2000 + minute * 270 + rng.randint(-2200, 2200)))
            y = max(500, min(14000, x + rng.randint(-1800, 1800)))
            if role == "BOTTOM":
                y = max(900, y - 4500)
            pos.append([minute * 60000, x if team == 100 else 14870 - x, y if team == 100 else 14870 - y])
        events = [[t, x, y, rng.choice(["k", "d", "a"])] for t, x, y in pos[3::2]]
        counts = {k: sum(e[3] == k for e in events) for k in ("k", "d", "a")}
        games.append(
            {
                "id": f"demo-{i}",
                "puuid": "fictional-demo",
                "pid": 1,
                "champ": champ,
                "role": role,
                "team": team,
                "win": i % 3 != 0,
                "queue": 420,
                "patch": "fictional",
                "dur": dur,
                "pos": pos,
                "ev": events,
                **counts,
                "cs": 130 + i * 6,
                "gold": 10000 + i * 200,
                "dmg": 17000 + i * 700,
                "vis": 18 + i * 2,
                "kp": 0.48 + i / 100,
            }
        )
    return games
