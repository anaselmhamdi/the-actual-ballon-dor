"""Per player-year features inside each award's real voting window."""
import numpy as np
import pandas as pd

from pipeline import comps

FIRST_YEAR, LAST_YEAR = 1956, 2026
NON_EURO_LEAGUE_PREFIX = ("BRA", "AR", "MEX", "URU", "COL", "CHI", "PER", "PAR", "ECU", "MLS", "JAP", "CSL", "SA1", "QSL", "UAE")


def window(year: int) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Calendar years until 2021; France Football switched to Aug–Jul seasons from 2022."""
    if year <= 2021:
        return pd.Timestamp(f"{year}-01-01"), pd.Timestamp(f"{year}-12-31")
    return pd.Timestamp(f"{year - 1}-08-01"), pd.Timestamp(f"{year}-07-31")


def tier(year: int) -> str:
    return "A" if year >= 2015 else "B" if year >= 1993 else "C"


def eligibility_rule(year: int) -> str:
    return "europeans" if year <= 1994 else "european_clubs" if year <= 2006 else "open"


def prepare(m: pd.DataFrame) -> pd.DataFrame:
    m = m[m["kind"] != "youth"].copy()
    m["npg"] = (m["goals"] - m["pen_goals"]).clip(lower=0)
    m["ga_on"] = m["opp_goals_on"].where(m["opp_goals_on"].notna(), m["ga"].where(m["minutes"] >= 85))
    # Shootout scores are folded into the totals, so the open-play score is unknown.
    m.loc[m["game_state"] == "penalty_shootout", "ga_on"] = np.nan
    opp = np.where(m["kind"] == "league",
                   np.select([m["opp_rank"] <= 4, m["opp_rank"] <= 10], [1.15, 1.0], 0.9), 1.0)
    m["w"] = m["stake"] * np.where(m["opp_rank"].isna() & (m["kind"] == "league"), 1.0, opp)
    goals_assists = m["npg"] + m["assists"]
    if "npxg" in m:
        has_xg = m["npxg"].notna()
        m["attack"] = np.where(has_xg, 0.5 * goals_assists + 0.5 * (m["npxg"].fillna(0) + m["xa"].fillna(0)), goals_assists)
    else:
        m["attack"] = goals_assists
    m["p90"] = m["minutes"] / 90
    m["cs"] = (m["minutes"] >= 60) & (m["ga_on"] == 0)
    return m


def club_is_european(m: pd.DataFrame) -> dict[str, bool]:
    clubs = m[~m["national"]]
    euro = set(clubs.loc[clubs["comp"].isin(comps.UEFA_ONLY), "club_id"])
    non = set(clubs.loc[clubs["comp"].isin(comps.NON_UEFA), "club_id"])
    league = clubs[clubs["kind"] == "league"].groupby("club_id")["comp"].agg(lambda s: s.mode().iat[0])
    out = {}
    for club, comp in league.items():
        out[club] = club in euro or (club not in non and not comp.startswith(NON_EURO_LEAGUE_PREFIX))
    return out


def player_is_european(m: pd.DataFrame) -> dict[str, bool | None]:
    nat = m[m["national"]]
    out = {}
    for pid, g in nat.groupby("tm_id"):
        e, n = g["comp"].isin(comps.UEFA_ONLY).sum(), g["comp"].isin(comps.NON_UEFA).sum()
        out[pid] = None if e == n == 0 else bool(e > n)
    return out


def trophies(m: pd.DataFrame) -> pd.DataFrame:
    """Every trophy a pool player shared in, with the date it was decided and his share of the campaign."""
    rows = []
    cupish = m[(m["comp"].isin(comps.TROPHY_VALUE)) | (m["kind"] == "cup")]
    finals = cupish[cupish["round"] == "FF"]
    for (comp, season, club), f in finals.groupby(["comp", "season", "club_id"]):
        f = f.sort_values("date")
        last = f.iloc[-1]
        won = last["points"] == 3 or (last["points"] == 1 and last["game_state"] != "penalty_shootout"
                                      and f.drop_duplicates("game_id")["gf"].sum() > f.drop_duplicates("game_id")["ga"].sum())
        if not won:
            continue
        value = comps.TROPHY_VALUE.get(comp, comps.DOMESTIC_CUP_VALUE)
        campaign = m[(m["comp"] == comp) & (m["season"] == season) & (m["club_id"] == club)]
        for pid, g in campaign.groupby("tm_id"):
            share = g.loc[g["played"], "minutes"].sum() / max(90 * len(g), 1)
            if share > 0:
                rows.append({"tm_id": pid, "date": last["date"], "comp": comp, "value": value, "share": min(1.0, share + 0.15)})
    lg = m[(m["kind"] == "league") & (m["comp_type"] == 1)]
    season_end = lg.groupby(["comp", "season"])["date"].max()
    for (pid, comp, season), g in lg.groupby(["tm_id", "comp", "season"]):
        last = g.loc[g["date"].idxmax()]
        if last["club_rank"] != 1 or last["date"] < season_end[(comp, season)] - pd.Timedelta(days=30):
            continue
        share = g.loc[g["played"], "minutes"].sum() / max(90 * len(g), 1)
        if share > 0:
            value = comps.LEAGUE_TITLE_VALUE * comps.league_strength(comp, 1)
            rows.append({"tm_id": pid, "date": last["date"], "comp": comp, "value": value, "share": min(1.0, share + 0.1)})
    return pd.DataFrame(rows)


def big_games(g: pd.DataFrame, pos: str) -> tuple[float, int]:
    big = g[g["comp"].isin(comps.BIG_GAME_COMP) & g["played"]]
    total, n = 0.0, 0
    for r in big.itertuples(index=False):
        rk = comps.round_key(r.round)
        rw = comps.ROUND_WEIGHT[rk] if rk else (0.6 if r.kind == "national_major" else 0.0)
        if not rw:
            continue
        result = {3: 1.0, 1: 0.3, 0: -0.5}.get(r.points, 0.0)
        val = r.p90 * (0.3 + result) + r.attack
        if pos in ("DEF", "GK"):
            val += 0.7 * r.cs - 0.15 * (r.ga_on if r.ga_on == r.ga_on else 0)
        elif pos == "MID":
            val += 0.3 * r.cs
        total += val * rw * comps.BIG_GAME_COMP[r.comp]
        n += 1
    return total, n


def player_years(matches: pd.DataFrame, players: pd.DataFrame) -> pd.DataFrame:
    m = prepare(matches)
    club_euro = club_is_european(m)
    nat_euro = player_is_european(m)
    troph = trophies(m)
    profile_pos = players.set_index("tm_id")["position"].to_dict()
    rows = []
    for year in range(FIRST_YEAR, LAST_YEAR + 1):
        start, end = window(year)
        wm = m[(m["date"] >= start) & (m["date"] <= end)]
        wt = troph[(troph["date"] >= start) & (troph["date"] <= end)] if len(troph) else troph
        for pid, g in wm.groupby("tm_id"):
            p = g[g["played"]]
            if p.empty:
                continue
            posd = p["pos_group_match"].dropna()
            pos = posd.mode().iat[0] if len(posd) >= 5 else profile_pos.get(pid, "MID")
            league_rows = p[p["kind"] == "league"]
            competitive = p[p["kind"] != "friendly"]
            league_missing = league_rows.empty and len(competitive) >= 3
            adj_min = float((p["p90"] * p["stake"]).sum())
            adj_attack = float((p["attack"] * p["w"]).sum())
            if league_missing:
                rate = adj_attack / max(adj_min, 1)
                adj_attack += rate * 30 * 0.85
                adj_min += 30 * 0.85
            full = p[p["minutes"] >= 60]
            ga_known = p[p["ga_on"].notna()]
            xg_rows = p[p["team_xga"].notna()] if "team_xga" in p else p.iloc[0:0]
            big, n_big = big_games(g, pos)
            club_minutes = p[~p["national"]].groupby("club_id")["minutes"].sum()
            main_club = club_minutes.idxmax() if len(club_minutes) else None
            nat_rows = p[p["national"]]
            tp = wt[wt["tm_id"] == pid] if len(wt) else wt
            rows.append({
                "year": year, "tm_id": pid, "pos": pos,
                "matches": len(p), "minutes": int(p["minutes"].sum()),
                "goals": int(p["goals"].sum()), "pen_goals": int(p["pen_goals"].sum()), "assists": int(p["assists"].sum()),
                "npxg": float(p["npxg"].sum()) if "npxg" in p and p["npxg"].notna().any() else None,
                "xa": float(p["xa"].sum()) if "xa" in p and p["xa"].notna().any() else None,
                "adj_minutes": adj_min, "adj_attack": adj_attack,
                "cs_rate": float((full["cs"] * full["stake"]).sum() / full["stake"].sum()) if len(full) else None,
                "conceded_p90": float(ga_known["ga_on"].sum() / max((ga_known["p90"] * ga_known["stake"]).sum(), 0.5)) if len(ga_known) else None,
                "ppg": float((p["points"].fillna(1) * p["stake"] * p["p90"]).sum() / max((p["stake"] * p["p90"]).sum(), 0.5)),
                "xga_p90": float((xg_rows["team_xga"] * xg_rows["p90"]).sum() / xg_rows["p90"].sum()) if len(xg_rows) >= 5 else None,
                "gk_saved_p90": float(((xg_rows["team_xga"] - xg_rows["ga_on"].fillna(0)) * xg_rows["p90"]).sum() / xg_rows["p90"].sum()) if len(xg_rows) >= 5 else None,
                "big_score": big, "big_matches": n_big,
                "trophy_score": float((tp["value"] * tp["share"]).sum()) if len(tp) else 0.0,
                "trophies": sorted(set(tp["comp"])) if len(tp) else [],
                "league_missing": league_missing,
                "main_club": main_club, "national_team": nat_rows["club_id"].mode().iat[0] if len(nat_rows) else None,
                "nat_euro": nat_euro.get(pid), "club_euro": club_euro.get(main_club, True) if main_club else None,
                "intl_goals": int(nat_rows["goals"].sum()),
            })
    return pd.DataFrame(rows)
