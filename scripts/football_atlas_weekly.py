"""Cloud-only, weekly Pinnacle archive ingestion and validated Atlas publication.

OddsPapi supplies historical 1X2 state; Goaloo independently supplies finished
league results. Existing published prices/results are immutable. No PC capture.
"""
import argparse
import copy
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time

import requests
import football_atlas_update as legacy

ROOT = Path(__file__).resolve().parents[1]
UTC = timezone.utc
BRANCH = 'codex/fair-odds-daily-pitch-20260908'
TOURNAMENTS = {'premier-league': 17, 'serie-a': 23, 'la-liga': 8, 'bundesliga': 35, 'ligue-1': 34}
FORWARD_START = datetime(2026, 9, 21, tzinfo=UTC)
MANIFEST = Path('src/data/football-atlas-release.json')


class RateLimited(RuntimeError):
    def __init__(self, retry_after):
        super().__init__('OddsPapi endpoint cooldown')
        self.retry_after = retry_after


def fetch_json(url, params=None):
    # Exception URLs may include credentials. Never surface requests' raw errors.
    try:
        response = requests.get(url, params=params, timeout=60,
                                headers={'User-Agent': 'IlMargine-Atlas/1.0'})
        if response.status_code == 404 and url.endswith('/fixtures'):
            if response.json().get('error', {}).get('code') == 'FIXTURE_NOT_FOUND':
                return []
        if response.status_code == 429:
            data = json.loads(response.content.decode('utf-8-sig'))
            error = data.get('error', data)
            if isinstance(error, dict) and error.get('code') == 'REQUEST_LIMIT_EXCEEDED':
                raise RuntimeError('OddsPapi monthly request allowance exhausted')
            wait = response.headers.get('Retry-After', '6')
            delay = float(wait) if str(wait).replace('.', '', 1).isdigit() else 6
            if delay > 60:
                raise RuntimeError('OddsPapi requests a longer pause; retry the job later')
            raise RateLimited(max(6, delay))
        if response.status_code != 200:
            raise RuntimeError(f'{url.split("?")[0]} returned HTTP {response.status_code}')
        return json.loads(response.content.decode('utf-8-sig'))
    except requests.RequestException:
        raise RuntimeError(f'{url.split("?")[0]} request failed (credentials withheld)') from None
    except ValueError:
        raise RuntimeError(f'{url.split("?")[0]} returned invalid JSON') from None


class OddsPapi:
    def __init__(self, key):
        if not key:
            raise ValueError('ODDSPAPI_API_KEY is missing')
        self.key, self.last, self.calls = key, {}, {}

    def get(self, endpoint, **params):
        cooldown = 5.2 if endpoint == 'historical-odds' else 3.0
        for attempt in range(3):
            time.sleep(max(0, cooldown - (time.monotonic() - self.last.get(endpoint, 0))))
            self.calls[endpoint] = self.calls.get(endpoint, 0) + 1
            try:
                return fetch_json('https://api.oddspapi.io/v4/' + endpoint, {'apiKey': self.key, **params})
            except RateLimited as exc:
                if attempt == 2:
                    raise RuntimeError('OddsPapi rate limit persisted after bounded retries') from None
                time.sleep(exc.retry_after * (attempt + 1))
            finally:
                # Provider cooldown starts when processing finishes, not request start.
                self.last[endpoint] = time.monotonic()

    def quota(self):
        def balances(value):
            if isinstance(value, dict):
                if 'request_limit' in value and 'request_count' in value:
                    yield int(value['request_limit']) - int(value['request_count'])
                for child in value.values():
                    yield from balances(child)
            elif isinstance(value, list):
                for child in value:
                    yield from balances(child)
        remaining = list(balances(self.get('account')))
        if not remaining or max(remaining) < 20:
            raise ValueError('OddsPapi quota unavailable or below 20-request safety reserve')
        return max(remaining)


