"""Per-fixture holds for the weekly club-history collection (F13).

One problem fixture is held and reported; it no longer stops the others.
Nothing in this module requests data, prices a match or writes the archive.
The collector decides what is held. This module keeps the closed code list,
the durable ledger, the window anchor, the accounting and the public summary.

Truth rules:
* A fixture counts as resolved only once it is found in the published archive
  handed to the collector. A dry run or a failed publication therefore cannot
  close a hold early or let the window move past it.
* The public release carries the list of held matches (clubs and dates only).
  If the state directory is lost, the ledger is rebuilt from that list.
"""
from collections import Counter
from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path

UTC = timezone.utc
SCHEMA = 1
LEDGER = 'club-history-holds.json'
AGE_LIMIT = timedelta(days=35)
# Keep the existing 20-request start reserve available to later runs.
QUOTA_FLOOR = 20
# Consecutive failed price requests before the run stops asking.
SOURCE_FAILURE_LIMIT = 3
REASON_LIMIT = 300

# Closed list. kind: retry = re-evaluated every run at no extra request,
# terminal = a price request is not repeated while the provider row is
# unchanged, review = a published row is questioned and needs a person,
# lifecycle = bookkeeping, never raised by a check.
HOLD_CODES = {
    'calendar-mismatch': ('retry', 'Calendar identity or kickoff mismatch'),
    'kickoff-timing-review': ('retry', 'Delayed or rescheduled, needs timing review'),
    'result-unconfirmed': ('retry', 'Result not confirmed in regulation time'),
    'club-name-unreviewed': ('retry', 'Unreviewed or conflicting club name'),
    'club-new-needs-review': ('retry', 'New club needs name and crest review'),
    'provider-row-out-of-scope': ('retry', 'Provider row for another sport or tournament'),
    'provider-row-malformed': ('retry', 'Provider row could not be read'),
    'provider-row-outside-window': ('retry', 'Provider row outside the requested window'),
    'provider-id-format': ('retry', 'Unexpected provider fixture ID format'),
    'provider-duplicate': ('retry', 'More than one provider row for one fixture'),
    'provider-missing': ('retry', 'Expected fixture not matched to a provider row'),
    'provider-unexpected': ('retry', 'Provider fixture not in the expected set'),
    'league-source-unavailable': ('retry', 'League fixture feed invalid or unavailable'),
    'price-source-unavailable': ('retry', 'Price history request failed'),
    'price-response-malformed': ('retry', 'Price history could not be read'),
    'quota-deferred': ('retry', 'Request allowance exhausted before this fixture'),
    'price-not-validated': ('terminal', 'No validated pre-match price'),
    'price-history-mismatch': ('terminal', 'Price history returned for another fixture'),
    'published-score-conflict': ('review', 'Published score differs from the calendar'),
    'awaiting-publication': ('lifecycle', 'Added, publication not yet confirmed'),
    'restored-from-release': ('lifecycle', 'Restored from the published held list'),
}
STATES = ('open', 'pending', 'aged', 'resolved')


class Hold(ValueError):
    """A per-fixture problem. Still a ValueError, so existing callers behave as before."""

    def __init__(self, code, message):
        if code not in HOLD_CODES:
            raise KeyError(f'Unknown hold code: {code}')
        super().__init__(message)
        self.code = code


def fixture_id(key):
    return 'fx:' + '|'.join(key)


def row_id(league, provider_id):
    return f'pr:{league}:{provider_id}'


def midnight(day):
    return datetime.fromisoformat(day + 'T00:00:00+00:00')


def kind_of(code):
    return HOLD_CODES[code][0]


def clip(text):
    text = ' '.join(str(text).split())
    return text if len(text) <= REASON_LIMIT else text[:REASON_LIMIT - 3] + '...'


class Blocked:
    """Stands in for the API once requests must stop. Cached prices still work."""

    def __init__(self, code, reason):
        self.code, self.reason = code, reason

    def get(self, endpoint, **params):
        raise Hold(self.code, self.reason)


