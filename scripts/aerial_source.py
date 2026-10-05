from collections import Counter
from datetime import datetime, timezone
import math

def count(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0 and int(value) == value else None


def player_stat(player, key):
    found = [s.get('stat', {}) for group in player.get('stats', []) for s in group.get('stats', {}).values() if s.get('key') == key]
    return found[0] if len(found) == 1 else {}



def team_stat(page, key, index, field='value'):
    values = [r.get('rawStats', []) for group in page.get('content', {}).get('stats', {}).get('Periods', {}).get('All', {}).get('stats', [])
              for r in group.get('stats', []) if r.get('key') == key and r.get('type') != 'title']
    if not values or len(values[0]) != 2:
        return None
    cell = values[0][index]
    return count(cell.get(field)) if isinstance(cell, dict) else None



def validate(p, row):
    g = p.get('general', {})
    assert str(g.get('matchId')) == row['id'], 'Fixture ID mismatch'
    assert str(g.get('leagueId')) == row['league_id'], 'League mismatch'
    assert g.get('finished') is True, 'Not finished'
    assert str(g.get('matchTimeUTCDate', ''))[:10] == row['date'][:10], 'Date mismatch'
    assert str(g.get('homeTeam', {}).get('id')) == row['home_id'], 'Home club mismatch'
    assert str(g.get('awayTeam', {}).get('id')) == row['away_id'], 'Away club mismatch'
    assert datetime.fromisoformat(g['matchTimeUTCDate'].replace('Z', '+00:00')) < datetime.now(timezone.utc), 'Future completed match'
    if row.get('score') is not None:
        assert p.get('header', {}).get('status', {}).get('scoreStr') == row['score'], 'Result disagrees with fixture inventory'


def extract(p, row):
    validate(p, row)
    c = p.get('content', {})
    lineup = c.get('lineup') or {}
    starter_ids, unused_bench, lineup_ok = set(), set(), str(lineup.get('matchId')) == row['id']
    for side, tid in [('homeTeam', row['home_id']), ('awayTeam', row['away_id'])]:
        team = lineup.get(side) or {}
        starters = team.get('starters') or []
        ids = [str(s.get('id')) for s in starters]
        lineup_ok &= (len(ids) == 11 and len(set(ids)) == 11 and 'None' not in ids
                      and str(team.get('id')) == tid and not starter_ids.intersection(ids))
        starter_ids.update(ids)
        unused_bench.update(str(s['id']) for s in (team.get('subs') or []) if not s.get('performance'))
    shots = (c.get('shotmap') or {}).get('shots')
    shots_ok = isinstance(shots, list) and all(isinstance(s, dict) and s.get('playerId') is not None and s.get('shotType') for s in shots)
    headers = Counter(str(s['playerId']) for s in shots if s['shotType'] == 'Header' and not s.get('isOwnGoal')) if shots_ok else {}
    players, exceptions = [], []
    for pid, player in (c.get('playerStats') or {}).items():
        if str(player.get('id')) != str(pid) or str(player.get('teamId')) not in (row['home_id'], row['away_id']):
            exceptions.append({'player_id': str(pid), 'reason': 'player_or_club_identity'}); continue
        minutes = count(player_stat(player, 'minutes_played').get('value'))
        if minutes is None:
            reason = 'unused_bench_no_stats' if str(pid) in unused_bench and not player.get('stats') else 'missing_minutes'
            exceptions.append({'player_id': str(pid), 'reason': reason}); continue
        if minutes == 0:
            continue
        aerial = player_stat(player, 'aerials_won')
        won, attempted = count(aerial.get('value')), count(aerial.get('total'))
        if won is None or attempted is None or won > attempted:
            won = attempted = None
        players.append({'id': str(pid), 'name': player.get('name'), 'team_id': str(player['teamId']),
                        'minutes': minutes, 'starter': str(pid) in starter_ids,
                        'aerials_won': won, 'aerials_attempted': attempted,
                        'headed_shots': headers.get(str(pid), 0) if shots_ok else None,
                        'keeper_high_claims': count(player_stat(player, 'keeper_high_claim').get('value')) if player.get('isGoalkeeper') else None,
                        'keeper_punches': count(player_stat(player, 'punches').get('value')) if player.get('isGoalkeeper') else None,
                        'usual_position': player.get('usualPosition'), 'goalkeeper': player.get('isGoalkeeper') is True})
    delivery = [{'team_id': tid, 'corners': team_stat(p, 'corners', i),
                 'crosses_attempted': team_stat(p, 'accurate_crosses', i, 'total'),
                 'crosses_accurate': team_stat(p, 'accurate_crosses', i)}
                for i, tid in enumerate((row['home_id'], row['away_id']))]
    starter_minutes_ok = lineup_ok and starter_ids.issubset({v['id'] for v in players})
    outfield = [p for p in players if not p['goalkeeper']]
    coverage = {'lineups': bool(lineup_ok), 'starter_minutes': starter_minutes_ok,
                'shotmap': bool(shots_ok), 'delivery': all(t['corners'] is not None and t['crosses_attempted'] is not None for t in delivery),
                'player_aerials_complete': bool(players) and all(p['aerials_won'] is not None for p in players),
                'outfield_aerials_complete': bool(outfield) and all(p['aerials_won'] is not None for p in outfield)}
    return {'id': row['id'], 'league_id': row['league_id'], 'season': row['season'],
            'date': row['date'], 'home_id': row['home_id'], 'away_id': row['away_id'],
            'coverage': coverage, 'players': players, 'delivery': delivery, 'exceptions': exceptions}



