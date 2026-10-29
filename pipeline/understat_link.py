"""Attach Understat match-level xG/xA to Transfermarkt league matches (2014/15 onward)."""
import difflib
import unicodedata
from pathlib import Path

import pandas as pd

from pipeline.sources import understat

OUT = Path(__file__).resolve().parent.parent / "data" / "out"
TM_LEAGUE = {"EPL": "GB1", "La_liga": "ES1", "Bundesliga": "L1", "Serie_A": "IT1", "Ligue_1": "FR1"}


def norm(name: str) -> str:
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    return " ".join(s.replace("-", " ").replace(".", " ").split())


def _similar(a: str, b: str) -> float:
    a, b = norm(a), norm(b)
    if not a or not b:
        return 0.0
    ta, tb = set(a.split()), set(b.split())
    if ta <= tb or tb <= ta:
        return 1.0
    return max(difflib.SequenceMatcher(None, a, b).ratio(), len(ta & tb) / max(len(ta), len(tb)))


def league_players() -> pd.DataFrame:
    rows = []
    for season in range(understat.FIRST_SEASON, 2026):
        for lg in understat.LEAGUES:
            for p in understat.league(lg, season).get("players", []):
                rows.append({"us_id": p["id"], "us_name": p["player_name"], "comp": TM_LEAGUE[lg], "season": season,
                             "us_goals": int(p["goals"]), "us_minutes": int(p["time"]), "us_team": p["team_title"]})
    return pd.DataFrame(rows)


def link(matches: pd.DataFrame, players: pd.DataFrame) -> dict[str, str]:
    """Return tm_id → understat id, verified by matching season goal and minute totals."""
    lg = matches[matches["comp"].isin(TM_LEAGUE.values()) & (matches["season"] >= understat.FIRST_SEASON) & matches["played"]]
    totals = lg.groupby(["tm_id", "comp", "season"]).agg(goals=("goals", "sum"), minutes=("minutes", "sum")).reset_index()
    us = league_players()
    names = players.set_index("tm_id")[["name", "short_name"]].to_dict("index")
    votes: dict[str, dict[str, float]] = {}
    for t in totals.itertuples(index=False):
        cand = us[(us["comp"] == t.comp) & (us["season"] == t.season)]
        cand = cand[(cand["us_goals"] - t.goals).abs() <= 1]
        cand = cand[(cand["us_minutes"] - t.minutes).abs() <= max(120, 0.12 * t.minutes)]
        nm = names.get(t.tm_id, {})
        for c in cand.itertuples(index=False):
            sim = max(_similar(nm.get("name"), c.us_name), _similar(nm.get("short_name"), c.us_name))
            if sim >= 0.6:
                votes.setdefault(t.tm_id, {}).setdefault(c.us_id, 0.0)
                votes[t.tm_id][c.us_id] += sim
    return {tm: max(v, key=v.get) for tm, v in votes.items()}


def match_xg(links: dict[str, str]) -> pd.DataFrame:
    """Per-player Understat matches with own npxG/xA and team-side xG against."""
    games = {}
    for season in range(understat.FIRST_SEASON, 2026):
        for lg in understat.LEAGUES:
            for d in understat.league(lg, season).get("dates", []):
                if d.get("isResult"):
                    games[d["id"]] = (d["h"]["title"], d["a"]["title"], float(d["xG"]["h"]), float(d["xG"]["a"]))
    rows = []
    for tm_id, us_id in links.items():
        data = understat.player(us_id)
        team_by_season = {}
        for g in data.get("groups", {}).get("season", []):
            team_by_season.setdefault(g["season"], set()).update(g["team"].split(","))
        for m in data.get("matches", []):
            game = games.get(m["id"])
            if not game:
                continue
            h, a, xg_h, xg_a = game
            teams = team_by_season.get(m["season"], set())
            home = h in teams if (h in teams) != (a in teams) else None
            rows.append({
                "tm_id": tm_id, "date": pd.Timestamp(m["date"]),
                "npxg": float(m["npxG"]), "xa": float(m["xA"]), "us_minutes": int(m["time"]),
                "team_xga": None if home is None else (xg_a if home else xg_h),
            })
    return pd.DataFrame(rows, columns=["tm_id", "date", "npxg", "xa", "us_minutes", "team_xga"])


def attach(matches: pd.DataFrame, xg: pd.DataFrame) -> pd.DataFrame:
    """Join on player + date, allowing a one-day shift (Understat dates are local, Transfermarkt's UTC)."""
    lg = matches["comp"].isin(TM_LEAGUE.values())
    left = matches[lg].reset_index()
    out = []
    for shift in (0, 1, -1):
        x = xg.copy()
        x["date"] = x["date"] + pd.Timedelta(days=shift)
        j = left.merge(x, on=["tm_id", "date"], how="inner")
        out.append(j[["index", "npxg", "xa", "team_xga"]])
        left = left[~left["index"].isin(j["index"])]
    joined = pd.concat(out).drop_duplicates("index").set_index("index")
    matches = matches.copy()
    for col in ("npxg", "xa", "team_xga"):
        matches[col] = joined[col].reindex(matches.index)
    return matches
