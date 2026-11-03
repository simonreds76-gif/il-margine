#!/usr/bin/env python3
"""Bounded daily GOAL/ESPN source check. No odds calls, alerts or live writes."""
import argparse
import json
import os
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
import requests
from football_identity import read, write
from keeper_feed_comparison import append_record, compare, digest, espn_sides, instant, team_matches

DEST = Path('data/goalkeeper-saves/source-comparison')


class BudgetError(RuntimeError):
    pass


class Client:
    def __init__(self, goal_key, goal_cap, espn_cap, seconds=240):
        self.goal_key = goal_key
        self.caps = {'goal': goal_cap, 'espn': espn_cap}
        self.used = Counter()
        self.cache = {}
        self.deadline = time.monotonic() + seconds
        self.receipts = []

    def get(self, source, path, params=None):
        key = (source, path, json.dumps(params or {}, sort_keys=True))
        if key in self.cache:
            return self.cache[key]
        if self.used[source] >= self.caps[source] or time.monotonic() >= self.deadline:
            raise BudgetError('request_or_time_budget_exhausted')
        if source == 'goal' and not self.goal_key:
            raise RuntimeError('goal_credential_missing')
        base = 'https://api.goal-api.com/v1' if source == 'goal' else 'https://site.api.espn.com/apis/site/v2/sports/soccer'
        headers = {'Accept': 'application/json', 'User-Agent': 'IlMargine-private-source-comparison/1.0'}
        if source == 'goal':
            headers['Authorization'] = 'Bearer ' + self.goal_key
        self.used[source] += 1
        # Redirects are rejected so credentials never leave the authorized host.
        try:
            response = requests.get(base+path, params=params, headers=headers, timeout=min(20, max(1, self.deadline-time.monotonic())), allow_redirects=False)
        except requests.RequestException:
            raise RuntimeError(source + '_transport_error') from None
        receipt = {'source': source, 'url': base+path, 'params': params,
                   'http_status': response.status_code, 'observed_at': datetime.now(timezone.utc).isoformat()}
        self.receipts.append(receipt)
        if response.status_code != 200:
            raise RuntimeError(source + '_http_' + str(response.status_code))
        try:
            body = response.json()
        except ValueError:
            raise RuntimeError(source + '_invalid_json') from None
        if source == 'goal' and body.get('success') is False:
            raise RuntimeError('goal_application_error')
        receipt['sha256'] = digest(body)
        self.cache[key] = body
        return body


def find_goal(client, ref, config, start, end):
    league = config['leagues'][str(ref['league_id'])]['goal']
    all_rows = []
    # League/date filters avoid paging the worldwide fixture catalogue.
    for offset in (0, 100, 200):
        payload = client.get('goal', '/fixtures', {'from': start, 'to': end, 'leagueId': league, 'status': 'FINISHED', 'limit': 100, 'offset': offset})
        rows = payload.get('data')
        if not isinstance(rows, list):
            raise ValueError('goal_calendar_schema')
        if any(str(r['leagueId']) != league for r in rows):
            raise ValueError('goal_calendar_filter_not_respected')
        all_rows.extend(rows)
        if len(rows) < 100:
            break
    else:
        raise ValueError('goal_calendar_truncated')
    hits = [r for r in all_rows if instant(r['kickoffUtc']) == instant(ref['kickoff']) and
            all(team_matches(ref[s], 'goal', {'id': r[s+'TeamId'], 'name': r[s+'TeamName']}, config) for s in ('home', 'away'))]
    if len(hits) != 1:
        raise ValueError('goal_fixture_identity_unresolved')
    return hits[0]


def find_espn(client, ref, config):
    slug = config['leagues'][str(ref['league_id'])]['espn']
    calendar = client.get('espn', f'/{slug}/scoreboard', {'dates': instant(ref['kickoff']).strftime('%Y%m%d')})
    hits = []
    for event in calendar.get('events', []):
        comp, sides = espn_sides(event)
        if instant(comp['date']) == instant(ref['kickoff']) and all(team_matches(ref[s], 'espn', sides[s]['team'], config) for s in ('home', 'away')):
            hits.append(event)
    if len(hits) != 1:
        raise ValueError('espn_fixture_identity_unresolved')
    body = client.get('espn', f'/{slug}/summary', {'event': hits[0]['id']})
    if str(body['header']['id']) != str(hits[0]['id']):
        raise ValueError('espn_summary_wrong_fixture')
    return body


def report(archive, state, config, now, requests_used, receipts, considered):
    latest = [v[-1] for v in archive.get('fixtures', {}).values()]
    keepers = [r for f in latest for r in f['keepers']]
    paired = [r for r in keepers if all(v is not None for v in r['saves'].values())]
    unresolved = {k: v for k, v in state.items() if v['status'] not in ('agreement', 'quarantined')}
    return {'schema_version': 1, 'generated_at': now, 'purpose': 'private data agreement, not betting performance',
            'models_unchanged': True, 'fixtures': len(latest), 'keepers': len(keepers),
            'fixture_status': dict(Counter(f['status'] for f in latest)),
            'by_league': {lid: dict(Counter(f['status'] for f in latest if str(f['league_id']) == lid)) for lid in config['leagues']},
            'cohorts': dict(Counter(f['cohort'] for f in latest)),
            'paired_saves': len(paired), 'saves_all_three_equal': sum(len(set(r['saves'].values())) == 1 for r in paired),
            'quarantine_flags': dict(Counter(reason for f in latest for reason in f['flags'] + [r for k in f['keepers'] for r in k['flags']])),
            'unresolved': unresolved, 'requests': dict(requests_used), 'request_receipts': receipts,
            'considered_this_run': considered, 'latest_fixture_kickoff': max((f['kickoff'] for f in latest), default=None),
            'status': 'attention_required' if unresolved else ('quarantines_present' if any(f['status'] != 'agreement' for f in latest) else 'agreement'),
            'limitations': ['No independent ground truth established by source agreement.',
                            'GOAL minutes diagnostic only; ESPN shotsFaced rejected; claims/xG unavailable.',
                            'No forecasts, stakes, alerts, historical settlements or model inputs modified.']}


