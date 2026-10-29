"""Transfermarkt competition IDs → how much a match there should count."""
from dataclasses import dataclass

# Transfermarkt competitionTypeId groups (from their player-performance bundle).
LEAGUE_TYPES = {1, 2, 3, 4, 5, 6, 7, 12, 18, 24}
YOUTH_TYPES = {17, 18, 20}

TOP_LEAGUES = {"ES1", "IT1", "GB1", "EFD1", "L1"}
STRONG_LEAGUES = {"FR1": 0.9, "PO1": 0.85, "NL1": 0.85, "OLS1": 0.85, "OLW1": 0.85, "OLN1": 0.85, "OLSW": 0.85,
                  "OLB1": 0.8, "BRA1": 0.85, "AR1N": 0.85, "ARG1": 0.85, "ARGC": 0.85}
WEAK_LEAGUES = {"MLS1", "SA1", "CSL", "JAP1", "MEX1", "MEXA", "QSL", "UAE1", "IND1", "AUS1"}

EUROPEAN_CUP = {"CL", "EPL"}
SECOND_EURO = {"UEFA", "EL", "EPP", "ITC"}
CONT_OTHER = {"CLI": 1.1, "KLUB": 1.0, "WEPO": 1.0}
MAJOR_NATIONAL = {"FIWC": 1.4, "EURO": 1.25, "COPA": 1.2, "CA16": 1.2, "AFCN": 1.0, "GOCU": 0.9,
                  "CONC": 0.9, "UNFI": 0.9, "AFT": 1.0}

TROPHY_VALUE = {"FIWC": 1.0, "CL": 1.0, "EPL": 1.0, "EURO": 0.7, "COPA": 0.6, "CA16": 0.6, "CLI": 0.6,
                "AFCN": 0.35, "GOCU": 0.25, "UEFA": 0.35, "EL": 0.35, "EPP": 0.35, "ITC": 0.3,
                "KLUB": 0.15, "WEPO": 0.15, "UNFI": 0.2, "CONC": 0.15, "AFT": 0.15}
LEAGUE_TITLE_VALUE = 0.6
DOMESTIC_CUP_VALUE = 0.2

BIG_GAME_COMP = {"FIWC": 1.2, "CL": 1.0, "EPL": 1.0, "EURO": 0.9, "COPA": 0.8, "CA16": 0.8, "CLI": 0.6,
                 "UEFA": 0.4, "EL": 0.4, "EPP": 0.4, "ITC": 0.35, "AFCN": 0.5, "KLUB": 0.3, "WEPO": 0.4}
ROUND_WEIGHT = {"AF": 1.0, "VF": 1.5, "HF": 2.0, "FF": 3.0, "PD": 1.0}

# Competitions that only national teams/clubs from one confederation enter.
UEFA_ONLY = {"EURO", "EMQ", "WMQ6", "UNLA", "UNFI", "POEM", "POWM", "CL", "EPL", "UEFA", "EL", "EPP", "ITC",
             "CLQ", "ELQ", "UEQ", "UI", "USC", "ECLQ"}
NON_UEFA = {"COPA", "CA16", "WMQ4", "WMQ2", "WMQ1", "WMQ3", "WMQ5", "AFCN", "AFCQ", "GOCU", "CLI", "SUC",
            "CCL", "ACL", "AFCL", "ACLE", "ACL2", "CS", "CMER", "CCON", "ACWC"}


@dataclass(frozen=True)
class Comp:
    kind: str  # league | cup | league_cup | supercup | ucl | uel | cont | national_major | qualifier | friendly | youth | other
    stake: float


def classify(comp: str, comp_type: int) -> Comp:
    if comp_type in YOUTH_TYPES or comp in {"OLYM", "U21Q"}:
        return Comp("youth", 0.0)
    if comp in EUROPEAN_CUP:
        return Comp("ucl", 1.25)
    if comp in SECOND_EURO:
        return Comp("uel", 1.0)
    if comp in CONT_OTHER:
        return Comp("cont", CONT_OTHER[comp])
    if comp in MAJOR_NATIONAL:
        return Comp("national_major", MAJOR_NATIONAL[comp])
    if comp == "FS":
        return Comp("friendly", 0.35)
    if comp_type == 19:
        return Comp("qualifier", 0.8)
    if comp_type in LEAGUE_TYPES:
        return Comp("league", league_strength(comp, comp_type))
    if comp_type == 8:
        return Comp("cup", 0.7)
    if comp_type == 14:
        return Comp("league_cup", 0.5)
    if comp_type in (9, 13):
        return Comp("supercup", 0.4)
    if comp_type == 10:
        return Comp("cont", 0.8)
    if comp_type == 11:
        return Comp("national_major", 0.9)
    return Comp("other", 0.5)


def league_strength(comp: str, comp_type: int) -> float:
    if comp_type == 2:
        return 0.5
    if comp_type not in (1, 24):
        return 0.6 if comp_type == 12 else 0.45
    if comp in TOP_LEAGUES:
        return 1.0
    if comp in STRONG_LEAGUES:
        return STRONG_LEAGUES[comp]
    if comp in WEAK_LEAGUES:
        return 0.6
    if comp_type == 24:
        return 0.75
    return 0.72


def round_key(code: str) -> str | None:
    for k in ROUND_WEIGHT:
        if code.startswith(k):
            return k
    return None
