"""Deduplicate alias-labelled team results before computing rolling form."""
from collections.abc import Callable
from typing import Any

COUNT_FIELDS = tuple(f'{metric}_{side}' for metric in ('goals','shots','sot','corners','xg') for side in ('for','against'))


def unique_team_results(rows: list[dict[str, Any]], team_key: Callable[[str], str]) -> list[dict[str, Any]]:
    indexed = {}
    for original in rows:
        row = dict(original)
        row['team_key'] = team_key(row.get('team') or row.get('team_key', ''))
        row['opponent_key'] = team_key(row.get('opponent') or row.get('opponent_key', ''))
        identity = (row['date'], row['league'], row['team_key'])
        previous = indexed.get(identity)
        if previous is None:
            indexed[identity] = row
            continue
        if any(previous.get(f) != row.get(f) for f in ('opponent_key', 'venue')):
            raise ValueError(f'Conflicting fixtures for team/day: {identity}')
        for field in COUNT_FIELDS:
            old, new = previous.get(field), row.get(field)
            if old not in (None, '') and new not in (None, '') and float(old) != float(new):
                raise ValueError(f'Conflicting {field} for team/day: {identity}')
        for field, value in row.items():
            if previous.get(field) in (None, '') and value not in (None, ''):
                previous[field] = value
    return list(indexed.values())