class Meter:
    """Counts requests after the opening balance and decides when to stop asking."""

    def __init__(self, api, remaining):
        self.api, self.remaining = api, remaining
        self.used, self.exhausted, self.failures = 0, False, {}
        self._baseline = self._counted()

    def _counted(self):
        try:
            return sum(int(v) for v in self.api.calls.values())
        except (AttributeError, TypeError, ValueError):
            return 0

    @property
    def calls(self):
        return self.api.calls

    def spent(self):
        # The real client counts every attempt, including bounded retries.
        return max(self.used, self._counted() - self._baseline)

    def get(self, endpoint, **params):
        self.used += 1
        try:
            value = self.api.get(endpoint, **params)
        except RuntimeError as exc:
            if 'request allowance exhausted' in str(exc):
                self.exhausted = True
            else:
                self.failures[endpoint] = self.failures.get(endpoint, 0) + 1
            raise
        self.failures[endpoint] = 0
        return value

    def out_of_quota(self):
        return self.exhausted or self.remaining - self.spent() <= QUOTA_FLOOR

    def price_gate(self):
        if self.out_of_quota():
            return Blocked('quota-deferred', 'Request allowance exhausted; price history not requested this run')
        if self.failures.get('historical-odds', 0) >= SOURCE_FAILURE_LIMIT:
            return Blocked('price-source-unavailable',
                           f'Price source failed {SOURCE_FAILURE_LIMIT} times in a row; no further requests this run')
        return self


