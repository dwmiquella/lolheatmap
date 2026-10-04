import json
from functools import lru_cache
from pathlib import Path

import numpy as np

BENCH = Path(__file__).resolve().parent.parent / "data" / "benchmark.npz"


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
