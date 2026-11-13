"""Weekly Pinnacle-first archive ingestion with a validated bet365 fallback.

OddsPapi supplies historical 1X2 state; Goaloo independently supplies finished
league results. Existing published prices/results are immutable. No PC capture.
"""
import argparse
from collections import Counter
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
import football_atlas_holds as holds

ROOT = Path(__file__).resolve().parents[1]
UTC = timezone.utc
BRANCH = 'codex/fair-odds-daily-pitch-20260908'
TOURNAMENTS = {'premier-league': 17, 'serie-a': 23, 'la-liga': 8, 'bundesliga': 35, 'ligue-1': 34}
FORWARD_START = datetime(2026, 9, 21, tzinfo=UTC)
MANIFEST = Path('src/data/football-atlas-release.json')
BOOKMAKERS = ('pinnacle', 'bet365')
PRICE_BASES = {'pinnacle': ('last-pre-match', 2), 'bet365': ('bet365-last-pre-match', 3)}


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
        raise holds.Hold('club-name-unreviewed', f'Unreviewed or conflicting {league} club name: {names}')
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
        raise holds.Hold('provider-row-out-of-scope', 'Unexpected sport/tournament in fixture response')
    home = canonical(league, [p.get('participant1Name'), p.get('participant1ShortName')], aliases, old['teams'])
    away = canonical(league, [p.get('participant2Name'), p.get('participant2ShortName')], aliases, old['teams'])
    scheduled = legacy.dt(p['startTime'])
    actual = legacy.dt(p['trueStartTime']) if p.get('trueStartTime') else scheduled
    if abs(actual - scheduled) > timedelta(minutes=15):
        raise holds.Hold('kickoff-timing-review', f'Delayed/rescheduled fixture needs timing review: {p["fixtureId"]}')
    # Results calendars may record the delayed start rather than the original
    # schedule. Require the provider's actual-start evidence and keep the same
    # bounded delay guard; never move the price cutoff forward with the delay.
    def timing_matches(f):
        kickoff = legacy.dt(f['kickoff'])
        return (abs(kickoff - scheduled) <= timedelta(minutes=5)
                or (bool(p.get('trueStartTime'))
                    and abs(kickoff - scheduled) <= timedelta(minutes=15)
                    and abs(kickoff - actual) <= timedelta(minutes=5)))
    candidates = [f for f in calendar if f['league'] == league and f['home'] == home and f['away'] == away
                  and timing_matches(f)]
    if len(candidates) != 1:
        raise holds.Hold('calendar-mismatch', f'Calendar identity/kickoff mismatch: {p["fixtureId"]} {home} / {away}')
    f = candidates[0]
    if f['status'] != -1 or not f['score'] or not all(type(n) is int and 0 <= n <= 30 for n in f['score']):
        raise holds.Hold('result-unconfirmed', f'Unconfirmed regulation-time result: {p["fixtureId"]}')
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


def select_market(histories, cutoff):
    """Use one complete bookmaker market. A fallback never repairs individual legs."""
    rejected = {}
    for bookmaker in BOOKMAKERS:
        try:
            odds, detail = prices_at_cutoff(histories.get(bookmaker, {}), cutoff)
        except (ValueError, KeyError, TypeError) as exc:
            rejected[bookmaker] = str(exc) if isinstance(exc, ValueError) else 'Malformed outcome history'
            continue
        basis, code = PRICE_BASES[bookmaker]
        return {'bookmaker': bookmaker, 'basis': basis, 'code': code,
                'odds': odds, 'prices': detail, 'rejected': rejected}
    raise holds.Hold('price-not-validated',
                     'No validated pre-match market: ' + '; '.join(f'{b}: {r}' for b, r in rejected.items()))