class Run:
    """Everything one collection run observed, before the ledger is updated."""

    def __init__(self, expected, stored, leagues, start, end, secrets=()):
        self.expected, self.stored, self.leagues = expected, stored, list(leagues)
        self.start, self.end = start, end
        # Reasons are built from error text. A credential must never reach a receipt.
        self.secrets = [s for s in secrets if isinstance(s, str) and len(s) >= 4]
        self.fixture_holds, self.reviews, self.row_holds = {}, {}, {}
        self.added, self.skipped, self.anomalies = {}, set(), []
        self.rows = {league: {} for league in self.leagues}
        self.feeds = {}

    def _safe(self, text):
        text = str(text)
        for secret in self.secrets:
            text = text.replace(secret, '[redacted]')
        return clip(text)

    def feed(self, league, status, code=None, reason=None, rows=None):
        self.feeds[league] = {'feed': status, 'code': code, 'reason': self._safe(reason) if reason else None, 'rows': rows}

    def row(self, league, disposition, provider_id):
        self.rows[league].setdefault(disposition, []).append(provider_id)

    def _hold(self, code, reason, league, home, away, day, provider_ids, signature, calendar_id, carried):
        return {'code': code, 'retry': kind_of(code), 'reason': self._safe(reason), 'league': league, 'home': home,
                'away': away, 'date': day, 'providerFixtureIds': sorted({str(i) for i in provider_ids if i}),
                'calendarId': calendar_id, 'signature': signature, 'carried': carried}

    def hold_fixture(self, key, fixture, code, reason, provider_ids=(), signature=None, carried=None):
        if key in self.fixture_holds or key in self.added or key in self.stored:
            raise ValueError(f'Hold accounting conflict for {key}')
        self.fixture_holds[key] = self._hold(code, reason, key[0], key[1], key[2], key[3], provider_ids, signature,
                                             (fixture or {}).get('id'), carried)

    def review(self, key, fixture, code, reason):
        self.reviews[key] = self._hold(code, reason, key[0], key[1], key[2], key[3], (), None, fixture.get('id'), None)

    def hold_row(self, league, row, code, reason, count=1):
        provider_id = str(row.get('fixtureId'))
        day = None
        try:
            day = datetime.fromisoformat(str(row.get('startTime')).replace('Z', '+00:00')).astimezone(UTC).date().isoformat()
        except (ValueError, TypeError):
            pass
        names = [row.get('participant1Name'), row.get('participant2Name')]
        home, away = (n if isinstance(n, str) else None for n in names)
        self.row_holds[(league, provider_id)] = self._hold(code, reason, league, home, away, day, [provider_id], None, None, None)
        for _ in range(count):
            self.row(league, 'held', provider_id)

    def add(self, key, provider_id):
        if key in self.added or key in self.fixture_holds or key in self.stored:
            raise ValueError(f'Addition accounting conflict for {key}')
        self.added[key] = provider_id

    def settle_unseen(self, ledger):
        """Every expected fixture not yet accounted for becomes a hold."""
        for key, fixture in self.expected.items():
            if key in self.stored or key in self.added or key in self.fixture_holds or key in self.skipped:
                continue
            feed = self.feeds.get(key[0], {'feed': 'not-requested', 'code': 'league-source-unavailable',
                                           'reason': 'League fixture feed was not requested'})
            if feed['feed'] != 'ok':
                prior = ledger.entries.get(fixture_id(key))
                if prior and prior['state'] == 'open' and kind_of(prior['code']) != 'lifecycle':
                    # Not re-examined this run: keep its code, reason and price signature.
                    self.hold_fixture(key, fixture, prior['code'], prior['reason'], prior.get('providerFixtureIds', ()),
                                      prior.get('signature'), carried='league')
                else:
                    self.hold_fixture(key, fixture, feed['code'], feed['reason'])
                continue
            unmatched = sorted(pid for (league, pid) in self.row_holds if league == key[0])
            reason = 'Completed in the results calendar but not matched to any provider row'
            if unmatched:
                reason += f'; {len(unmatched)} provider rows in this league are held unmatched: ' + ', '.join(unmatched[:8])
            self.hold_fixture(key, fixture, 'provider-missing', reason)

    def accounting(self):
        """Exact, with ID lists. Raises if anything is counted twice or not at all."""
        label = lambda key: f'{key[3]} {key[0]} {key[1]} v {key[2]}'
        buckets = {'published': [], 'added': [], 'held': [], 'beforeForwardStart': []}
        for key in sorted(self.expected, key=lambda k: (k[3], k)):
            places = [name for name, present in (('published', key in self.stored), ('added', key in self.added),
                                                 ('held', key in self.fixture_holds),
                                                 ('beforeForwardStart', key in self.skipped)) if present]
            if len(places) != 1:
                raise ValueError(f'Hold accounting does not balance for {label(key)}: {places or "unaccounted"}')
            buckets[places[0]].append(label(key))
        stray = [label(k) for k in (set(self.added) | set(self.fixture_holds)) - set(self.expected)]
        provider = {}
        for league in self.leagues:
            total = self.feeds.get(league, {}).get('rows')
            dispositions = self.rows[league]
            counted = sum(len(ids) for ids in dispositions.values())
            if total is not None and counted != total:
                raise ValueError(f'Provider row accounting does not balance for {league}: {counted} of {total}')
            provider[league] = {'rows': total, **{name: sorted(ids) for name, ids in sorted(dispositions.items())}}
        return {'calendar': {'expected': len(self.expected), **{name: len(ids) for name, ids in buckets.items()},
                             'ids': buckets, 'outsideExpected': sorted(stray), 'balanced': True},
                'provider': provider}

    def by_league(self):
        out = {}
        for league in self.leagues:
            expected = [k for k in self.expected if k[0] == league]
            held = [k for k in expected if k in self.fixture_holds]
            added = [k for k in expected if k in self.added]
            unpublished = [k for k in expected if k not in self.stored and k not in self.skipped]
            codes = Counter(h['code'] for k, h in self.fixture_holds.items() if k[0] == league)
            codes.update(h['code'] for (lg, _), h in self.row_holds.items() if lg == league)
            feed = self.feeds.get(league, {'feed': 'not-requested'})
            out[league] = {'feed': feed['feed'], 'feedReason': feed.get('reason'), 'expected': len(expected),
                           'published': len(expected) - len(unpublished) - sum(k in self.skipped for k in expected),
                           'added': len(added), 'held': len(held), 'codes': dict(sorted(codes.items())),
                           # One held fixture is a fixture problem. A league with every
                           # unpublished fixture held is a source problem for that league.
                           'sourceFailure': feed['feed'] != 'ok' or (len(unpublished) >= 2 and len(held) == len(unpublished))}
        return out


