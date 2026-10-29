"""Club and national-team Elo computed from every distinct match in the pool's logs.

ClubElo's API was down, and this has the bonus of linking leagues through European
cup results instead of a hand-set strength table.
"""
import numpy as np
import pandas as pd

from pipeline import comps

K = 20
HOME_ADVANTAGE = 60
# Seeds put a club's first rating near its league's level; results take over from there.
SEED_BASE, SEED_SPAN = 1200, 400


def _gd_multiplier(gd: int) -> float:
    return 1.0 if gd <= 1 else 1.5 if gd == 2 else (11 + gd) / 8


def compute(m: pd.DataFrame) -> pd.DataFrame:
    """Return one row per (game_id, club_id) with both sides' pre-match ratings."""
    games = (m.sort_values("date")
               .drop_duplicates("game_id")[["game_id", "date", "club_id", "opp_id", "gf", "ga", "home",
                                            "comp", "comp_type", "kind", "game_state", "national"]])
    seed: dict[str, float] = {}
    league = games[games["kind"] == "league"]
    for team_col in ("club_id", "opp_id"):
        for team, comp, ctype in league[[team_col, "comp", "comp_type"]].itertuples(index=False):
            seed.setdefault(team, SEED_BASE + SEED_SPAN * comps.league_strength(comp, ctype))
    rating: dict[str, float] = {}
    out = []
    for g in games.itertuples(index=False):
        a, b = g.club_id, g.opp_id
        ra = rating.get(a, seed.get(a, 1500.0))
        rb = rating.get(b, seed.get(b, 1500.0))
        out.append((g.game_id, a, ra, rb))
        out.append((g.game_id, b, rb, ra))
        if g.kind in ("youth", "friendly") or pd.isna(g.gf) or pd.isna(g.ga):
            continue
        adv = HOME_ADVANTAGE if (g.home and g.kind == "league") else (-HOME_ADVANTAGE if g.kind == "league" else 0)
        expected = 1 / (1 + 10 ** ((rb - ra - adv) / 400))
        if g.game_state == "penalty_shootout":
            score, gd = 0.5, 0
        else:
            score = 1.0 if g.gf > g.ga else 0.5 if g.gf == g.ga else 0.0
            gd = abs(int(g.gf) - int(g.ga))
        delta = K * _gd_multiplier(gd) * (score - expected)
        rating[a] = ra + delta
        rating[b] = rb - delta
    return pd.DataFrame(out, columns=["game_id", "club_id", "elo", "opp_elo"])


def attach(m: pd.DataFrame) -> pd.DataFrame:
    r = compute(m).drop_duplicates(["game_id", "club_id"])
    return m.merge(r, on=["game_id", "club_id"], how="left")