def historical_market(api, fixture, cutoff, history_dir, now):
    """Reuse validated cache; fetch both books in one request when history is needed."""
    cache = history_dir / (fixture['fixtureId'] + '.json.gz')
    signature = [fixture['startTime'], fixture.get('trueStartTime'), fixture.get('updatedAt')]
    saved = json.loads(gzip.decompress(cache.read_bytes())) if cache.exists() else {}
    if saved.get('signature') == signature and saved.get('fixtureId') == fixture['fixtureId']:
        # Keep the existing Pinnacle-only cache useful; upgrade it only if unusable.
        histories = saved.get('histories') or {saved.get('bookmaker'): saved.get('outcomes', {})}
        try:
            return select_market(histories, cutoff), saved['responseSha256']
        except ValueError:
            if saved.get('requestedBookmakers') == list(BOOKMAKERS):
                raise
    raw = api.get('historical-odds', fixtureId=fixture['fixtureId'], bookmakers=','.join(BOOKMAKERS))
    if raw.get('fixtureId') != fixture['fixtureId']:
        raise holds.Hold('price-history-mismatch', 'Historical odds fixture mismatch')
    histories = {book: raw.get('bookmakers', {}).get(book, {}).get('markets', {}).get('101', {}).get('outcomes', {})
                 for book in BOOKMAKERS}
    saved = {'signature': signature, 'fixtureId': fixture['fixtureId'], 'market': 101,
             'requestedBookmakers': list(BOOKMAKERS), 'histories': histories, 'downloadedAt': now.isoformat(),
             'responseSha256': hashlib.sha256(json.dumps(raw, sort_keys=True).encode()).hexdigest()}
    selected = select_market(histories, cutoff)
    # Failed/partial responses are not cached as a successful collection.
    cache.write_bytes(gzip.compress(json.dumps(saved).encode()))
    return selected, saved['responseSha256']


def merge_archive(old, additions):
    new = copy.deepcopy(old)
    keys = stored_keys(old)
    if len(additions) > 180:
        raise ValueError('More than 180 new matches; review backfill')
    for f, odds, source_id, basis_code in additions:
        if basis_code not in (2, 3):
            raise ValueError('Unsupported weekly price basis')
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
                                new['teams'].index(f['away']), *f['score'], *odds, basis_code])
    new['fixtures'].sort(key=lambda r: (r[1], r[0]))
    if len({r[0] for r in new['fixtures']}) != len(new['fixtures']):
        raise ValueError('Duplicate fixture ID')
    return new