def canonical(league, names, aliases, teams):
    known = {legacy.normal(n): n for n in teams}
    matches = {aliases.get(league, {}).get(legacy.normal(n)) or known.get(legacy.normal(n))
               for n in names if n}
    matches.discard(None)
    if len(matches) != 1:
        raise ValueError(f'Unreviewed or conflicting {league} club name: {names}')
    return matches.pop()


def fixture_key(f):
    return (f['league'], f['home'], f['away'], legacy.dt(f['kickoff']).date().isoformat())


def stored_keys(index):
    pairs = {(index['leagues'][r[2]], index['teams'][r[4]], index['teams'][r[5]], r[1]): r for r in index['fixtures']}
    if len(pairs) != len(index['fixtures']):
        raise ValueError('Duplicate existing fixture identity')
    return pairs


def match_fixture(p, league, calendar, aliases, old):
    if p.get('tournamentId') != TOURNAMENTS[league] or p.get('sportId') != 10:
        raise ValueError('Unexpected sport/tournament in fixture response')
    home = canonical(league, [p.get('participant1Name'), p.get('participant1ShortName')], aliases, old['teams'])
    away = canonical(league, [p.get('participant2Name'), p.get('participant2ShortName')], aliases, old['teams'])
    scheduled = legacy.dt(p['startTime'])
    candidates = [f for f in calendar if f['league'] == league and f['home'] == home and f['away'] == away
                  and abs(legacy.dt(f['kickoff']) - scheduled) <= timedelta(minutes=5)]
    if len(candidates) != 1:
        raise ValueError(f'Calendar identity/kickoff mismatch: {p["fixtureId"]} {home} / {away}')
    f = candidates[0]
    if f['status'] != -1 or not f['score'] or not all(type(n) is int and 0 <= n <= 30 for n in f['score']):
        raise ValueError(f'Unconfirmed regulation-time result: {p["fixtureId"]}')
    actual = legacy.dt(p['trueStartTime']) if p.get('trueStartTime') else scheduled
    if abs(actual - scheduled) > timedelta(minutes=15):
        raise ValueError(f'Delayed/rescheduled fixture needs timing review: {p["fixtureId"]}')
    return f, min(scheduled, actual, legacy.dt(f['kickoff']))


def prices_at_cutoff(outcomes, cutoff):
    quotes, provenance = [], []
    for oid in ('101', '102', '103'):
        rows = outcomes.get(oid, {}).get('players', {}).get('0', [])
        before = [r for r in rows if legacy.dt(r['createdAt']) < cutoff]
        if not before:
            raise ValueError('Missing pre-match outcome history')
        last_at = max(legacy.dt(r['createdAt']) for r in before)
        latest = [r for r in before if legacy.dt(r['createdAt']) == last_at]
        if len({(r.get('price'), r.get('active')) for r in latest}) != 1:
            raise ValueError('Conflicting outcome states at the same timestamp')
        q = latest[0]
        if q.get('active') is not True:
            raise ValueError('Outcome suspended at pre-match cutoff; no stale carry-forward')
        price = q.get('price')
        if type(price) not in (float, int) or not math.isfinite(price) or not 1 < price < 1001:
            raise ValueError('Invalid decimal price')
        quotes.append(price)
        provenance.append({'outcome': oid, 'price': price, 'lastChangedAt': q['createdAt']})
    if not .99 <= sum(1 / p for p in quotes) <= 1.18:
        raise ValueError('Implausible three-way overround')
    return quotes, provenance


def merge_archive(old, additions):
    new = copy.deepcopy(old)
    keys = stored_keys(old)
    if len(additions) > 180:
        raise ValueError('More than 180 new matches; review backfill')
    for f, odds, source_id in additions:
        key = fixture_key(f)
        if key in keys:
            raise ValueError('Duplicate addition or attempted replacement')
        keys[key] = True
        if f['season'] not in new['seasons']:
            new['seasons'].append(f['season'])
        if any(n not in new['teams'] for n in (f['home'], f['away'])):
            raise ValueError('New club requires name/crest review')
        new['fixtures'].append(['papi-' + source_id, key[3], new['leagues'].index(f['league']),
                                new['seasons'].index(f['season']), new['teams'].index(f['home']),
                                new['teams'].index(f['away']), *f['score'], *odds, 2])
    new['fixtures'].sort(key=lambda r: (r[1], r[0]))
    if len({r[0] for r in new['fixtures']}) != len(new['fixtures']):
        raise ValueError('Duplicate fixture ID')
    return new


