import json

import pytest

from heatmap import cache
from heatmap.demo import demo_games
from heatmap.riot_client import Riot, RiotError, collect


def test_corrupt_cache_recovers_and_replaces_atomically(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "CACHE", tmp_path)
    folder = tmp_path / "timelines"
    folder.mkdir()
    (folder / "test.json").write_text("{")
    expected = {"pos": {}, "ev": []}
    assert cache._cached("timelines", "test", lambda: expected, lambda x: x) == expected
    assert json.loads((folder / "test.json").read_text()) == expected
    assert len(list(folder.iterdir())) == 1


def test_legacy_match_cache_refetches_missing_queue(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "CACHE", tmp_path)
    folder = tmp_path / "matches"
    folder.mkdir()
    (folder / "test.json").write_text('{"map": 11}')
    assert cache._cached("matches", "test", lambda: {"queue": 420}, lambda x: x)["queue"] == 420


def test_partial_results_survive_api_failure():
    g = demo_games()[0]

    class Client:
        def match(self, mid):
            if mid == "bad":
                raise RiotError("Network failed")
            return {"map": 11, "dur": g["dur"], "queue": 420, "players": [g]}

        def timeline(self, mid):
            return {"pos": {"1": g["pos"]}, "ev": []}

    warnings = []
    loaded = collect(Client(), g["puuid"], ["good", "bad"], warnings=warnings)
    assert len(loaded) == 1
    assert "Network failed" in warnings[0]


@pytest.mark.parametrize("riot_id", ["name", "name#", "#tag"])
def test_bad_riot_ids_fail_before_network(riot_id):
    with pytest.raises(RiotError):
        Riot("fake", "na1").puuid(riot_id)
