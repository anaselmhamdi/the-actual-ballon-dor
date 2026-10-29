"""Add strong Understat-era performers who never received a Ballon d'Or vote."""
import json
from pathlib import Path

import pandas as pd

from pipeline.sources import transfermarkt, understat
from pipeline.understat_link import _similar

OUT = Path(__file__).resolve().parent.parent / "data" / "out"


def candidates() -> pd.DataFrame:
    rows = []
    for season in range(understat.FIRST_SEASON, 2026):
        for lg in understat.LEAGUES:
            data = understat.league(lg, season)
            team_xga = {t["title"]: sum(h["npxGA"] for h in t["history"]) / max(len(t["history"]), 1)
                        for t in data.get("teams", {}).values()}
            for p in data.get("players", []):
                team = p["team_title"].split(",")[-1]
                rows.append({"season": season, "league": lg, "name": p["player_name"], "pos": p["position"],
                             "minutes": int(p["time"]), "npxg_xa": float(p["npxG"]) + float(p["xA"]),
                             "buildup": float(p["xGBuildup"]), "team_xga": team_xga.get(team, 9)})
    df = pd.DataFrame(rows)
    df = df[df["minutes"] >= 1500]
    picks = []
    for season, s in df.groupby("season"):
        picks.append(s.nlargest(15, "npxg_xa"))
        picks.append(s.nlargest(5, "buildup"))
        back = s[s["pos"].str.contains("D|GK") & (s["minutes"] >= 2500)]
        picks.append(back.nsmallest(10, "team_xga"))
    return pd.concat(picks).drop_duplicates("name")


def main():
    pool = json.loads((OUT / "pool_wiki.json").read_text())
    known = {v.lower() for v in pool.values()}
    extra = {}
    for r in candidates().itertuples(index=False):
        if r.name.lower() in known:
            continue
        for pid, slug in transfermarkt.search(r.name)[:5]:
            if _similar(slug.replace("-", " "), r.name) >= 0.75:
                if pid not in pool:
                    extra.setdefault(pid, r.name)
                break
    (OUT / "pool_extra.json").write_text(json.dumps(extra, ensure_ascii=False, indent=1))
    print(len(extra), "extra candidates (verified later by the Understat link)")


if __name__ == "__main__":
    main()
