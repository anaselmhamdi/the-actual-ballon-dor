"""Turn player-year features into position-normalized component scores."""
import numpy as np
import pandas as pd

ERA_HALF_WIDTH = 5
MIN_MINUTES = 900

# Sub-metric blend per position: what "output" means for each role.
OUTPUT_RECIPE = {
    "FWD": {"attack_total": 0.45, "attack_rate": 0.30, "team": 0.15, "volume": 0.10},
    "MID": {"attack_total": 0.35, "attack_rate": 0.20, "team": 0.25, "def_cs": 0.10, "volume": 0.10},
    "DEF": {"attack_total": 0.10, "def_conc": 0.30, "def_cs": 0.20, "team": 0.25, "volume": 0.15},
    "GK": {"def_conc": 0.35, "def_cs": 0.25, "team": 0.25, "volume": 0.15},
}
# Tier A has expected-goals-against, which separates a defence from a goalkeeper's shot-stopping.
OUTPUT_RECIPE_XG = {
    "DEF": {"attack_total": 0.10, "def_conc": 0.15, "def_xga": 0.20, "def_cs": 0.15, "team": 0.25, "volume": 0.15},
    "GK": {"def_conc": 0.15, "gk_saved": 0.30, "def_cs": 0.15, "team": 0.25, "volume": 0.15},
}
ATTACK_RECIPE = OUTPUT_RECIPE["FWD"]


def sub_metrics(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in ["cs_rate", "conceded_p90", "xga_p90", "gk_saved_p90", "npxg", "xa"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    prior = (df["adj_attack"].sum() / df["adj_minutes"].sum())
    k = 6.0
    by_pos_prior = df.groupby("pos").apply(lambda g: g["adj_attack"].sum() / max(g["adj_minutes"].sum(), 1), include_groups=False)
    pp = df["pos"].map(by_pos_prior).fillna(prior)
    df["attack_total"] = df["adj_attack"]
    df["attack_rate"] = (df["adj_attack"] + k * pp) / (df["adj_minutes"] + k)
    df["team"] = df["ppg"]
    df["volume"] = df["adj_minutes"].clip(upper=60)
    df["def_cs"] = df["cs_rate"]
    df["def_conc"] = -df["conceded_p90"]
    df["def_xga"] = -df["xga_p90"]
    df["gk_saved"] = df["gk_saved_p90"]
    return df


def _zscore(values: pd.Series, ref: pd.Series) -> pd.Series:
    ref = ref.dropna()
    if len(ref) < 3 or ref.std() == 0:
        return pd.Series(0.0, index=values.index)
    return ((values - ref.mean()) / ref.std()).fillna(-0.5)


def score(df: pd.DataFrame) -> pd.DataFrame:
    df = sub_metrics(df)
    df["qualified"] = (df["minutes"] >= MIN_MINUTES) | (df["league_missing"] & (df["matches"] >= 4))
    q = df[df["qualified"]]
    out = []
    for year, ydf in df[df["qualified"]].groupby("year"):
        ref = q[(q["year"] - year).abs() <= ERA_HALF_WIDTH]
        ydf = ydf.copy()
        cols = {}
        for metric in ["attack_total", "attack_rate", "team", "volume", "def_cs", "def_conc", "def_xga", "gk_saved"]:
            cols[f"zall_{metric}"] = _zscore(ydf[metric], ref[metric])
            zp = pd.Series(0.0, index=ydf.index)
            for pos, pdf in ydf.groupby("pos"):
                zp.loc[pdf.index] = _zscore(pdf[metric], ref.loc[ref["pos"] == pos, metric])
            cols[f"zpos_{metric}"] = zp
        z = pd.DataFrame(cols, index=ydf.index)
        recipe_out = []
        for idx, r in ydf.iterrows():
            recipe = OUTPUT_RECIPE[r["pos"]]
            if r["pos"] in OUTPUT_RECIPE_XG and pd.notna(r["xga_p90"]):
                recipe = OUTPUT_RECIPE_XG[r["pos"]]
            recipe_out.append(sum(w * z.at[idx, f"zpos_{k}"] for k, w in recipe.items()))
        ydf["output_pos_raw"] = recipe_out
        ydf["output_all_raw"] = sum(w * z[f"zall_{k}"] for k, w in ATTACK_RECIPE.items())
        out.append(ydf)
    df = pd.concat(out)
    # Restandardize the blended components so the three sliders act on comparable scales.
    final = []
    for year, ydf in df.groupby("year"):
        ref = df[(df["year"] - year).abs() <= ERA_HALF_WIDTH]
        ydf = ydf.copy()
        ydf["output_pos"] = 0.0
        ydf["big_pos"] = 0.0
        for pos, pdf in ydf.groupby("pos"):
            rp = ref[ref["pos"] == pos]
            ydf.loc[pdf.index, "output_pos"] = _zscore(pdf["output_pos_raw"], rp["output_pos_raw"])
            ydf.loc[pdf.index, "big_pos"] = _zscore(pdf["big_score"], rp["big_score"])
        ydf["output_all"] = _zscore(ydf["output_all_raw"], ref["output_all_raw"])
        ydf["big_all"] = _zscore(ydf["big_score"], ref["big_score"])
        ydf["trophy"] = _zscore(np.sqrt(ydf["trophy_score"]), np.sqrt(ref["trophy_score"]))
        final.append(ydf)
    return pd.concat(final)


DEFAULT_WEIGHTS = {"output": 0.5, "big": 0.25, "trophy": 0.25}


def total(df: pd.DataFrame, weights=DEFAULT_WEIGHTS, fairness: float = 0.7) -> pd.Series:
    out = fairness * df["output_pos"] + (1 - fairness) * df["output_all"]
    big = fairness * df["big_pos"] + (1 - fairness) * df["big_all"]
    return weights["output"] * out + weights["big"] * big + weights["trophy"] * df["trophy"]
