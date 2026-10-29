from pipeline.http import cached_json

BASE = "https://understat.com"
XHR = {"X-Requested-With": "XMLHttpRequest"}
LEAGUES = ["EPL", "La_liga", "Bundesliga", "Serie_A", "Ligue_1"]
FIRST_SEASON = 2014


def league(name: str, season: int) -> dict:
    return cached_json("understat_league", f"{name}_{season}", f"{BASE}/getLeagueData/{name}/{season}", headers=XHR, delay=1.0) or {}


def player(player_id: str) -> dict:
    return cached_json("understat_player", player_id, f"{BASE}/getPlayerData/{player_id}", headers=XHR, delay=1.0) or {}
