import os
from pathlib import Path

MAP = 14870  # Summoner's Rift coordinates run ~0..14870 on both axes
CACHE = Path(os.environ.get("LOLHEAT_CACHE", "cache"))
INTERVAL = float(os.environ.get("RIOT_MIN_INTERVAL", 1.25))  # dev key: 100 req / 2 min
ROLES = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]
KINDS = {  # key -> (label, colormap)
    "pos": ("Position density", "inferno"),
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


SERVER_NAMES = {
    "na1": "North America",
    "br1": "Brazil",
    "la1": "Latin America North",
    "la2": "Latin America South",
    "euw1": "Europe West",
    "eun1": "Europe Nordic & East",
    "tr1": "Türkiye",
    "ru": "Russia",
    "kr": "Korea",
    "jp1": "Japan",
    "oc1": "Oceania",
    "ph2": "Philippines",
    "sg2": "Singapore",
    "th2": "Thailand",
    "tw2": "Taiwan",
    "vn2": "Vietnam",
}
ROLE_NAMES = {
    "All": "All roles",
    "TOP": "Top",
    "JUNGLE": "Jungle",
    "MIDDLE": "Mid",
    "BOTTOM": "ADC",
    "UTILITY": "Support",
    "": "Unknown",
}
QUEUE_NAMES = {420: "Ranked solo", 440: "Ranked flex", 400: "Normal draft", 0: "Any queue"}
