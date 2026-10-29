import pandas as pd

from pipeline import comps, features, model


def test_window_switches_to_seasons_in_2022():
    assert features.window(2021) == (pd.Timestamp("2021-01-01"), pd.Timestamp("2021-12-31"))
    assert features.window(2022) == (pd.Timestamp("2021-08-01"), pd.Timestamp("2022-07-31"))


def test_eligibility_eras():
    assert features.eligibility_rule(1994) == "europeans"
    assert features.eligibility_rule(1995) == "european_clubs"
    assert features.eligibility_rule(2007) == "open"


def test_old_european_cup_is_not_the_premier_league():
    assert comps.classify("EPL", 10).kind == "ucl"
    assert comps.classify("GB1", 1).kind == "league"


def test_round_codes():
    assert comps.round_key("AFH") == "AF"
    assert comps.round_key("FF") == "FF"
    assert comps.round_key("B") is None


def _match(**kw):
    base = dict(tm_id="1", game_id="g", date=pd.Timestamp("2015-06-06"), comp="CL", comp_type=10, round="FF", season=2014,
                national=False, game_state="regularly_terminated", club_id="131", opp_id="506", club_rank=None,
                opp_rank=None, gf=3, ga=1, points=3, state="played", position_id=12, minutes=90, starting=True,
                goals=0, pen_goals=0, assists=1, own_goals=0, team_goals_on=3, opp_goals_on=1, pen_saves=0,
                kind="ucl", stake=1.25, played=True, pos_group_match="FWD")
    base.update(kw)
    return base


def test_final_winner_gets_the_trophy_and_the_loser_does_not():
    m = pd.DataFrame([_match(), _match(tm_id="2", club_id="506", opp_id="131", gf=1, ga=3, points=0)])
    t = features.trophies(features.prepare(m))
    assert list(t["tm_id"]) == ["1"]
    assert t.iloc[0]["value"] == 1.0


def test_shootout_final_counts_for_the_team_awarded_three_points():
    m = pd.DataFrame([_match(game_state="penalty_shootout", gf=6, ga=4, points=3)])
    assert len(features.trophies(features.prepare(m))) == 1


def test_league_title_needs_first_place_at_season_end():
    rows = [_match(comp="ES1", comp_type=1, round="", kind="league", stake=1.0, club_rank=1,
                   date=pd.Timestamp("2015-05-23"), game_id="a"),
            _match(tm_id="2", comp="ES1", comp_type=1, round="", kind="league", stake=1.0, club_rank=2,
                   club_id="418", date=pd.Timestamp("2015-05-23"), game_id="b")]
    t = features.trophies(features.prepare(pd.DataFrame(rows)))
    assert list(t["tm_id"]) == ["1"]


def test_total_respects_fairness_blend():
    df = pd.DataFrame({"output_pos": [2.0], "output_all": [0.0], "big_pos": [1.0], "big_all": [0.0], "trophy": [0.0]})
    full = model.total(df, fairness=1.0).iat[0]
    none = model.total(df, fairness=0.0).iat[0]
    assert full == 0.5 * 2.0 + 0.25 * 1.0
    assert none == 0.0
