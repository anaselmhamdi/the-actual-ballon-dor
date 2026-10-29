"""Run the full model and write the compact JSON the site reads."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

from pipeline import features, matches, model, understat_link
from pipeline.sources import transfermarkt

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "out"
WEB_DATA = ROOT / "web" / "public" / "data.json"
PER_YEAR = 40

COMP_NAMES = {
    "CL": "Champions League", "EPL": "European Cup", "FIWC": "World Cup", "EURO": "Euro", "COPA": "Copa América",
    "CA16": "Copa América", "CLI": "Libertadores", "UEFA": "UEFA Cup", "EL": "Europa League", "EPP": "Cup Winners' Cup",
    "ITC": "Fairs Cup", "KLUB": "Club World Cup", "WEPO": "Intercontinental Cup", "AFCN": "AFCON", "GOCU": "Gold Cup",
    "UNFI": "Nations League", "CONC": "Confederations Cup", "AFT": "Finalissima",
    "ES1": "La Liga", "IT1": "Serie A", "GB1": "Premier League", "EFD1": "First Division", "L1": "Bundesliga",
    "FR1": "Ligue 1", "NL1": "Eredivisie", "PO1": "Primeira Liga", "SC1": "Scottish title", "BE1": "Belgian title",
    "TR1": "Süper Lig", "RU1": "Russian title", "SU1L": "Soviet title", "GR1": "Greek title", "BRA1": "Brasileirão",
    "AR1N": "Argentine title", "ARG1": "Argentine title", "ARGC": "Argentine title", "C1": "Czechoslovak title",
    "JL11": "Yugoslav title", "JL12": "Yugoslav title", "OLS1": "German title", "OLW1": "German title",
    "OLN1": "German title", "OLSW": "German title", "OLB1": "German title", "A1": "Austrian title",
    "FAC": "FA Cup", "CDR": "Copa del Rey", "CIT": "Coppa Italia", "DFB": "DFB-Pokal", "FRC": "Coupe de France",
    "NLP": "KNVB Cup", "POPO": "Taça de Portugal", "SFA": "Scottish Cup",
}


def club_names(ids: set[str]) -> dict[str, str]:
    out = {}
    for cid in sorted(i for i in ids if i):
        c = transfermarkt.club(cid)
        out[cid] = (c.get("baseDetails") or {}).get("shortName") or c.get("name") or cid
    return out


def voter_bias(df: pd.DataFrame, votes: pd.DataFrame) -> dict:
    """What real votes rewarded, holding the model's components fixed."""
    awarded = df[df["year"].isin(votes["year"].unique()) & df["qualified"]].copy()
    vs = votes.dropna(subset=["tm_id"]).copy()
    vs["points"] = vs["points"].fillna(31 - vs["rank"].clip(upper=30))
    vs["share"] = vs["points"] / vs.groupby("year")["points"].transform("sum")
    awarded = awarded.merge(vs[["year", "tm_id", "share"]], on=["year", "tm_id"], how="left")
    awarded["share"] = awarded["share"].fillna(0) * 100
    winners = vs[vs["rank"] == 1][["year", "tm_id"]]
    prev = {(y + (2 if y == 2019 else 1), t) for y, t in winners.itertuples(index=False)}
    awarded["prev_winner"] = [int((y, t) in prev) for y, t in zip(awarded["year"], awarded["tm_id"])]
    awarded["won_wc_or_euro"] = awarded["trophies"].apply(lambda t: int(bool({"FIWC", "EURO"} & set(t))))
    awarded["won_ucl"] = awarded["trophies"].apply(lambda t: int(bool({"CL", "EPL"} & set(t))))
    awarded["real_or_barca"] = awarded["main_club"].isin(["418", "131"]).astype(int)
    for p in ("MID", "DEF", "GK"):
        awarded[f"pos_{p}"] = (awarded["pos"] == p).astype(int)
    features_ = {
        "output_pos": "Individual output",
        "big_pos": "Big-game output",
        "goals": "Goals scored",
        "won_ucl": "Won the Champions League",
        "won_wc_or_euro": "Won the World Cup or Euro",
        "prev_winner": "Won it the year before",
        "real_or_barca": "Plays for Real or Barça",
        "pos_MID": "Midfielder",
        "pos_DEF": "Defender",
        "pos_GK": "Goalkeeper",
    }
    X = awarded[list(features_)].astype(float)
    X["goals"] = (X["goals"] - X["goals"].mean()) / X["goals"].std()
    fit = sm.OLS(awarded["share"], sm.add_constant(X)).fit(cov_type="cluster", cov_kwds={"groups": awarded["year"]})
    rows = [{"key": k, "label": v, "coef": round(float(fit.params[k]), 2),
             "lo": round(float(fit.conf_int().loc[k, 0]), 2), "hi": round(float(fit.conf_int().loc[k, 1]), 2)}
            for k, v in features_.items()]
    return {"unit": "percentage points of vote share", "n": int(fit.nobs), "r2": round(float(fit.rsquared), 3), "rows": rows}