def collect(old, manifest, state, now, api):
    """Collect one week. A problem with one fixture is a hold, not a failure.

    Still fatal, exactly as before: an unusable results calendar, a duplicate
    identity in the stored archive, quota unavailable at the start, missing
    credentials, more than 180 additions, and any addition that would replace
    or duplicate a stored row. New and fatal: no league feed available at all.
    """
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
    base = max(FORWARD_START - timedelta(days=7), min(now - timedelta(days=14), legacy.dt(manifest['through'] + 'T00:00:00Z')))
    if end - base > timedelta(days=35):
        raise ValueError('Archive is over 35 days behind; review catch-up before spending quota')
    keys = stored_keys(old)
    ledger = holds.Ledger.load(state, manifest.get('historyHolds'), keys, now)
    # The window follows the oldest hold inside 35 days. Older holds are aged,
    # kept for review, and never widen the window or trip the stop above.
    start = ledger.window_start(base, end, now)
    expected = {fixture_key(f): f for f in fixtures if start <= legacy.dt(f['kickoff']) < end and f['status'] == -1}
    run = holds.Run(expected, keys, TOURNAMENTS, start, end,
                    secrets=(getattr(api, 'key', None), os.environ.get('ODDSPAPI_API_KEY')))
    for key, f in expected.items():
        if key in keys and keys[key][6:8] != f['score']:
            # A public number may be wrong. Report it first; never rewrite the stored row.
            run.review(key, f, 'published-score-conflict',
                       f'Published score {keys[key][6:8]} differs from the results calendar {f["score"]}; stored row left unchanged')
    additions, seen, provenance, counts = [], set(), [], {}
    remaining = api.quota()
    meter = holds.Meter(api, remaining)
    history_dir = state / 'history'
    history_dir.mkdir(exist_ok=True)
    for league, tid in TOURNAMENTS.items():
        counts[league] = {'completed': 0, 'new': 0}
        if meter.out_of_quota():
            run.feed(league, 'not-requested', 'quota-deferred', 'Request allowance exhausted before this league feed was requested')
            continue
        try:
            rows = meter.get('fixtures', tournamentId=tid, **{'from': start.isoformat(), 'to': end.isoformat()})
        except RuntimeError as exc:
            run.feed(league, 'unavailable', 'quota-deferred' if meter.exhausted else 'league-source-unavailable',
                     f'League fixture feed request failed: {exc}')
            continue
        if (not isinstance(rows, list) or len(rows) > 200
                or not all(isinstance(p, dict) and isinstance(p.get('fixtureId'), str) and p['fixtureId'] for p in rows)):
            run.feed(league, 'invalid', 'league-source-unavailable', f'Invalid fixture response for {league}')
            continue
        legacy.write(state / f'fixtures-{tid}.json', rows)
        run.feed(league, 'ok', rows=len(rows))
        repeated = {pid: n for pid, n in Counter(p['fixtureId'] for p in rows).items() if n > 1}
        for pid, n in repeated.items():
            run.hold_row(league, next(p for p in rows if p['fixtureId'] == pid), 'provider-duplicate',
                         f'Provider returned fixture ID {pid} {n} times', count=n)
        matched = []
        for p in rows:
            pid = p['fixtureId']
            if pid in repeated:
                continue
            if p.get('statusId') != 2:
                run.row(league, 'notCompleted', pid)
                continue
            try:
                f, cutoff = match_fixture(p, league, fixtures, aliases, old)
            except holds.Hold as exc:
                run.hold_row(league, p, exc.code, str(exc))
                continue
            except (ValueError, KeyError, TypeError, AttributeError) as exc:
                run.hold_row(league, p, 'provider-row-malformed', f'{type(exc).__name__}: {exc}')
                continue
            if not start <= legacy.dt(f['kickoff']) < end:
                run.hold_row(league, p, 'provider-row-outside-window', 'Fixture outside requested window')
                continue
            matched.append((p, f, cutoff, fixture_key(f)))
        shared = {key: [p['fixtureId'] for p, _, _, k in matched if k == key]
                  for key, n in Counter(k for *_, k in matched).items() if n > 1}
        for key, pids in shared.items():
            # Two provider rows for one fixture: hold both, never choose.
            seen.add(key)
            if key in keys:
                run.anomalies.append({'league': league, 'issue': 'Duplicate provider rows for an already published fixture',
                                      'providerFixtureIds': sorted(pids)})
            else:
                run.hold_fixture(key, expected.get(key), 'provider-duplicate',
                                 'Provider returned duplicate match identities: ' + ', '.join(sorted(pids)), pids)
            for pid in pids:
                run.row(league, 'published' if key in keys else 'held', pid)
        for p, f, cutoff, key in matched:
            pid = p['fixtureId']
            if key in shared:
                continue
            seen.add(key)
            counts[league]['completed'] += 1
            if key in keys:
                run.row(league, 'published', pid)
                continue
            if key not in expected:
                run.hold_row(league, p, 'provider-unexpected', 'Provider fixture is not in the expected calendar set')
                continue
            if cutoff < FORWARD_START:
                run.skipped.add(key)
                run.row(league, 'beforeForwardStart', pid)
                continue
            signature = [p.get('startTime'), p.get('trueStartTime'), p.get('updatedAt')]
            verdict = None  # (code, reason, carried) when this fixture is held
            if not re.fullmatch(r'id\d+', pid):
                verdict = ('provider-id-format', 'Unexpected fixture ID format', None)
            elif any(n not in old['teams'] for n in (f['home'], f['away'])):
                verdict = ('club-new-needs-review', 'New club requires name/crest review', None)
            else:
                prior = ledger.terminal(key, pid, signature)
                if prior:
                    # Historical prices do not change. Do not spend a request on the same answer.
                    verdict = (prior['code'], prior['reason'], 'terminal')
                else:
                    try:
                        selected, response_hash = historical_market(meter.price_gate(), p, cutoff, history_dir, now)
                    except holds.Hold as exc:
                        verdict = (exc.code, str(exc), None)
                    except RuntimeError as exc:
                        verdict = ('quota-deferred' if meter.exhausted else 'price-source-unavailable', str(exc), None)
                    except (ValueError, KeyError, TypeError, AttributeError, OSError, EOFError) as exc:
                        verdict = ('price-response-malformed', f'{type(exc).__name__}: {exc}', None)
            if verdict:
                run.hold_fixture(key, f, verdict[0], verdict[1], [pid], signature, carried=verdict[2])
                run.row(league, 'held', pid)
                continue
            run.row(league, 'added', pid)
            run.add(key, pid)
            additions.append((f, selected['odds'], p['fixtureId'], selected['code']))
            counts[league]['new'] += 1
            provenance.append({'fixtureId': p['fixtureId'], 'resultId': f['id'], 'home': f['home'], 'away': f['away'],
                               'scheduledKickoff': p['startTime'], 'actualKickoff': p.get('trueStartTime'),
                               'calendarKickoff': f['kickoff'],
                               'score': f['score'], 'cutoff': cutoff.isoformat(), 'prices': selected['prices'],
                               'responseSha256': response_hash, 'basis': selected['basis'],
                               'bookmaker': selected['bookmaker'], 'fallbackReasons': selected['rejected']})
        print(f'{league}: {counts[league]}', flush=True)
    if not any(feed['feed'] == 'ok' for feed in run.feeds.values()):
        # Not a fixture problem: the source gave nothing. Ledger and archive stay as they were.
        failure = {'checkedAt': now.isoformat(), 'status': 'failed', 'leagues': run.feeds}
        legacy.write(state / 'collection.json', failure)
        raise ValueError('No league fixture feed was available; nothing collected and holds left unchanged')
    waiting = {key[0] for key in expected if key not in keys and not ledger.known(key)}
    if not seen and len(waiting) >= 2:
        # Rows may have arrived, but not one matched the calendar in any league while
        # two or more leagues have new results waiting. That is a source or calendar
        # failure, not a fixture problem: stay loud, change nothing. Fixtures already
        # held from an earlier run never trigger this.
        failure = {'checkedAt': now.isoformat(), 'status': 'failed', 'leagues': run.feeds,
                   'leaguesWaiting': sorted(waiting)}
        legacy.write(state / 'collection.json', failure)
        raise ValueError(f'No provider fixture matched the results calendar in any league ({len(waiting)} leagues waiting); '
                         'nothing collected and holds left unchanged')
    # A provider can stop listing an older fixture already validated and stored;
    # that never blocks. An unpublished fixture the provider did not return is
    # held for that fixture only, and everything else proceeds.
    run.settle_unseen(ledger)
    accounting = run.accounting()
    # Integrity checks on the additions are unchanged and still fatal.
    new = merge_archive(old, additions)
    ledger.apply(run, now)
    ledger.save(now)
    for league in TOURNAMENTS:
        counts[league]['held'] = sum(key[0] == league for key in run.fixture_holds)
    missing = set(expected) - seen
    held_keys = sorted(run.fixture_holds, key=lambda k: (k[3], k))
    reconciliation = {'checkedAt': now.isoformat(), 'status': 'held' if run.fixture_holds or run.row_holds else 'validated',
                      'missing': [{'fixture': expected[k], 'alreadyPublished': k in keys} for k in sorted(missing)],
                      'unexpected': [],
                      'held': [{'fixture': list(k), 'code': run.fixture_holds[k]['code']} for k in held_keys]}
    legacy.write(state / 'reconciliation.json', reconciliation)
    public = ledger.public()
    report = {'reviewItems': [{'fixture': list(k), **{n: h[n] for n in ('code', 'reason', 'calendarId')}}
                              for k, h in sorted(run.reviews.items(), key=lambda item: (item[0][3], item[0]))],
              'checkedAt': now.isoformat(), 'windowFrom': start.isoformat(), 'windowTo': end.isoformat(),
              'newMatches': len(additions), 'leagues': counts, 'quotaBefore': remaining,
              'calls': api.calls, 'status': 'validated', 'provenance': provenance,
              'priceSources': {book: sum(p['bookmaker'] == book for p in provenance) for book in BOOKMAKERS},
              'holdStatus': ledger.status(), 'windowBase': base.isoformat(), 'windowFollowsHold': start < base,
              'holds': ledger.report(run), 'accounting': accounting,
              'quota': {'before': remaining, 'requestsThisRun': meter.spent(), 'exhausted': meter.exhausted,
                        'deferred': sum(h['code'] == 'quota-deferred' for h in run.fixture_holds.values())},
              'publicHolds': public,
              'publicHoldsChanged': not holds.same_public(manifest.get('historyHolds'), public)}
    legacy.write(state / 'collection.json', report)
    return new, report


