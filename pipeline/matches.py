"""Load cached Transfermarkt match logs + profiles into tidy tables."""
import json
from pathlib import Path

import pandas as pd

from pipeline import comps
from pipeline.sources import transfermarkt

OUT = Path(__file__).resolve().parent.parent / "data" / "out"

POSITION_GROUP = {"GOALKEEPER": "GK", "DEFENDER": "DEF", "MIDFIELD": "MID", "MIDFIELDER": "MID", "FORWARD": "FWD", "STRIKER": "FWD"}
# Transfermarkt positionId → group (1 GK, 2-5 defenders, 6-10 midfield, 11-14 attack)
POSITION_ID_GROUP = {1: "GK", 2: "DEF", 3: "DEF", 4: "DEF", 5: "DEF", 6: "MID", 7: "MID", 8: "MID", 9: "MID",
                     10: "MID", 11: "FWD", 12: "FWD", 13: "FWD", 14: "FWD"}


def pool_ids() -> dict[str, str]:
    pool = json.loads((OUT / "pool_wiki.json").read_text())
    extra = OUT / "pool_extra.json"
    if extra.exists():
        pool |= json.loads(extra.read_text())
    return pool


def load_players(ids) -> pd.DataFrame:
    rows = []
    for pid in ids:
        p = transfermarkt.profile(pid)
        if not p:
            continue
        attrs = p.get("attributes", {})
        nat = p.get("nationalityDetails", {}).get("nationalities", {})
        rows.append({
            "tm_id": pid,
            "name": p.get("name"),
            "short_name": p.get("shortName"),
            "dob": (p.get("lifeDates") or {}).get("dateOfBirth"),
            "nationality_id": nat.get("nationalityId"),
            "position": POSITION_GROUP.get((attrs.get("positionGroup") or "").upper(), "MID"),
            "position_name": (attrs.get("position") or {}).get("name"),
        })
    return pd.DataFrame(rows)


def load_matches(ids) -> pd.DataFrame:
    rows = []
    for pid in ids:
        rows.extend(transfermarkt.flatten(pid, transfermarkt.performance(pid)))
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    kinds = {(c, t): comps.classify(c, t) for c, t in df[["comp", "comp_type"]].drop_duplicates().itertuples(index=False)}
    df["kind"] = [kinds[(c, t)].kind for c, t in zip(df["comp"], df["comp_type"])]
    df["stake"] = [kinds[(c, t)].stake for c, t in zip(df["comp"], df["comp_type"])]
    df["played"] = (df["state"] == "played") & (df["minutes"] > 0)
    df["pos_group_match"] = df["position_id"].map(POSITION_ID_GROUP)
    return df


def main():
    ids = sorted(pool_ids())
    players = load_players(ids)
    matches = load_matches(ids)
    players.to_parquet(OUT / "players.parquet")
    matches.to_parquet(OUT / "matches.parquet")
    print(len(players), "players", len(matches), "match rows", matches["played"].sum(), "played")


if __name__ == "__main__":
    main()