def main():
    ids = sorted(matches.pool_ids())
    players = matches.load_players(ids)
    mt = matches.load_matches(list(players["tm_id"]))
    links = understat_link.link(mt, players)
    print(len(links), "players linked to Understat")
    mt = understat_link.attach(mt, understat_link.match_xg(links))
    print(int(mt["npxg"].notna().sum()), "matches with xG")
    extra = json.loads((OUT / "pool_extra.json").read_text()) if (OUT / "pool_extra.json").exists() else {}
    unverified = set(extra) - set(links) - set(json.loads((OUT / "pool_wiki.json").read_text()))
    mt = mt[~mt["tm_id"].isin(unverified)]
    players = players[~players["tm_id"].isin(unverified)]

    py = features.player_years(mt, players)
    df = model.score(py)
    df["total"] = model.total(df)
    votes = pd.DataFrame(json.loads((OUT / "votes.json").read_text()))
    df.to_parquet(OUT / "player_years.parquet")
    mt.to_parquet(OUT / "matches.parquet")
    players.to_parquet(OUT / "players.parquet")

    bias = voter_bias(df, votes)
    keep_parts = []
    for year, ydf in df.groupby("year"):
        voted = set(votes.loc[(votes["year"] == year) & (votes["rank"] <= 10), "tm_id"].dropna())
        keep_parts.append(ydf[ydf["tm_id"].isin(voted) | ydf["tm_id"].isin(ydf.nlargest(PER_YEAR, "total")["tm_id"])])
        # Keep the best of each position too, so the fairness slider has someone to promote.
        for pos in ("GK", "DEF", "MID", "FWD"):
            keep_parts.append(ydf[ydf["pos"] == pos].nlargest(6, "output_pos"))
    keep = pd.concat(keep_parts).drop_duplicates(["year", "tm_id"])
    clubs = club_names(set(keep["main_club"].dropna()) | set(keep["national_team"].dropna()))

    used = set(keep["tm_id"]) | set(votes["tm_id"].dropna())
    pl = players[players["tm_id"].isin(used)].set_index("tm_id")
    nat_of = keep.dropna(subset=["national_team"]).groupby("tm_id")["national_team"].agg(lambda s: s.mode().iat[0])

    def r2(x):
        return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), 2)

    years = []
    for year in range(features.FIRST_YEAR, features.LAST_YEAR + 1):
        start, end = features.window(year)
        yv = votes[votes["year"] == year].sort_values("rank")
        ydf = keep[keep["year"] == year].sort_values("total", ascending=False)
        years.append({
            "year": year, "from": str(start.date()), "to": str(end.date()), "tier": features.tier(year),
            "rule": features.eligibility_rule(year), "awarded": bool(len(yv)),
            "real": [{"id": r.tm_id if isinstance(r.tm_id, str) else None, "name": r.name, "rank": int(r.rank), "points": r2(r.points)}
                     for r in yv.itertuples()],
            "c": [{
                "id": r.tm_id, "pos": r.pos,
                "o": r2(r.output_pos), "oa": r2(r.output_all), "b": r2(r.big_pos), "ba": r2(r.big_all), "t": r2(r.trophy),
                "euro": r.nat_euro, "eclub": r.club_euro,
                "club": clubs.get(r.main_club), "m": int(r.matches), "min": int(r.minutes), "g": int(r.goals),
                "pg": int(r.pen_goals), "a": int(r.assists), "xg": r2(r.npxg), "xa": r2(r.xa), "bm": int(r.big_matches),
                "tr": [COMP_NAMES.get(c, c) for c in r.trophies], "lm": bool(r.league_missing),
            } for r in ydf.itertuples()],
        })
    data = {
        "generated": pd.Timestamp.now().strftime("%Y-%m-%d"),
        "weights": model.DEFAULT_WEIGHTS,
        "players": {pid: {"n": r["name"], "s": r["short_name"], "p": r["position"], "nat": clubs.get(nat_of.get(pid))}
                    for pid, r in pl.iterrows()},
        "years": years,
        "bias": bias,
    }
    WEB_DATA.parent.mkdir(parents=True, exist_ok=True)
    WEB_DATA.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False))
    print(f"wrote {WEB_DATA} ({WEB_DATA.stat().st_size // 1024} KB), {len(keep)} player-years")


if __name__ == "__main__":
    main()