def write_release(old_manifest, index, now, holds_public=None):
    """holds_public=None keeps the manifest exactly as before this change.

    A dict (possibly empty) states the current public held list: empty removes
    any earlier hold metadata, non-empty replaces it. The archive bytes and
    version never depend on it.
    """
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
    if holds_public is not None:
        release.pop('historyHolds', None)
        if holds_public.get('held') or holds_public.get('review'):
            # Clubs, dates and counts only. Never a provider name, ID or reason.
            release['historyHolds'] = holds.with_complete_through(holds_public, release['through'])
    legacy.write(ROOT / MANIFEST, release)
    return release, path.relative_to(ROOT)


def publish(state, manifest, report):
    helper = legacy.load_module('atlas_cloud_publish_helpers', ROOT / 'scripts/refresh-return-atlas.py')
    run = helper.run
    token = os.environ.get('VERCEL_TOKEN')
    if not token:
        raise ValueError('Project-scoped VERCEL_TOKEN is missing')
    # The CLI reads VERCEL_TOKEN from its environment; never put it in argv.
    def authenticated_run(args, cwd=None, **kwargs):
        try:
            return run(args, cwd, **kwargs)
        except RuntimeError as exc:
            raise RuntimeError(str(exc).replace(token, '[redacted]')) from None
    helper.run = authenticated_run
    def project_scoped_api(route, body=None):
        # A project token legitimately has no personal /user identity. The CLI
        # --scope resolver asks for one before forwarding a valid API request.
        # Keep the existing exact team/project scope and avoid that user lookup.
        if not route.startswith('/') or route.startswith('//') or '://' in route:
            raise ValueError('Unexpected Vercel API route')
        try:
            response = requests.request('GET' if body is None else 'POST',
                'https://api.vercel.com' + route, params={'teamId': helper.TEAM},
                headers={'Authorization': 'Bearer ' + token}, json=body,
                timeout=60, allow_redirects=False)
        except requests.RequestException:
            raise RuntimeError('Project-scoped Vercel request failed; credential details withheld') from None
        if not 200 <= response.status_code < 300:
            raise RuntimeError(f'Project-scoped Vercel request HTTP {response.status_code}; live release retained')
        return response.json() if response.content else {}
    helper.project_scoped_api = project_scoped_api
    try:
        headers = {'Authorization': 'Bearer ' + token}
        alias_response = requests.get('https://api.vercel.com/v4/aliases/ilmargine.bet',
                                      params={'teamId': helper.TEAM}, headers=headers, timeout=30)
        alias_response.raise_for_status()
        live_response = requests.get('https://api.vercel.com/v13/deployments/' + alias_response.json()['deploymentId'],
                                     params={'teamId': helper.TEAM}, headers=headers, timeout=30)
        live_response.raise_for_status()
        live = live_response.json()
        helper.validate_deployment_identity(live, expected_id=alias_response.json()['deploymentId'])
        from atlas_production_release import stage_football
        release_root, release_branch, live_sha, release_sha = stage_football(ROOT, state, live, run)
        helper.check_static_budget(release_root)
        report.update(productionBaseSha=live_sha, releaseBranch=release_branch, releaseSha=release_sha)
    except requests.RequestException:
        raise RuntimeError('Cannot validate current Vercel release (credential details withheld)') from None
    config = {'checkout': str(release_root), 'stateDirectory': str(state),
              'releaseBranch': release_branch, 'expectedProductionId': alias_response.json()['deploymentId']}
    legacy.publish(config, helper, manifest['version'], Path('public') / manifest['indexUrl'].lstrip('/'), report)