def collect(old, manifest, state, now, api):
    aliases = legacy.read(ROOT / 'scripts/config/football-atlas-clubs.json')
    config = {'stateDirectory': str(state), 'aliases': str(ROOT / 'scripts/config/football-atlas-clubs.json')}
    # Calendar parser validates the season, all club names and completion status.
    def calendar_fetch(url):
        for attempt in range(3):
            try:
                return fetch_json(url)
            except RuntimeError:
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)
    fixtures = legacy.calendar(config, now, force=True, fetcher=calendar_fetch)
    end = now - timedelta(hours=6)
    start = max(FORWARD_START - timedelta(days=7), min(now - timedelta(days=14), legacy.dt(manifest['through'] + 'T00:00:00Z')))
    if end - start > timedelta(days=35):
        raise ValueError('Archive is over 35 days behind; review catch-up before spending quota')
    expected = {fixture_key(f): f for f in fixtures if start <= legacy.dt(f['kickoff']) < end and f['status'] == -1}
    keys = stored_keys(old)
    for key, f in expected.items():
        if key in keys and keys[key][6:8] != f['score']:
            raise ValueError(f'Published score correction requires review: {key}')
    additions, seen, provenance, counts = [], set(), [], {}
    remaining = api.quota()
    history_dir = state / 'history'
    history_dir.mkdir(exist_ok=True)
    for league, tid in TOURNAMENTS.items():
        rows = api.get('fixtures', tournamentId=tid, **{'from': start.isoformat(), 'to': end.isoformat()})
        if not isinstance(rows, list) or len(rows) > 200:
            raise ValueError(f'Invalid fixture response for {league}')
        legacy.write(state / f'fixtures-{tid}.json', rows)
        counts[league] = {'completed': 0, 'new': 0}
        ids = set()
        for p in rows:
            if p['fixtureId'] in ids:
                raise ValueError('Duplicate provider fixture')
            ids.add(p['fixtureId'])
            if p.get('statusId') != 2:
                continue
            f, cutoff = match_fixture(p, league, fixtures, aliases, old)
            if not start <= legacy.dt(f['kickoff']) < end:
                raise ValueError('Fixture outside requested window')
            key = fixture_key(f)
            if key in seen:
                raise ValueError('Provider returned duplicate match identities')
            seen.add(key)
            counts[league]['completed'] += 1
            if key in keys or cutoff < FORWARD_START:
                continue
            if not re.fullmatch(r'id\d+', p['fixtureId']):
                raise ValueError('Unexpected fixture ID format')
            cache = history_dir / (p['fixtureId'] + '.json.gz')
            signature = [p['startTime'], p.get('trueStartTime'), p.get('updatedAt')]
            h = json.loads(gzip.decompress(cache.read_bytes())) if cache.exists() else {}
            if h.get('signature') != signature:
                raw = api.get('historical-odds', fixtureId=p['fixtureId'], bookmakers='pinnacle')
                if raw.get('fixtureId') != p['fixtureId']:
                    raise ValueError('Historical odds fixture mismatch')
                outcomes = raw.get('bookmakers', {}).get('pinnacle', {}).get('markets', {}).get('101', {}).get('outcomes', {})
                h = {'signature': signature, 'fixtureId': p['fixtureId'], 'bookmaker': 'pinnacle', 'market': 101,
                     'outcomes': outcomes, 'downloadedAt': now.isoformat(),
                     'responseSha256': hashlib.sha256(json.dumps(raw, sort_keys=True).encode()).hexdigest()}
                cache.write_bytes(gzip.compress(json.dumps(h).encode()))
            odds, detail = prices_at_cutoff(h['outcomes'], cutoff)
            additions.append((f, odds, p['fixtureId']))
            counts[league]['new'] += 1
            provenance.append({'fixtureId': p['fixtureId'], 'resultId': f['id'], 'home': f['home'], 'away': f['away'],
                               'score': f['score'], 'cutoff': cutoff.isoformat(), 'prices': detail,
                               'responseSha256': h['responseSha256'], 'basis': 'last-pre-match'})
        print(f'{league}: {counts[league]}', flush=True)
    if set(expected) != seen:
        raise ValueError(f'Incomplete fixture reconciliation: {len(set(expected)-seen)} missing, {len(seen-set(expected))} unexpected')
    new = merge_archive(old, additions)
    report = {'checkedAt': now.isoformat(), 'windowFrom': start.isoformat(), 'windowTo': end.isoformat(),
              'newMatches': len(additions), 'leagues': counts, 'quotaBefore': remaining,
              'calls': api.calls, 'status': 'validated', 'provenance': provenance}
    legacy.write(state / 'collection.json', report)
    return new, report


