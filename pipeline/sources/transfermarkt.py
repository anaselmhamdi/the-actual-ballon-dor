import re

from pipeline.http import cached_json, cached_text

TMAPI = "https://tmapi.transfermarkt.technology"
JSON = {"Accept": "application/json"}


def performance(player_id: str) -> list[dict]:
    data = cached_json("tm_performance", player_id, f"https://www.transfermarkt.com/ceapi/performance-game/{player_id}", delay=1.5)
    return (data or {}).get("data", {}).get("performance", [])


def profile(player_id: str) -> dict:
    data = cached_json("tm_player", player_id, f"{TMAPI}/player/{player_id}", headers=JSON, delay=0.5)
    return (data or {}).get("data", {})


def club(club_id: str) -> dict:
    data = cached_json("tm_club", club_id, f"{TMAPI}/club/{club_id}", headers=JSON, delay=0.5)
    return (data or {}).get("data", {})


def country(country_id: int) -> dict:
    data = cached_json("tm_country", str(country_id), f"{TMAPI}/country/{country_id}", headers=JSON, delay=0.5)
    return (data or {}).get("data", {})


def flatten(player_id: str, rows: list[dict]) -> list[dict]:
    """One flat record per match the player was involved in."""
    out = []
    for x in rows:
        g = x["gameInformation"]
        c = x["clubsInformation"]
        s = x["statistics"]
        gen = s.get("generalStatistics") or {}
        gs = s.get("goalStatistics") or {}
        pt = s.get("playingTimeStatistics") or {}
        out.append({
            "tm_id": player_id,
            "game_id": g["gameId"],
            "date": g["date"]["dateTimeUTC"][:10],
            "comp": g["competitionId"],
            "comp_type": g["competitionTypeId"],
            "round": g.get("competitionGroupId") or "",
            "season": g["seasonId"],
            "national": bool(g.get("isNationalGame")),
            "game_state": g.get("gameState"),
            "club_id": c["club"]["clubId"],
            "opp_id": c["opponent"]["clubId"],
            "club_rank": c["club"].get("clubRank"),
            "opp_rank": c["opponent"].get("clubRank"),
            "gf": c["club"].get("goalsTotal"),
            "ga": c["opponent"].get("goalsTotal"),
            "points": c["club"].get("points"),
            "state": gen.get("participationState"),
            "position_id": gen.get("positionId"),
            "minutes": pt.get("playedMinutes") or 0,
            "starting": bool(pt.get("isStarting")),
            "goals": gs.get("goalsScoredTotal") or 0,
            "pen_goals": gs.get("penaltyShooterGoalsScored") or 0,
            "assists": gs.get("assists") or 0,
            "own_goals": gs.get("ownGoalsScored") or 0,
            "team_goals_on": gs.get("teamGoalsOnThePitch"),
            "opp_goals_on": gs.get("opponentGoalsOnThePitch"),
            "pen_saves": gs.get("penaltyGoalkeeperSaves") or 0,
        })
    return out


def search(name: str) -> list[tuple[str, str]]:
    """(player id, url slug) pairs in Transfermarkt's relevance order."""
    html = cached_text("tm_search", name, "https://www.transfermarkt.com/schnellsuche/ergebnis/schnellsuche",
                       params={"query": name}, delay=1.5) or ""
    return list(dict.fromkeys((pid, slug) for slug, pid in re.findall(r'href="/([^/"]+)/profil/spieler/(\d+)"', html)))