class Ledger:
    def __init__(self, path, entries, rebuilt=None, evidence=None):
        self.path, self.entries, self.rebuilt, self.evidence = path, entries, rebuilt, evidence
        self.resolved_now, self.aged_now = [], []

    @classmethod
    def load(cls, state, public, stored, now):
        path = Path(state) / LEDGER
        entries, rebuilt, evidence = {}, None, None
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
                if data.get('schema') != SCHEMA or not isinstance(data.get('holds'), list):
                    raise ValueError('Unsupported hold ledger')
                for entry in data['holds']:
                    if (entry['code'] not in HOLD_CODES or entry['state'] not in STATES
                            or entry['kind'] not in ('fixture', 'provider-row') or not isinstance(entry['id'], str)
                            or not isinstance(entry['firstSeen'], str)):
                        raise ValueError('Invalid hold ledger entry')
                    if entry['kind'] == 'fixture':
                        midnight(entry['date'])
                    entries[entry['id']] = entry
                if len(entries) != len(data['holds']):
                    raise ValueError('Duplicate hold ledger entry')
            except (OSError, ValueError, KeyError, TypeError, AttributeError):
                # Keep the unreadable bytes as evidence and rebuild from the published list.
                evidence = path.with_name(f'club-history-holds.corrupt-{now.strftime("%Y%m%dT%H%M%SZ")}.json')
                path.replace(evidence)
                entries, rebuilt = {}, 'unreadable'
        elif (public or {}).get('matches') or (public or {}).get('held'):
            rebuilt = 'missing'
        try:
            listed = list((public or {}).get('matches') or [])
            for match in listed:
                key = (match['league'], match['home'], match['away'], match['date'])
                midnight(match['date']), midnight(match['since'])
                if not all(isinstance(part, str) for part in key):
                    raise ValueError('Invalid published held match')
                identity = fixture_id(key)
                known = entries.get(identity)
                if key in stored or (known and known['state'] != 'resolved'):
                    continue
                entries[identity] = {
                    'id': identity, 'kind': 'fixture', 'code': 'restored-from-release', 'retry': 'lifecycle',
                    'reason': 'Listed as held in the published release; detail not in the local ledger',
                    'league': key[0], 'home': key[1], 'away': key[2], 'date': key[3], 'providerFixtureIds': [],
                    'calendarId': None, 'signature': None, 'state': 'aged' if match.get('state') == 'aged' else 'open',
                    'firstSeen': (known or {}).get('firstSeen') or match['since'] + 'T00:00:00+00:00',
                    'lastSeen': now.isoformat(), 'attempts': 0, 'previousCodes': [], 'restored': True}
        except (KeyError, TypeError, ValueError, AttributeError):
            raise ValueError('Published hold metadata is malformed; review before collection') from None
        return cls(path, entries, rebuilt, evidence.name if evidence else None)

    def window_start(self, base, end, now):
        """C6 and C7: follow the oldest hold inside 35 days; older ones are aged and kept."""
        limit, anchors = end - AGE_LIMIT, []
        for entry in self.entries.values():
            if entry['state'] not in ('open', 'pending') or not entry.get('date'):
                continue
            at = midnight(entry['date'])
            if at < limit:
                self._age(entry, now)
            else:
                anchors.append(at)
        return min([base, *anchors])

    def _age(self, entry, now):
        entry.update(state='aged', agedAt=now.isoformat())
        self.aged_now.append(entry['id'])

    def known(self, key):
        """Already on the books from an earlier run, in any unresolved state."""
        entry = self.entries.get(fixture_id(key))
        return bool(entry) and entry['state'] != 'resolved'

    def terminal(self, key, provider_id, signature):
        """A price hold whose provider row has not changed: do not ask again."""
        entry = self.entries.get(fixture_id(key))
        if (entry and entry['state'] == 'open' and kind_of(entry['code']) == 'terminal'
                and entry.get('signature') and entry['signature'] == signature
                and provider_id in entry.get('providerFixtureIds', ())):
            return entry
        return None

    def _upsert(self, identity, kind, hold, stamp):
        entry = self.entries.get(identity)
        if entry is None:
            entry = self.entries[identity] = {'id': identity, 'kind': kind, 'firstSeen': stamp, 'attempts': 0,
                                              'previousCodes': [], 'code': hold['code']}
        elif entry['state'] == 'resolved':
            entry['reopenedAt'] = stamp
            for name in ('resolvedAt', 'resolution'):
                entry.pop(name, None)
        if hold['carried'] == 'league':
            entry['carriedAt'] = stamp
        elif hold['carried'] == 'terminal':
            entry.update(lastSeen=stamp, skippedRequests=entry.get('skippedRequests', 0) + 1)
        else:
            if entry['code'] != hold['code'] and entry['code'] not in entry['previousCodes']:
                entry['previousCodes'].append(entry['code'])
            entry.update({name: hold[name] for name in ('code', 'retry', 'reason', 'league', 'home', 'away', 'date',
                                                        'providerFixtureIds', 'calendarId', 'signature')})
            entry.update(lastSeen=stamp, attempts=entry['attempts'] + 1)
        entry['state'] = 'open'
        for name in ('pendingSince', 'agedAt'):
            entry.pop(name, None)
        return identity

    def _resolve(self, entry, resolution, stamp):
        entry.update(state='resolved', resolvedAt=stamp, resolution=resolution)
        self.resolved_now.append(entry['id'])

    def apply(self, run, now):
        stamp, touched, drop = now.isoformat(), set(), []
        for key, hold in {**run.fixture_holds, **run.reviews}.items():
            touched.add(self._upsert(fixture_id(key), 'fixture', hold, stamp))
        for (league, provider_id), hold in run.row_holds.items():
            touched.add(self._upsert(row_id(league, provider_id), 'provider-row', hold, stamp))
        for key, provider_id in run.added.items():
            # Added this run. It stays on the books, and keeps anchoring the window,
            # until a later run finds it in the published archive.
            identity = fixture_id(key)
            entry = self.entries.get(identity)
            if entry is None:
                entry = self.entries[identity] = {
                    'id': identity, 'kind': 'fixture', 'code': 'awaiting-publication', 'retry': 'lifecycle',
                    'reason': HOLD_CODES['awaiting-publication'][1], 'league': key[0], 'home': key[1], 'away': key[2],
                    'date': key[3], 'providerFixtureIds': [provider_id], 'calendarId': run.expected[key].get('id'),
                    'signature': None, 'firstSeen': stamp, 'attempts': 0, 'previousCodes': []}
            if entry.get('state') != 'pending':
                entry['pendingSince'] = stamp
            for name in ('resolvedAt', 'resolution', 'agedAt'):
                entry.pop(name, None)
            entry.update(state='pending', lastSeen=stamp)
            touched.add(identity)
        for identity, entry in self.entries.items():
            if identity in touched or entry['state'] == 'resolved':
                continue
            feed_ok = run.feeds.get(entry.get('league'), {}).get('feed') == 'ok'
            in_window = bool(entry.get('date')) and midnight(entry['date']) >= run.start
            if entry['kind'] == 'fixture':
                key = (entry['league'], entry['home'], entry['away'], entry['date'])
                review = kind_of(entry['code']) == 'review'
                if key in run.stored and not review:
                    if entry['code'] == 'awaiting-publication' and not entry['previousCodes']:
                        drop.append(identity)  # Never held; publication is now confirmed.
                    else:
                        self._resolve(entry, 'published', stamp)
                elif entry['state'] == 'aged':
                    continue
                elif not in_window:
                    self._age(entry, now)
                elif review:
                    self._resolve(entry, 'conflict-cleared', stamp)
                elif not feed_ok:
                    entry['carriedAt'] = stamp
                else:
                    self._resolve(entry, 'no-longer-expected', stamp)
            elif entry['state'] == 'aged':
                continue
            elif entry.get('date') and not in_window:
                self._age(entry, now)
            elif feed_ok:
                self._resolve(entry, 'row-cleared', stamp)
            else:
                entry['carriedAt'] = stamp
        for identity in drop:
            del self.entries[identity]

    def counts(self):
        return dict(Counter(entry['state'] for entry in self.entries.values()))

    def status(self):
        # Open means something is held or aged. An addition awaiting publication is not a hold.
        return 'open' if any(entry['state'] in ('open', 'aged') for entry in self.entries.values()) else 'closed'

    def save(self, now):
        ordered = sorted(self.entries.values(), key=lambda e: (e.get('date') or '', e['id']))
        value = {'schema': SCHEMA, 'updatedAt': now.isoformat(), 'status': self.status(), 'counts': self.counts(),
                 'codes': {code: {'kind': kind, 'meaning': meaning} for code, (kind, meaning) in HOLD_CODES.items()},
                 'holds': ordered}
        tmp = self.path.with_name(self.path.name + f'.{os.getpid()}.tmp')
        tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
        tmp.replace(self.path)

    def public(self):
        """Clubs, dates and counts only. No provider names, IDs or reasons."""
        matches, review = [], 0
        for entry in self.entries.values():
            if entry['kind'] != 'fixture' or entry['state'] not in ('open', 'aged'):
                continue
            if kind_of(entry['code']) == 'review':
                review += 1
                continue
            matches.append({'date': entry['date'], 'league': entry['league'], 'home': entry['home'],
                            'away': entry['away'], 'since': entry['firstSeen'][:10],
                            'state': 'aged' if entry['state'] == 'aged' else 'held'})
        if not matches and not review:
            return None
        matches.sort(key=lambda m: (m['date'], m['league'], m['home'], m['away']))
        summary = {'held': len(matches), 'matches': matches}
        if review:
            summary['review'] = review
        return summary

    def report(self, run):
        listed = lambda state: [e for e in sorted(self.entries.values(), key=lambda e: (e.get('date') or '', e['id']))
                                if e['state'] == state]
        return {'status': self.status(), 'counts': self.counts(), 'ledger': self.path.name,
                'ledgerRebuilt': self.rebuilt, 'ledgerEvidence': self.evidence,
                'byLeague': run.by_league(), 'open': listed('open'), 'aged': listed('aged'),
                'pendingPublication': listed('pending'),
                'resolvedThisRun': [self.entries[i] for i in self.resolved_now if i in self.entries],
                'agedThisRun': list(self.aged_now), 'anomalies': run.anomalies}


def same_public(old, new):
    """Has the public held list changed? completeThrough is derived, so ignore it."""
    strip = lambda value: {k: v for k, v in (value or {}).items() if k != 'completeThrough'}
    return strip(old) == strip(new)


def with_complete_through(summary, through):
    """The last day up to which no confirmed result is known to be missing."""
    public = dict(summary)
    if public.get('matches'):
        oldest = min(m['date'] for m in public['matches'])
        public['completeThrough'] = min(through, (date.fromisoformat(oldest) - timedelta(days=1)).isoformat())
    return public
