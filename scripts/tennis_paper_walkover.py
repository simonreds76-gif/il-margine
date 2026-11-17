"""Evidence used only when grading recorded ATP player-prop contracts."""
import csv
from datetime import date
from oncourt_nonplayed import settlement_games


def csv_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        yield from csv.DictReader(handle)


def result_rows(directory):
    return settlement_games(directory, "atp", csv_rows)


def consistent_walkover(game, scheduled, registered, observed, has_stats):
    """Require dated native evidence compatible with the captured fixture and no play."""
    if has_stats or not scheduled or not registered or registered >= scheduled:
        return False
    try:
        result_day = date.fromisoformat(game["date"])
    except (ValueError, TypeError, KeyError):
        return False
    return (registered.date() <= result_day <= observed.date()
            and abs((result_day - scheduled.date()).days) <= 1)