def stage_release(run, root, changed_paths):
    """Include filesystem deletions and deletions already staged by retention."""
    tracked = set(run(['git', 'ls-files', '--', *sorted(changed_paths)], root).splitlines())
    to_stage = tracked | {path for path in changed_paths if (root / path).exists()}
    if to_stage:
        run(['git', 'add', '--all', '--', *sorted(to_stage)], root)
    # Content-addressed replacements often look like renames to Git. Count both
    # old and new paths explicitly so a legitimate deletion is not "missing".
    staged = set(run(['git', 'diff', '--cached', '--no-renames', '--name-only'], root).splitlines())
    # Writers return all their output paths, including byte-identical files.
    # Such files have no staged diff; only tracked, unchanged paths may be absent.
    unexpected = staged - changed_paths
    missing = changed_paths - staged - tracked
    remaining = set(run(['git', 'diff', '--no-renames', '--name-only', '--', *sorted(changed_paths)], root).splitlines())
    if unexpected or missing or remaining:
        raise ValueError(f'Unexpected staged files: extra={sorted(unexpected)}, missing={sorted(missing)}, unstaged={sorted(remaining)}')


def synchronize_release(run, root, report, *, base=None, changed_paths=()):
    """Carry unrelated presentation/news commits forward, never stale Atlas inputs.

    Before writers run the checkout must be clean and can only fast-forward.
    After writing, only the single scoped data commit may be replayed. Unknown
    paths, collection code, configuration and all Atlas inputs require a fresh run.
    """
    if run(['git', 'status', '--porcelain'], root).strip():
        raise ValueError('Release synchronization requires a clean checkout')
    head = run(['git', 'rev-parse', 'HEAD'], root).strip()
    base = base or head
    run(['git', 'fetch', '--no-tags', 'origin', 'refs/heads/' + BRANCH], root)
    remote = run(['git', 'rev-parse', 'FETCH_HEAD'], root).strip()
    if remote in (base, head):
        return remote
    run(['git', 'merge-base', '--is-ancestor', base, remote], root)
    upstream = set(run(['git', 'diff', '--no-renames', '--name-only', base, remote], root).splitlines())
    allowed_prefixes = ('src/app/', 'src/components/', 'src/lib/', 'src/styles/',
                        'data/penalty-news/', 'public/penalty-news/',
                        'src/data/penalty-news', 'scripts/tests/penalty-news')
    blocked = {path for path in upstream if not path.startswith(allowed_prefixes)}
    blocked.update(upstream.intersection(changed_paths))
    if blocked:
        raise ValueError('Release inputs changed; fresh validation required: ' + ', '.join(sorted(blocked)))
    if head == base:
        run(['git', 'merge', '--ff-only', remote], root)
    else:
        parents = run(['git', 'rev-list', '--parents', '-n', '1', head], root).split()
        local = set(run(['git', 'diff', '--no-renames', '--name-only', base, head], root).splitlines())
        if parents != [head, base] or not local or not local.issubset(set(changed_paths)):
            raise ValueError('Release synchronization requires one scoped Atlas commit')
        run(['git', 'rebase', '--onto', remote, base], root)
    report.setdefault('releaseSynchronizations', []).append({'from': base, 'onto': remote, 'paths': sorted(upstream)})
    return remote


