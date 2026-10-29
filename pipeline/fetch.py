"""Download raw data for the pool. Everything is cached under data/raw, so reruns are cheap."""
import json
import sys
from pathlib import Path

from pipeline.sources import transfermarkt, understat

OUT = Path(__file__).resolve().parent.parent / "data" / "out"


def tm(ids: list[str]):
    for n, pid in enumerate(ids, 1):
        try:
            transfermarkt.performance(pid)
            transfermarkt.profile(pid)
        except RuntimeError as e:
            print("FAILED", pid, e, flush=True)
        if n % 25 == 0:
            print(f"tm {n}/{len(ids)}", flush=True)


def understat_leagues():
    for season in range(understat.FIRST_SEASON, 2026):
        for lg in understat.LEAGUES:
            understat.league(lg, season)
        print("understat", season, flush=True)


if __name__ == "__main__":
    what = sys.argv[1]
    if what == "tm":
        from pipeline.matches import pool_ids
        tm(sorted(pool_ids()))
    elif what == "understat":
        understat_leagues()
