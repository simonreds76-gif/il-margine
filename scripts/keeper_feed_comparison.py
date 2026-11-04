"""Private source agreement only: no model, odds, ledger or notification writes."""
import hashlib
import json
import math
from datetime import datetime, timezone
from football_identity import folded
from football_identity_research import lookup

SIDES = ('home', 'away')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def instant(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(timezone.utc)


def count(value):
    if value is None or isinstance(value, bool) or value == '':
        return None
    try:
        v = float(value)
        return int(v) if math.isfinite(v) and v >= 0 and v.is_integer() else None
    except (TypeError, ValueError):
        return None


def espn_sides(event):
    comp = event['competitions'][0]
    sides = {r['homeAway']: r for r in comp['competitors']}
    if len(comp['competitors']) != 2 or set(sides) != set(SIDES):
        raise ValueError('ambiguous_event_sides')
    return comp, sides


def team_matches(ref, provider, foreign, config):
    bridge = config.get('teams', {}).get(str(ref['id']), {}).get(provider)
    if bridge:
        return str(foreign['id']) == str(bridge['id'])
    # Exact whole names only; no fuzzy/substrings and no venue-only joins.
    names = [foreign.get(k) for k in ('name', 'displayName', 'shortDisplayName')]
    return folded(ref['name']) in {folded(n) for n in names if n}


def fixture_ok(ref, goal, espn, config):
    comp, sides = espn_sides(espn)
    if goal.get('matchStatus') != 'FINISHED' or comp['status']['type'].get('completed') is not True:
        raise ValueError('unfinished_fixture')
    expected = instant(ref['kickoff'])
    if instant(goal['kickoffUtc']) != expected or instant(comp['date']) != expected:
        raise ValueError('kickoff_mismatch')
    league = config['leagues'][str(ref['league_id'])]
    if str(goal['leagueId']) != league['goal']:
        raise ValueError('league_mismatch')
    score = {}
    for side in SIDES:
        if not team_matches(ref[side], 'goal', {'id': goal[side+'TeamId'], 'name': goal[side+'TeamName']}, config):
            raise ValueError('goal_team_identity')
        if not team_matches(ref[side], 'espn', sides[side]['team'], config):
            raise ValueError('espn_team_identity')
        a, b = count(goal[side+'TeamScore']), count(sides[side]['score'])
        if a is None or b is None or a != b:
            raise ValueError('result_disagreement')
        if ref[side].get('score') is not None and a != count(ref[side]['score']):
            raise ValueError('reference_result_disagreement')
        score[side] = a
    return score


def stats(row):
    out = {}
    for item in row.get('stats', row.get('statistics', [])):
        name, value = item['name'], count(item.get('value', item.get('displayValue')))
        if name in out and out[name] != value:
            raise ValueError('duplicate_conflicting_espn_stat')
        out[name] = value
    return out


def pick_player(root, ref, candidates, provider, fixture, config):
    def pid(row):
        return str(row['playerId'] if provider == 'goal' else row['athlete']['id'])
    if len({pid(x) for x in candidates}) != len(candidates):
        return None, 'duplicate_roster_identity'
    reviewed = config.get('fixture_player_aliases', {}).get(f'{fixture}/{ref["player_id"]}/{provider}')
    link = lookup(root, ref['player_id'], 'espn', 'person') if provider == 'espn' else {}
    if link.get('status') in ('reviewed_id_conflict', 'target_collision', 'ambiguous_target',
                              'ambiguous_source', 'withdrawn_or_inactive_source', 'existing_id_conflict'):
        return None, link['status']
    target = link.get('id') or reviewed
    if target:
        if reviewed and link.get('id') and str(reviewed) != link['id']:
            return None, 'alias_registry_conflict'
        hits = [r for r in candidates if pid(r) == str(target)]
        return (hits[0], link.get('status', 'reviewed_fixture_identity')) if len(hits) == 1 else (None, 'mapped_id_absent_from_same_team')
    wanted = folded(ref['player'])
    def names(row):
        return [row.get('playerName'), row.get('player', {}).get('name')] if provider == 'goal' else [row['athlete'].get(k) for k in ('fullName', 'displayName')]
    hits = [r for r in candidates if wanted in {folded(n) for n in names(r) if n}]
    return (hits[0], 'exact_same_team_name') if len(hits) == 1 else (None, 'identity_unresolved')


def compare(root, ref, goal_fixture, goal_stats, espn, config, observed_at):
    score = fixture_ok(ref, goal_fixture, espn['header'], config)
    data = goal_stats['data']
    if data.get('hasStatistics') is not True:
        raise ValueError('goal_statistics_unavailable')
    rows, flags = [], []
    for side in SIDES:
        gp = data.get('players', {}).get(side, [])
        if any(str(p.get('fixtureId')) != str(goal_fixture['id']) for p in gp):
            raise ValueError('goal_statistics_wrong_fixture')
        rosters = [r for r in espn.get('rosters', []) if r['homeAway'] == side]
        if len(rosters) != 1:
            raise ValueError('espn_roster_missing_or_duplicate')
        _, competition = espn_sides(espn['header'])
        if str(rosters[0]['team']['id']) != str(competition[side]['team']['id']):
            raise ValueError('espn_roster_wrong_team')
        ep = rosters[0]['roster']
        refs = [r for r in ref['keepers'] if str(r['team_id']) == str(ref[side]['id'])]
        active_gp = [p for p in gp if p.get('playerPosition') == 'Goalkeepers' and (count(p.get('minutesPlayed')) or 0) > 0]
        for player in refs:
            g, gm = pick_player(root, player, gp, 'goal', ref['match_id'], config)
            e, em = pick_player(root, player, ep, 'espn', ref['match_id'], config)
            reasons = []
            if g is None or e is None:
                reasons.append('identity_unresolved')
            if g is not None and (g.get('playerPosition') != 'Goalkeepers' or (count(g.get('minutesPlayed')) or 0) <= 0):
                reasons.append('goal_not_playing_keeper')
            if e is not None and (e.get('position', {}).get('abbreviation') not in ('G', 'GK') or not (e.get('starter') or e.get('subbedIn'))):
                reasons.append('espn_not_playing_keeper')
            es = stats(e) if e is not None else {}
            values = {'reference': count(player.get('saves')), 'goal': count(g.get('saves')) if g else None, 'espn': es.get('saves')}
            if any(x is None for x in values.values()):
                reasons.append('missing_saves')
            elif len(set(values.values())) != 1:
                reasons.append('saves_disagreement')
            if player.get('target_conflict'):
                reasons.append('reference_event_conflict')
            rows.append({'side': side, 'player_id': str(player['player_id']), 'player': player['player'],
                         'goal_player_id': str(g['playerId']) if g else None,
                         'espn_player_id': str(e['athlete']['id']) if e else None,
                         'goal_identity': gm, 'espn_identity': em, 'saves': values,
                         'reference_minutes': player.get('minutes'), 'goal_minutes_diagnostic_only': count(g.get('minutesPlayed')) if g else None,
                         'goal_punches': count(g.get('punches')) if g else None,
                         'goal_updated_at': g.get('updatedAt') if g else None,
                         'flags': reasons})
        # Team saves must reconcile ALL appearing keepers, including substitutions.
        totals = {count(s.get(side)) for s in data.get('match', {}).get('fullTime', []) if s.get('type') == 'Saves'}
        saves = [count(p.get('saves')) for p in active_gp]
        if len(totals) != 1 or None in totals or not saves or None in saves:
            flags.append(side + ':goal_team_saves_missing_or_conflicting')
        elif sum(saves) != next(iter(totals)):
            flags.append(side + ':goal_team_keeper_saves_conflict')
        expected_ids = {r['goal_player_id'] for r in rows if r['side'] == side and r['goal_player_id']}
        if expected_ids != {str(p['playerId']) for p in active_gp}:
            flags.append(side + ':keeper_appearance_coverage')
        active_ep = [p for p in ep if p.get('position', {}).get('abbreviation') in ('G', 'GK') and (p.get('starter') or p.get('subbedIn'))]
        expected_ep = {r['espn_player_id'] for r in rows if r['side'] == side and r['espn_player_id']}
        if expected_ep != {str(p['athlete']['id']) for p in active_ep}:
            flags.append(side + ':espn_keeper_appearance_coverage')
    if not rows:
        raise ValueError('no_reference_keepers')
    status = 'agreement' if not flags and not any(r['flags'] for r in rows) else 'quarantined'
    record = {'schema_version': 1, 'match_id': ref['match_id'], 'kickoff': ref['kickoff'],
            'league_id': ref['league_id'], 'home': ref['home'], 'away': ref['away'],
            'goal_fixture_id': goal_fixture['id'], 'espn_fixture_id': espn['header']['id'],
            'observed_at': observed_at, 'reference_observed_at': ref['observed_at'],
            'source_hashes': {'reference': ref['source_sha256'], 'goal_fixture': digest(goal_fixture),
                              'goal_statistics': digest(goal_stats), 'espn': digest(espn)},
            'result': score, 'status': status, 'flags': flags, 'keepers': rows,
            'purpose': 'source comparison; no model inputs or settlements changed'}
    return apply_reviewed_counts(record, ref, config)


def apply_reviewed_counts(record, ref, config):
    """Separate a reviewed published total from an unresolved event discrepancy.

    Only an exact, dated review may release the source-comparison quarantine.
    Native history/event labels, model inputs and settlements are never edited.
    A changed reference, identity or provider total invalidates the decision.
    """
    for keeper in record['keepers']:
        if keeper['flags'] != ['reference_event_conflict']:
            continue
        originals = [x for x in ref['keepers'] if str(x['player_id']) == keeper['player_id']]
        reviews = [x for x in config.get('reviewed_published_counts', [])
                   if str(x['match_id']) == str(record['match_id']) and str(x['player_id']) == keeper['player_id']]
        if len(originals) != 1 or len(reviews) != 1:
            continue
        original, review = originals[0], reviews[0]
        try:
            valid = (review['scope'] == 'source_comparison_only'
                and instant(review['kickoff']) == instant(record['kickoff'])
                and str(review['league_id']) == str(record['league_id'])
                and str(review['team_id']) == str(ref[keeper['side']]['id'])
                and review['reference_sha256'] == ref['source_sha256']
                and str(review['goal_player_id']) == keeper['goal_player_id']
                and str(review['espn_player_id']) == keeper['espn_player_id']
                and original.get('started') is True and original.get('minutes') == 90
                and original.get('event_saves') == review['event_saves']
                and all(v == review['published_saves'] for v in keeper['saves'].values())
                and len(set(review['source_urls'])) >= 2 and bool(review['reason'])
                and instant(record['kickoff']) < instant(review['reviewed_at']) <= datetime.now(timezone.utc))
        except (KeyError, ValueError, TypeError):
            valid = False
        if not valid:
            continue
        keeper['flags'] = []
        keeper['event_evidence'] = {'status':'disagreement_retained', 'event_saves':original['event_saves'],
                                   'published_saves':review['published_saves'], 'original_flag':'reference_event_conflict'}
        keeper['published_count_review'] = dict(review)
    if not record['flags'] and not any(x['flags'] for x in record['keepers']):
        record['status'] = ('reviewed_agreement' if any(x.get('published_count_review') for x in record['keepers']) else 'agreement')
    return record


def append_record(archive, record):
    # Source revisions retained, identical rechecks do not add observations.
    signature = digest({k: v for k, v in record.items() if k not in ('observed_at', 'cohort')})
    versions = archive.setdefault('fixtures', {}).setdefault(str(record['match_id']), [])
    if any(r['record_sha256'] == signature for r in versions):
        return False
    versions.append(dict(record, record_sha256=signature))
    return True