def run(root, config, replay=None, output=None, max_matches=None, fixture_ids=None):
    dest = output or root / DEST
    now = datetime.now(timezone.utc)
    stamp = now.isoformat()
    archive = read(dest / 'comparisons.json.gz', {'schema_version': 1, 'fixtures': {}})
    state = read(dest / 'state.json', {})
    history = read(root / 'data/aerial/keeper-history.json.gz', {'fixtures': {}})
    refs = {str(k): v[-1] for k, v in history['fixtures'].items() if v}
    client = Client(os.environ.get('GOAL_API_KEY', '').strip(), config['max_goal_requests'], config['max_espn_requests'])
    if replay:
        fixtures = read(replay / 'cohort.json')['fixtures']
        packet = read(replay / 'goal-capture.json')
        stats = {str(r['fm_id']): r for r in packet['statistics']}
        calendar = {r['id']: r for p in packet['pages'] for r in p['response']['data']}
        ids = [str(f['id']) for f in fixtures]
        # Preserve native keeper-history event conflicts, even in the replay.
        for f in fixtures:
            if str(f['id']) not in refs:
                raise ValueError('replay_reference_missing:' + str(f['id']))
            refs[str(f['id'])] = dict(refs[str(f['id'])], home=f['home'], away=f['away'])
    else:
        cutoff = now - timedelta(days=config['days_back'])
        ids = [mid for mid, r in refs.items() if str(r['league_id']) in config['leagues'] and cutoff <= instant(r['kickoff']) <= now - timedelta(hours=2)]
        # Unchecked fixtures first; successful old checks wait for a source revision.
        ids = [mid for mid in ids if state.get(mid, {}).get('reference_hash') != refs[mid]['source_sha256'] or
               state.get(mid, {}).get('status') != 'agreement' or instant(refs[mid]['kickoff']) > now-timedelta(days=2)]
        ids.sort(key=lambda mid: (state.get(mid, {}).get('checked_at', ''), refs[mid]['kickoff']))
    if fixture_ids:
        ids = [str(mid) for mid in fixture_ids]
        if any(mid not in refs or str(refs[mid]['league_id']) not in config['leagues'] for mid in ids):
            raise ValueError('requested_reference_fixture_unavailable')
    if not replay:
        for mid in ids:
            state.setdefault(mid, {'status': 'queued', 'checked_at': '', 'reference_hash': refs[mid]['source_sha256']})
        ids = ids[:max_matches or config['max_matches']]
    failures = 0
    for mid in ids:
        ref = refs[mid]
        try:
            if replay:
                row = stats[mid]
                gf, gs = calendar[row['goal_id']], row['response']
                ep = read(replay / 'espn' / (mid + '.json'))
                observed = row['observed_at']
            else:
                gf = find_goal(client, ref, config, (now-timedelta(days=config['days_back'])).date().isoformat(), now.date().isoformat())
                gs = client.get('goal', f'/fixtures/{gf["id"]}/statistics')
                ep = find_espn(client, ref, config)
                observed = datetime.now(timezone.utc).isoformat()
            record = compare(root, ref, gf, gs, ep, config, observed)
            record['cohort'] = 'installation_replay' if replay else ('forward_collection' if instant(ref['kickoff']) >= instant(config['activated_at']) else 'historical_backfill')
            append_record(archive, record)
            status = record['status']
        except (ValueError, KeyError, TypeError, RuntimeError) as error:
            # Never expose HTTP bodies, headers or credentials in health/logs.
            status = 'budget_deferred' if isinstance(error, BudgetError) else 'source_or_identity_error'
            reason = str(error) if isinstance(error, (ValueError, RuntimeError)) else type(error).__name__
            failures += not isinstance(error, BudgetError)
            state[mid] = {'status': status, 'reason': reason, 'checked_at': stamp, 'reference_hash': ref['source_sha256']}
            if isinstance(error, BudgetError):
                break
            continue
        state[mid] = {'status': status, 'checked_at': stamp, 'reference_hash': ref['source_sha256']}
    summary = report(archive, state, config, stamp, client.used, client.receipts, len(ids))
    write(dest / 'comparisons.json.gz', archive)
    write(dest / 'state.json', state)
    write(dest / 'status.json', summary)
    print(json.dumps({k: summary[k] for k in ('status', 'fixtures', 'keepers', 'paired_saves', 'saves_all_three_equal', 'fixture_status', 'requests', 'cohorts')}))
    return 2 if failures else 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--replay', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--max-matches', type=int)
    parser.add_argument('--fixture', action='append', help='Bounded explicit validation cohort; no effect on the daily default')
    args = parser.parse_args()
    raise SystemExit(run(args.root, read(args.root / 'config/keeper-feed-comparison.json'), args.replay, args.output, args.max_matches, args.fixture))