def push_release(run, root, report, base, changed_paths):
    """Retry only verified non-overlapping branch advances; never force-push."""
    for attempt in range(3):
        base = synchronize_release(run, root, report, base=base, changed_paths=changed_paths)
        try:
            run(['git', 'push', 'origin', 'HEAD:' + BRANCH], root)
            return
        except RuntimeError:
            head = run(['git', 'rev-parse', 'HEAD'], root).strip()
            remote = run(['git', 'ls-remote', 'origin', 'refs/heads/' + BRANCH], root).split()[0]
            if remote == head:  # Server accepted the commit before a transport error.
                return
            if remote == base or attempt == 2:
                raise


def recover_fixture_board(state, manifest, report, *, dry_run=False):
    """A historical ingestion failure must not block a validated new schedule.

    This runs before archive writers: club/manager history stays byte-identical.
    The ordinary publisher still verifies ancestry, scope, deployment and alias.
    """
    import atlas_fixture_board
    if not dry_run:
        helper = legacy.load_module('atlas_board_recovery_helpers', ROOT / 'scripts/refresh-return-atlas.py')
        run = helper.run
        if run(['git', 'status', '--porcelain'], ROOT).strip():
            raise ValueError('Fixture recovery requires a clean production checkout')
        synchronize_release(run, ROOT, report)
        base = run(['git', 'rev-parse', 'HEAD'], ROOT).strip()
    board = atlas_fixture_board.refresh(state)
    report['fixtureBoard'] = board['report']
    if dry_run:
        report['fixtureRecovery'] = 'validated-dry-run'
        return
    if board['changed']:
        stage_release(run, ROOT, set(board['paths']))
        run(['git', 'commit', '-m', 'data: refresh Matchday while retaining validated Atlas history'], ROOT)
        push_release(run, ROOT, report, base, set(board['paths']))
    publish(state, manifest, report)
    report['fixtureRecovery'] = 'published'


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
        if args.publish:
            helper = legacy.load_module('atlas_commit_helpers', ROOT / 'scripts/refresh-return-atlas.py')
            run = helper.run
            dirty = run(['git', 'status', '--porcelain'], ROOT).strip()
            if dirty:
                raise ValueError('Publication checkout dirty before collection: ' + dirty[:1000])
        manifest = legacy.read(ROOT / MANIFEST)
        old = legacy.read(ROOT / 'public' / manifest['indexUrl'].lstrip('/'))
        try:
            new, report = collect(old, manifest, state, datetime.now(UTC), OddsPapi(os.environ.get('ODDSPAPI_API_KEY')))
        except Exception as archive_error:
            # Keep the historical failure visible, but restore the independently
            # verified upcoming board instead of leaving the entire site stale.
            try:
                recover_fixture_board(state, manifest, report, dry_run=not args.publish)
            except Exception as board_error:
                report['fixtureRecoveryError'] = str(board_error)[:1000]
            raise archive_error
        if not args.publish:
            # Validate managers against the current candidate prices without committing.
            import manager_atlas_weekly
            write_release(manifest,new,datetime.now(UTC),holds_public=report.get('publicHolds') or {})
            manager_result=manager_atlas_weekly.refresh_or_retain(state)
            report['managers']={'added':manager_result['added'],'version':manager_result['manifest']['version'],'pending':manager_result.get('pending',[]),'publicationState':manager_result.get('publicationState'),'error':manager_result.get('error')}
            import atlas_fixture_board
            report['fixtureBoard'] = atlas_fixture_board.refresh(state)['report']
            report['status'] = 'dry-run-passed'
        else:
            dirty = run(['git', 'status', '--porcelain'], ROOT).strip()
            if dirty:
                raise ValueError('Publication checkout dirty: ' + dirty[:1000])
            synchronize_release(run, ROOT, report)
            base = run(['git', 'rev-parse', 'HEAD'], ROOT).strip()
            live_html = helper.fetch('https://ilmargine.bet/football-atlas').decode()
            changed_paths=set()
            # A changed held list must reach the public manifest even in a week with no additions.
            if report['newMatches'] or report.get('publicHoldsChanged'):
                previous = manifest['indexUrl']
                manifest, path = write_release(manifest, new, datetime.now(UTC), holds_public=report.get('publicHolds') or {})
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
                changed_paths.update({path.as_posix(),MANIFEST.as_posix(),*removed})
            # One validated transaction and deployment for club and manager archives.
            import manager_atlas_weekly
            managers=manager_atlas_weekly.refresh_or_retain(state)
            report['managers']={'added':managers['added'],'version':managers['manifest']['version'],'pending':managers.get('pending',[]),'publicationState':managers.get('publicationState'),'error':managers.get('error')}
            manager_live_html=helper.fetch('https://ilmargine.bet/manager-atlas').decode()
            if managers['changed']:
                changed_paths.update(managers['paths'])
                live_manager_paths=set(re.findall(r'/manager-atlas/index-[a-f0-9]{12}\.json',manager_live_html))
                if not live_manager_paths:raise ValueError('Cannot identify live manager archive for retention')
                keep=live_manager_paths|{managers['previous'],managers['manifest']['indexUrl']}
                manager_root=(ROOT/'public/manager-atlas').resolve()
                for archive in manager_root.glob('index-*.json'):
                    if re.fullmatch(r'index-[a-f0-9]{12}\.json',archive.name) and '/manager-atlas/'+archive.name not in keep:
                        if archive.resolve().parent!=manager_root:raise ValueError('Unsafe manager archive retention path')
                        relative=archive.relative_to(ROOT).as_posix()
                        run(['git','rm','--',relative],ROOT);changed_paths.add(relative)
            # Refresh the bounded fixture/roster snapshot even in weeks with no new history.
            # It uses the same transaction and deployment, with no visitor-time API work.
            import atlas_fixture_board
            board = atlas_fixture_board.refresh(state)
            report['fixtureBoard'] = board['report']
            if board['changed']:
                changed_paths.update(board['paths'])
            if changed_paths:
                stage_release(run, ROOT, changed_paths)
                run(['git', 'commit', '-m', f'data: update Football and Manager Atlas through {manifest["through"]}'], ROOT)
                push_release(run, ROOT, report, base, changed_paths)
            needs_publish = bool(changed_paths) or manifest['version'] not in live_html or managers['manifest']['version'] not in manager_live_html
            if not needs_publish:
                try:
                    board_live_html = helper.fetch('https://ilmargine.bet/football-atlas/fixtures').decode()
                except (OSError, RuntimeError):
                    board_live_html = ''
                needs_publish = board['report']['version'] not in board_live_html
            if needs_publish:
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