def write_release(old_manifest, index, now):
    payload = json.dumps(index, ensure_ascii=False, separators=(',', ':')).encode()
    version = hashlib.sha256(payload).hexdigest()[:12]
    path = ROOT / 'public/football-atlas' / f'index-{version}.json'
    path.write_bytes(payload)
    priced = [r for r in index['fixtures'] if all(type(p) in (int, float) and math.isfinite(p) and 1 < p < 1001 for p in r[8:11])]
    release = {**old_manifest, 'version': version, 'indexUrl': '/football-atlas/' + path.name,
               'checkedAt': now.isoformat(), 'through': max(r[1] for r in priced), 'matches': len(priced),
               'fixtures': len(index['fixtures']), 'bytes': len(payload), 'seasons': index['seasons'], 'previewOnly': False}
    release['coverage'] = {league: {season: {'eligible': sum(r[2] == li and r[3] == si for r in index['fixtures']),
                                          'priced': sum(r[2] == li and r[3] == si for r in priced)}
                                  for si, season in enumerate(index['seasons'])}
                          for li, league in enumerate(index['leagues'])}
    legacy.write(ROOT / MANIFEST, release)
    return release, path.relative_to(ROOT)


def publish(state, manifest, report):
    helper = legacy.load_module('atlas_cloud_publish_helpers', ROOT / 'scripts/refresh-return-atlas.py')
    run = helper.run
    token = os.environ.get('VERCEL_TOKEN')
    if not token:
        raise ValueError('Project-scoped VERCEL_TOKEN is missing')
    # CLI token remains in the process only, never in an artifact or repository file.
    def authenticated_run(args, cwd=None, **kwargs):
        if Path(str(args[0])).name in ('vercel', 'vercel.cmd'):
            args = [args[0], '--token', token, *args[1:]]
        try:
            return run(args, cwd, **kwargs)
        except RuntimeError as exc:
            raise RuntimeError(str(exc).replace(token, '[redacted]')) from None
    helper.run = authenticated_run
    try:
        headers = {'Authorization': 'Bearer ' + token}
        alias_response = requests.get('https://api.vercel.com/v4/aliases/ilmargine.bet',
                                      params={'teamId': helper.TEAM}, headers=headers, timeout=30)
        alias_response.raise_for_status()
        live_response = requests.get('https://api.vercel.com/v13/deployments/' + alias_response.json()['deploymentId'],
                                     params={'teamId': helper.TEAM}, headers=headers, timeout=30)
        live_response.raise_for_status()
        live_sha = live_response.json().get('meta', {}).get('githubCommitSha')
        if not live_sha:
            raise ValueError('Cannot establish live release ancestry')
        run(['git', 'merge-base', '--is-ancestor', live_sha, 'HEAD'], ROOT)
    except requests.RequestException:
        raise RuntimeError('Cannot validate current Vercel release (credential details withheld)') from None
    config = {'checkout': str(ROOT), 'stateDirectory': str(state)}
    legacy.publish(config, helper, manifest['version'], Path('public') / manifest['indexUrl'].lstrip('/'), report)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--state-directory', type=Path, required=True)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--publish', action='store_true')
    mode.add_argument('--dry-run', action='store_true')
    args = p.parse_args()
    state = args.state_directory.resolve()
    state.mkdir(parents=True, exist_ok=True)
    report = {'status': 'started', 'checkedAt': datetime.now(UTC).isoformat()}
    try:
        if args.publish and not os.environ.get('VERCEL_TOKEN'):
            raise ValueError('Project-scoped VERCEL_TOKEN is required before publication starts')
        manifest = legacy.read(ROOT / MANIFEST)
        old = legacy.read(ROOT / 'public' / manifest['indexUrl'].lstrip('/'))
        new, report = collect(old, manifest, state, datetime.now(UTC), OddsPapi(os.environ.get('ODDSPAPI_API_KEY')))
        if not args.publish:
            report['status'] = 'dry-run-passed'
        else:
            helper = legacy.load_module('atlas_commit_helpers', ROOT / 'scripts/refresh-return-atlas.py')
            run = helper.run
            dirty = run(['git', 'status', '--porcelain'], ROOT).strip()
            if dirty:
                raise ValueError('Publication checkout dirty: ' + dirty[:1000])
            if run(['git', 'ls-remote', 'origin', 'refs/heads/' + BRANCH], ROOT).split()[0] != run(['git', 'rev-parse', 'HEAD'], ROOT).strip():
                raise ValueError('Release branch advanced during collection; rerun against latest commit')
            live_html = helper.fetch('https://ilmargine.bet/football-atlas').decode()
            if report['newMatches']:
                previous = manifest['indexUrl']
                manifest, path = write_release(manifest, new, datetime.now(UTC))
                run(['node', '--experimental-strip-types', '--test', 'scripts/tests/football-atlas.test.mjs'], ROOT)
                live_paths = set(re.findall(r'/football-atlas/index-[a-f0-9]{12}\.json', live_html))
                if not live_paths:
                    raise ValueError('Cannot identify live archive for retention')
                keep = live_paths | {previous, manifest['indexUrl']}
                removed = []
                archive_root = (ROOT / 'public/football-atlas').resolve()
                for file in archive_root.glob('index-*.json'):
                    if re.fullmatch(r'index-[a-f0-9]{12}\.json', file.name) and '/football-atlas/' + file.name not in keep:
                        if file.resolve().parent != archive_root:
                            raise ValueError('Unsafe archive retention path')
                        relative = file.relative_to(ROOT).as_posix()
                        run(['git', 'rm', '--', relative], ROOT)
                        removed.append(relative)
                run(['git', 'add', '--', path, MANIFEST], ROOT)
                staged = set(run(['git', 'diff', '--cached', '--name-only'], ROOT).splitlines())
                if staged != {path.as_posix(), MANIFEST.as_posix(), *removed}:
                    raise ValueError('Unexpected staged files')
                run(['git', 'commit', '-m', f'data: update Football Atlas through {manifest["through"]}'], ROOT)
                run(['git', 'push', 'origin', 'HEAD:' + BRANCH], ROOT)
            if report['newMatches'] or manifest['version'] not in live_html:
                publish(state, manifest, report)
            else:
                report['status'] = 'unchanged'
        legacy.write(state / 'publish-status.json', report)
        print(json.dumps({k: v for k, v in report.items() if k != 'provenance'}))
    except Exception as exc:
        message = f'Weekly update failed: {type(exc).__name__}: {str(exc)[:1500]}'
        for name in ('ODDSPAPI_API_KEY', 'VERCEL_TOKEN'):
            if os.environ.get(name):
                message = message.replace(os.environ[name], '[redacted]')
        legacy.write(state / 'publish-status.json', {**report, 'status': 'failed', 'error': message})
        print(message, file=sys.stderr)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
