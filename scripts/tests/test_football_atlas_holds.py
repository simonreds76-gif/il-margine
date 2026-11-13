"""F13: per-fixture club-history holds. Deterministic, offline, no real records.

Every request goes to a fake. The baseline comparison (C5) needs the strict
pre-F13 collector: set F13_BASELINE_SCRIPTS to a folder holding the current
football_atlas_weekly.py, otherwise that one test is skipped and says so.
"""
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1]))
import football_atlas_weekly as w
import football_atlas_holds as holds

UTC = timezone.utc
NOW = datetime(2026, 11, 10, 18, tzinfo=UTC)
PL, SA = 'premier-league', 'serie-a'
TID = {PL: 17, SA: 23}
TEAMS = ['Arsenal', 'Chelsea', 'Liverpool', 'Everton', 'Fulham', 'Brentford', 'Napoli', 'Parma', 'Roma', 'Lazio']
REAL_READ = w.legacy.read


def day(days_ago, hour=15):
    return (NOW - timedelta(days=days_ago)).replace(hour=hour, minute=0)


def fixture(gid, home, away, kickoff, league=PL, score=(2, 1), status=-1):
    return dict(id=gid, league=league, home=home, away=away, kickoff=kickoff.isoformat(), status=status,
                score=list(score), season='2026-2027')


def row(pid, home, away, kickoff, league=PL, **extra):
    return dict(fixtureId=pid, tournamentId=TID[league], sportId=10, participant1Name=home, participant2Name=away,
                startTime=kickoff.isoformat(), statusId=2, **extra)


def history(kickoff, prices=(2.5, 3.2, 3.1)):
    return {oid: {'players': {'0': [{'createdAt': (kickoff - timedelta(minutes=4)).isoformat(), 'price': price,
                                    'active': True}]}}
            for oid, price in zip(('101', '102', '103'), prices)}


def priced(pid, kickoff, book='pinnacle'):
    return {'fixtureId': pid, 'bookmakers': {book: {'markets': {'101': {'outcomes': history(kickoff)}}}}}


def archive(*rows):
    return dict(teams=list(TEAMS), leagues=list(w.TOURNAMENTS), seasons=['2026-2027'], fixtures=[list(r) for r in rows])


def stored(identity, date, league, home, away, score=(2, 1)):
    return [identity, date, list(w.TOURNAMENTS).index(league), 0, TEAMS.index(home), TEAMS.index(away), *score,
            2.5, 3.2, 3.1, 2]


class API:
    """Fake provider. feeds: league -> rows, or an Exception to raise, or any invalid value."""

    def __init__(self, feeds=None, prices=None, quota=200):
        self.feeds, self.prices, self.quota_value = feeds or {}, prices or {}, quota
        self.calls, self.log = {}, []

    def quota(self):
        if isinstance(self.quota_value, Exception):
            raise self.quota_value
        return self.quota_value

    def get(self, endpoint, **params):
        self.calls[endpoint] = self.calls.get(endpoint, 0) + 1
        if endpoint == 'fixtures':
            league = next(name for name, tid in w.TOURNAMENTS.items() if tid == params['tournamentId'])
            self.log.append(('fixtures', league))
            value = self.feeds.get(league, [])
        else:
            self.log.append(('price', params['fixtureId']))
            value = self.prices[params['fixtureId']]
        if isinstance(value, Exception):
            raise value
        return copy.deepcopy(value)

    def price_requests(self):
        return [name for kind, name in self.log if kind == 'price']


class Case(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state = Path(self.tmp.name) / 'state'
        self.state.mkdir()
        self.aliases = {}

    def collect(self, old, calendar, api, now=NOW, through='2026-11-01', public=None, state=None):
        before = copy.deepcopy(old)
        manifest = {'through': through}
        if public is not None:
            manifest['historyHolds'] = public
        read = lambda path: self.aliases if str(path).endswith('football-atlas-clubs.json') else REAL_READ(path)
        with patch.object(w.legacy, 'calendar', return_value=copy.deepcopy(calendar)), \
                patch.object(w.legacy, 'read', side_effect=read), patch('builtins.print'):
            new, report = w.collect(old, manifest, state or self.state, now, api)
        # C3: the archive handed in is never mutated and every stored row survives unchanged.
        self.assertEqual(old, before)
        for stored_row in before['fixtures']:
            self.assertIn(stored_row, new['fixtures'])
        self.assertEqual(len(new['fixtures']), len(before['fixtures']) + report['newMatches'])
        # C1: the receipt balances and carries ID lists.
        calendar_side = report['accounting']['calendar']
        self.assertTrue(calendar_side['balanced'])
        self.assertEqual(calendar_side['expected'], sum(len(v) for v in calendar_side['ids'].values()))
        self.assertEqual(calendar_side['added'], report['newMatches'])
        # C2: every hold on the books has a closed code and the required fields.
        for entry in self.ledger(state)['holds']:
            self.assertIn(entry['code'], holds.HOLD_CODES)
            for name in ('reason', 'league', 'date', 'firstSeen', 'lastSeen', 'providerFixtureIds', 'state'):
                self.assertIn(name, entry)
        return new, report

    def ledger(self, state=None):
        return json.loads(((state or self.state) / holds.LEDGER).read_text(encoding='utf-8'))

    def entry(self, identity, state=None):
        return next(e for e in self.ledger(state)['holds'] if e['id'] == identity)

    def held(self, report):
        return {(e['id'], e['code']) for e in report['holds']['open']}

    @staticmethod
    def fx(f):
        return holds.fixture_id(w.fixture_key(f))


class HoldTypes(Case):
    """One problem fixture is held with its code; the independent fixture is still added."""

    def setUp(self):
        super().setUp()
        self.good = fixture('g1', 'Arsenal', 'Chelsea', day(3))
        self.good_row = row('id1', 'Arsenal', 'Chelsea', day(3))
        self.bad = fixture('g2', 'Liverpool', 'Everton', day(4))
        self.prices = {'id1': priced('id1', day(3)), 'id2': priced('id2', day(4))}

    def run_with(self, bad_rows, calendar=None, prices=None, old=None):
        api = API({PL: [self.good_row, *bad_rows]}, prices or self.prices)
        new, report = self.collect(old or archive(), calendar or [self.good, self.bad], api)
        added = [r[0] for r in new['fixtures']]
        self.assertEqual(added, ['papi-id1'])  # C4: nothing is added for the held fixture.
        self.assertEqual(report['newMatches'], 1)
        self.assertEqual(report['holdStatus'], 'open')
        return report, api

    def test_calendar_mismatch(self):
        report, _ = self.run_with([row('id2', 'Liverpool', 'Everton', day(4) + timedelta(hours=2))])
        self.assertEqual(self.held(report), {('pr:premier-league:id2', 'calendar-mismatch'),
                                             (self.fx(self.bad), 'provider-missing')})
        self.assertIn('id2', self.entry(self.fx(self.bad))['reason'])
        self.assertEqual(report['accounting']['provider'][PL]['held'], ['id2'])
        self.assertEqual(report['accounting']['provider'][PL]['added'], ['id1'])

    def test_kickoff_timing_review(self):
        delayed = row('id2', 'Liverpool', 'Everton', day(4), trueStartTime=(day(4) + timedelta(hours=1)).isoformat())
        report, _ = self.run_with([delayed])
        self.assertIn(('pr:premier-league:id2', 'kickoff-timing-review'), self.held(report))

    def test_result_unconfirmed_is_held_by_provider_row(self):
        pending = {**self.bad, 'status': 0}
        report, _ = self.run_with([row('id2', 'Liverpool', 'Everton', day(4))], calendar=[self.good, pending])
        self.assertEqual(self.held(report), {('pr:premier-league:id2', 'result-unconfirmed')})
        self.assertIsNone(report['publicHolds'])  # Not a confirmed result, so not a public gap.

    def test_club_name_unreviewed(self):
        report, _ = self.run_with([row('id2', 'Liverpool Reds XI', 'Everton', day(4))])
        self.assertIn(('pr:premier-league:id2', 'club-name-unreviewed'), self.held(report))
        self.assertIn((self.fx(self.bad), 'provider-missing'), self.held(report))

    def test_new_club_needs_review(self):
        self.aliases = {PL: {'sunderland': 'Sunderland'}}
        newcomer = fixture('g2', 'Sunderland', 'Everton', day(4))
        report, api = self.run_with([row('id2', 'Sunderland', 'Everton', day(4))], calendar=[self.good, newcomer])
        self.assertEqual(self.held(report), {(self.fx(newcomer), 'club-new-needs-review')})
        self.assertEqual(api.price_requests(), ['id1'])

    def test_provider_row_out_of_scope(self):
        report, _ = self.run_with([{**row('id2', 'Liverpool', 'Everton', day(4)), 'sportId': 11}])
        self.assertIn(('pr:premier-league:id2', 'provider-row-out-of-scope'), self.held(report))

    def test_provider_row_malformed(self):
        broken = row('id2', 'Liverpool', 'Everton', day(4))
        del broken['startTime']
        report, _ = self.run_with([broken])
        self.assertIn(('pr:premier-league:id2', 'provider-row-malformed'), self.held(report))

    def test_provider_row_outside_window(self):
        recent = NOW - timedelta(hours=2)  # Finished, but inside the six-hour settling margin.
        late = fixture('g3', 'Fulham', 'Brentford', recent)
        report, _ = self.run_with([row('id3', 'Fulham', 'Brentford', recent)], calendar=[self.good, late])
        self.assertEqual(self.held(report), {('pr:premier-league:id3', 'provider-row-outside-window')})

    def test_provider_id_format(self):
        report, api = self.run_with([row('x2', 'Liverpool', 'Everton', day(4))])
        self.assertEqual(self.held(report), {(self.fx(self.bad), 'provider-id-format')})
        self.assertEqual(api.price_requests(), ['id1'])

    def test_same_provider_id_twice_holds_both_rows(self):
        twice = row('id2', 'Liverpool', 'Everton', day(4))
        report, api = self.run_with([twice, dict(twice)])
        self.assertIn(('pr:premier-league:id2', 'provider-duplicate'), self.held(report))
        self.assertEqual(report['accounting']['provider'][PL]['held'], ['id2', 'id2'])
        self.assertEqual(api.price_requests(), ['id1'])

    def test_two_provider_rows_for_one_identity_hold_both_never_choose(self):
        report, api = self.run_with([row('id2', 'Liverpool', 'Everton', day(4)), row('id9', 'Liverpool', 'Everton', day(4))],
                                    prices={**self.prices, 'id9': priced('id9', day(4))})
        self.assertEqual(self.held(report), {(self.fx(self.bad), 'provider-duplicate')})
        self.assertEqual(self.entry(self.fx(self.bad))['providerFixtureIds'], ['id2', 'id9'])
        self.assertEqual(api.price_requests(), ['id1'])

    def test_expected_fixture_not_returned(self):
        report, _ = self.run_with([])
        self.assertEqual(self.held(report), {(self.fx(self.bad), 'provider-missing')})
        self.assertEqual(report['publicHolds']['held'], 1)

    def test_price_not_validated_and_fallback_never_repairs_a_leg(self):
        suspended = priced('id2', day(4))
        legs = suspended['bookmakers']['pinnacle']['markets']['101']['outcomes']
        legs['102']['players']['0'].append({'createdAt': (day(4) - timedelta(seconds=5)).isoformat(), 'price': 3.2, 'active': False})
        report, _ = self.run_with([row('id2', 'Liverpool', 'Everton', day(4))], prices={**self.prices, 'id2': suspended})
        self.assertEqual(self.held(report), {(self.fx(self.bad), 'price-not-validated')})
        self.assertEqual(self.entry(self.fx(self.bad))['retry'], 'terminal')

    def test_price_history_for_another_fixture(self):
        report, _ = self.run_with([row('id2', 'Liverpool', 'Everton', day(4))],
                                  prices={**self.prices, 'id2': priced('id777', day(4))})
        self.assertEqual(self.held(report), {(self.fx(self.bad), 'price-history-mismatch')})

    def test_price_source_unavailable(self):
        report, _ = self.run_with([row('id2', 'Liverpool', 'Everton', day(4))],
                                  prices={**self.prices, 'id2': RuntimeError('historical-odds returned HTTP 500')})
        self.assertEqual(self.held(report), {(self.fx(self.bad), 'price-source-unavailable')})
        self.assertEqual(self.entry(self.fx(self.bad))['retry'], 'retry')

    def test_price_response_malformed(self):
        report, _ = self.run_with([row('id2', 'Liverpool', 'Everton', day(4))], prices={**self.prices, 'id2': ['not', 'a', 'dict']})
        self.assertEqual(self.held(report), {(self.fx(self.bad), 'price-response-malformed')})

    def test_a_credential_in_error_text_never_reaches_the_receipt_or_ledger(self):
        api = API({PL: [self.good_row, row('id2', 'Liverpool', 'Everton', day(4))]},
                  {**self.prices, 'id2': RuntimeError('GET https://x/y?apiKey=test-only-secret-key failed')})
        api.key = 'test-only-secret-key'
        _, report = self.collect(archive(), [self.good, self.bad], api)
        self.assertEqual(self.entry(self.fx(self.bad))['reason'], 'GET https://x/y?apiKey=[redacted] failed')
        for name in ('collection.json', holds.LEDGER, 'reconciliation.json'):
            self.assertNotIn('test-only-secret-key', (self.state / name).read_text(encoding='utf-8'))

    def test_hold_codes_are_a_closed_list(self):
        with self.assertRaises(KeyError):
            holds.Hold('made-up-code', 'x')
        self.assertTrue(issubclass(holds.Hold, ValueError))
        self.assertEqual({kind for kind, _ in holds.HOLD_CODES.values()}, {'retry', 'terminal', 'review', 'lifecycle'})


class Isolation(Case):
    def test_partial_feed_holds_one_fixture_and_never_fails_the_run(self):
        f = fixture('g1', 'Arsenal', 'Chelsea', day(3))
        new, report = self.collect(archive(), [f], API())
        self.assertEqual(new['fixtures'], [])
        self.assertEqual(self.held(report), {(self.fx(f), 'provider-missing')})
        self.assertEqual(report['status'], 'validated')
        self.assertEqual(json.loads((self.state / 'reconciliation.json').read_text())['status'], 'held')

    def test_unreviewed_club_holds_every_fixture_of_that_club_and_the_rest_proceed(self):
        calendar = [fixture('g1', 'Arsenal', 'Chelsea', day(3)), fixture('g2', 'Liverpool', 'Everton', day(4)),
                    fixture('g3', 'Fulham', 'Liverpool', day(10)), fixture('g4', 'Napoli', 'Parma', day(3), SA)]
        api = API({PL: [row('id1', 'Arsenal', 'Chelsea', day(3)), row('id2', 'Liverpool Reds XI', 'Everton', day(4)),
                        row('id3', 'Fulham', 'Liverpool Reds XI', day(10))],
                   SA: [row('id4', 'Napoli', 'Parma', day(3), SA)]},
                  {'id1': priced('id1', day(3)), 'id4': priced('id4', day(3), 'bet365')})
        new, report = self.collect(archive(), calendar, api)
        self.assertEqual(sorted(r[0] for r in new['fixtures']), ['papi-id1', 'papi-id4'])
        self.assertEqual({code for _, code in self.held(report)}, {'club-name-unreviewed', 'provider-missing'})
        self.assertEqual(report['publicHolds']['held'], 2)
        league = report['holds']['byLeague']
        self.assertEqual(league[PL]['codes'], {'club-name-unreviewed': 2, 'provider-missing': 2})
        self.assertFalse(league[PL]['sourceFailure'])  # One of its three fixtures was added.
        self.assertEqual(league[SA]['codes'], {})
        self.assertEqual(report['priceSources'], {'pinnacle': 1, 'bet365': 1})

    def test_invalid_league_response_is_scoped_to_that_league(self):
        calendar = [fixture('g1', 'Arsenal', 'Chelsea', day(3)), fixture('g2', 'Liverpool', 'Everton', day(4)),
                    fixture('g4', 'Napoli', 'Parma', day(3), SA)]
        for label, feed in (('not a list', {'error': 'x'}), ('too many rows', [row(f'id{n}', 'Arsenal', 'Chelsea', day(3)) for n in range(201)]),
                            ('row without an ID', [{'statusId': 2}]), ('request failed', RuntimeError('fixtures returned HTTP 503'))):
            with self.subTest(label), tempfile.TemporaryDirectory() as directory:
                api = API({PL: feed, SA: [row('id4', 'Napoli', 'Parma', day(3), SA)]}, {'id4': priced('id4', day(3))})
                new, report = self.collect(archive(), calendar, api, state=Path(directory))
                self.assertEqual([r[0] for r in new['fixtures']], ['papi-id4'])
                league = report['holds']['byLeague'][PL]
                self.assertTrue(league['sourceFailure'])
                self.assertNotEqual(league['feed'], 'ok')
                self.assertEqual(league['codes'], {'league-source-unavailable': 2})
                self.assertFalse(report['holds']['byLeague'][SA]['sourceFailure'])
                self.assertFalse((Path(directory) / 'fixtures-17.json').exists())  # Invalid feed is not saved as good.

    def test_league_with_every_fixture_held_is_reported_as_a_source_failure(self):
        calendar = [fixture('g1', 'Arsenal', 'Chelsea', day(3)), fixture('g2', 'Liverpool', 'Everton', day(4))]
        _, report = self.collect(archive(), calendar, API())
        self.assertTrue(report['holds']['byLeague'][PL]['sourceFailure'])
        self.assertEqual(report['holds']['byLeague'][PL]['feed'], 'ok')

    def test_published_score_conflict_is_first_in_the_receipt_and_the_stored_row_is_untouched(self):
        published = stored('papi-id5', day(5).date().isoformat(), PL, 'Fulham', 'Brentford', (1, 0))
        calendar = [fixture('g5', 'Fulham', 'Brentford', day(5), score=(1, 1)), fixture('g1', 'Arsenal', 'Chelsea', day(3))]
        api = API({PL: [row('id5', 'Fulham', 'Brentford', day(5)), row('id1', 'Arsenal', 'Chelsea', day(3))]},
                  {'id1': priced('id1', day(3))})
        new, report = self.collect(archive(published), calendar, api)
        self.assertEqual(next(iter(report)), 'reviewItems')
        self.assertEqual(report['reviewItems'][0]['code'], 'published-score-conflict')
        self.assertIn(published, new['fixtures'])
        self.assertEqual(report['newMatches'], 1)
        self.assertEqual(report['publicHolds'], {'held': 0, 'matches': [], 'review': 1})
        self.assertEqual(api.price_requests(), ['id1'])
        # Calendar and archive agree again: the review item closes, nothing is rewritten.
        calendar[0]['score'] = [1, 0]
        again, report = self.collect(new, calendar, api, now=NOW + timedelta(days=1))
        self.assertEqual(again, new)
        self.assertEqual(report['reviewItems'], [])
        self.assertEqual(self.entry(self.fx(calendar[0]))['resolution'], 'conflict-cleared')

    def test_public_summary_names_clubs_and_dates_only(self):
        f = fixture('g2', 'Liverpool', 'Everton', day(4))
        api = API({PL: [row('id2', 'Liverpool', 'Everton', day(4))]}, {'id2': priced('id777', day(4))})
        _, report = self.collect(archive(), [f], api)
        public = report['publicHolds']
        self.assertEqual(public, {'held': 1, 'matches': [{'date': day(4).date().isoformat(), 'league': PL, 'home': 'Liverpool',
                                                          'away': 'Everton', 'since': NOW.date().isoformat(), 'state': 'held'}]})
        text = json.dumps(public).lower()
        for word in ('pinnacle', 'bet365', 'oddspapi', 'goaloo', 'id2', 'id777', 'price', 'mismatch'):
            self.assertNotIn(word, text)


class Fatal(Case):
    """Integrity failures still stop the run and leave archive and ledger alone."""

    def setUp(self):
        super().setUp()
        self.f = fixture('g1', 'Arsenal', 'Chelsea', day(3))
        self.api = API({PL: [row('id1', 'Arsenal', 'Chelsea', day(3))]}, {'id1': priced('id1', day(3))})

    def fatal(self, pattern, **kwargs):
        args = {'old': archive(), 'calendar': [self.f], 'api': self.api, **kwargs}
        with self.assertRaisesRegex((ValueError, RuntimeError), pattern):
            self.collect(**args)
        self.assertFalse((self.state / holds.LEDGER).exists())

    def test_duplicate_identity_in_the_stored_archive(self):
        date = day(20).date().isoformat()
        self.fatal('Duplicate existing fixture identity',
                   old=archive(stored('a', date, PL, 'Fulham', 'Brentford'), stored('b', date, PL, 'Fulham', 'Brentford')))

    def test_calendar_unavailable(self):
        with patch.object(w.legacy, 'calendar', side_effect=ValueError('Incomplete calendar')), \
                self.assertRaisesRegex(ValueError, 'Incomplete calendar'):
            w.collect(archive(), {'through': '2026-11-01'}, self.state, NOW, self.api)
        self.assertEqual(self.api.log, [])

    def test_quota_unavailable_at_the_start(self):
        self.api.quota_value = ValueError('OddsPapi quota unavailable or below 20-request safety reserve')
        self.fatal('quota unavailable')
        self.assertEqual(self.api.log, [])

    def test_credentials_missing(self):
        with self.assertRaisesRegex(ValueError, 'ODDSPAPI_API_KEY is missing'):
            w.OddsPapi(None)

    def test_archive_over_35_days_behind(self):
        self.fatal('over 35 days behind', through='2026-09-25')

    def test_more_than_180_additions(self):
        rows, prices = [], {}
        calendar, n = [], 0
        for days_ago in range(3, 13):
            for home in TEAMS[:6]:
                for away in TEAMS[:6]:
                    if home != away and n < 181:
                        kickoff = day(days_ago)
                        calendar.append(fixture(f'g{n}', home, away, kickoff))
                        rows.append(row(f'id{n}', home, away, kickoff))
                        prices[f'id{n}'] = priced(f'id{n}', kickoff)
                        n += 1
        self.assertEqual(len(calendar), 181)
        # Exercise the addition limit, rather than exhausting the request reserve.
        api = API({PL: rows}, prices, quota=holds.QUOTA_FLOOR + 200)
        with self.assertRaisesRegex(ValueError, 'More than 180 new matches'):
            self.collect(archive(), calendar, api)
        self.assertFalse((self.state / holds.LEDGER).exists())

    def test_no_league_feed_at_all(self):
        down = RuntimeError('fixtures returned HTTP 503')
        self.api.feeds = {league: down for league in w.TOURNAMENTS}
        self.fatal('No league fixture feed was available')
        self.assertEqual(json.loads((self.state / 'collection.json').read_text())['status'], 'failed')

    def test_nothing_matched_in_any_league_is_a_source_failure_not_a_pile_of_holds(self):
        calendar = [self.f, fixture('g4', 'Napoli', 'Parma', day(3), SA)]
        for label, feeds in (('empty feeds', {}), ('rows that match nothing', {PL: [row('id1', 'Arsenal', 'Chelsea', day(3) + timedelta(hours=3))],
                                                                              SA: [row('id4', 'Napoli', 'Parma', day(3) + timedelta(hours=3), SA)]})):
            with self.subTest(label):
                self.api.feeds = feeds
                self.fatal('No provider fixture matched the results calendar in any league', calendar=calendar)
        self.assertEqual(json.loads((self.state / 'collection.json').read_text())['leaguesWaiting'], [PL, SA])
        # One league waiting is a fixture-level matter: held, not fatal.
        _, report = self.collect(archive(), [self.f], API())
        self.assertEqual(report['publicHolds']['held'], 1)
        # Once held, the same quiet week never turns fatal, even with a second league now waiting but known.
        self.collect(archive(), [self.f], API({SA: [row('id4', 'Napoli', 'Parma', day(3), SA)]}, {'id4': priced('id777', day(3))}),
                     now=NOW + timedelta(hours=1))
        _, report = self.collect(archive(), calendar, API(), now=NOW + timedelta(hours=2))
        self.assertEqual(report['publicHolds']['held'], 2)

    def test_malformed_published_hold_metadata(self):
        self.fatal('Published hold metadata is malformed', public={'held': 1, 'matches': [{'league': PL}]})

    def test_accounting_that_does_not_balance_is_fatal(self):
        key = w.fixture_key(self.f)
        run = holds.Run({key: self.f}, {}, w.TOURNAMENTS, NOW - timedelta(days=14), NOW)
        with self.assertRaisesRegex(ValueError, 'does not balance'):
            run.accounting()
        run.add(key, 'id1')
        with self.assertRaisesRegex(ValueError, 'accounting conflict'):
            run.hold_fixture(key, self.f, 'provider-missing', 'x')
        run.feed(PL, 'ok', rows=2)
        run.row(PL, 'added', 'id1')
        with self.assertRaisesRegex(ValueError, 'Provider row accounting does not balance'):
            run.accounting()


class Lifecycle(Case):
    def test_hold_then_fix_adds_once_keeps_first_seen_and_third_run_is_a_no_op(self):
        f = fixture('g2', 'Liverpool', 'Everton', day(4))
        api = API({PL: [row('id2', 'Liverpool Reds XI', 'Everton', day(4))]}, {'id2': priced('id2', day(4))})
        old = archive()
        first, report = self.collect(old, [f], api)
        self.assertEqual(first, old)
        self.assertEqual(api.price_requests(), [])
        public = report['publicHolds']
        # The alias is reviewed. Second run, a week later.
        self.aliases = {PL: {'liverpoolredsxi': 'Liverpool'}}
        week = NOW + timedelta(days=7)
        second, report = self.collect(first, [f], api, now=week, public=public)
        self.assertEqual([r[0] for r in second['fixtures']], ['papi-id2'])
        entry = self.entry(self.fx(f))
        self.assertEqual((entry['state'], entry['firstSeen'], entry['code']),
                         ('pending', NOW.isoformat(), 'provider-missing'))
        self.assertEqual(self.entry('pr:premier-league:id2')['resolution'], 'row-cleared')
        self.assertIsNone(report['publicHolds'])
        self.assertTrue(report['publicHoldsChanged'])
        # Third run on the published archive: nothing changes, same version, hold closed for good.
        third, report = self.collect(second, [f], api, now=week + timedelta(days=7), through='2026-11-06')
        self.assertEqual(json.dumps(third), json.dumps(second))
        self.assertEqual((report['newMatches'], report['holdStatus'], report['publicHoldsChanged']), (0, 'closed', False))
        entry = self.entry(self.fx(f))
        self.assertEqual((entry['state'], entry['resolution'], entry['firstSeen']), ('resolved', 'published', NOW.isoformat()))
        self.assertEqual(api.price_requests(), ['id2'])  # Exactly one request across three runs.

    def test_repeat_run_with_no_new_evidence_changes_nothing(self):
        calendar = [fixture('g1', 'Arsenal', 'Chelsea', day(3)), fixture('g2', 'Liverpool', 'Everton', day(4))]
        api = API({PL: [row('id1', 'Arsenal', 'Chelsea', day(3))]}, {'id1': priced('id1', day(3))})
        first, report = self.collect(archive(), calendar, api)
        public = report['publicHolds']
        second, report = self.collect(first, calendar, api, now=NOW + timedelta(hours=1), public=public)
        self.assertEqual(json.dumps(second), json.dumps(first))
        self.assertEqual((report['newMatches'], report['publicHoldsChanged']), (0, False))
        self.assertEqual(report['publicHolds'], public)
        entry = self.entry(self.fx(calendar[1]))
        self.assertEqual((entry['firstSeen'], entry['attempts']), (NOW.isoformat(), 2))
        self.assertEqual(api.price_requests(), ['id1'])

    def test_ordinary_addition_leaves_a_closed_ledger_once_published(self):
        f = fixture('g1', 'Arsenal', 'Chelsea', day(3))
        api = API({PL: [row('id1', 'Arsenal', 'Chelsea', day(3))]}, {'id1': priced('id1', day(3))})
        new, report = self.collect(archive(), [f], api)
        self.assertEqual((report['holdStatus'], report['publicHolds']), ('closed', None))
        self.assertEqual(self.ledger()['counts'], {'pending': 1})
        self.collect(new, [f], api, now=NOW + timedelta(days=7))
        self.assertEqual((self.ledger()['status'], self.ledger()['holds']), ('closed', []))

    def test_unpublished_addition_keeps_anchoring_the_window(self):
        # A dry run, or a publication that failed, must not let a held fixture drop out.
        f = fixture('g2', 'Liverpool', 'Everton', day(20))
        api = API({PL: []}, {'id2': priced('id2', day(20))})
        old = archive()
        _, report = self.collect(old, [f], api, through='2026-10-20')
        self.assertEqual(self.held(report), {(self.fx(f), 'provider-missing')})
        api.feeds[PL] = [row('id2', 'Liverpool', 'Everton', day(20))]
        added, report = self.collect(old, [f], api, now=NOW + timedelta(days=1), through='2026-11-09')
        self.assertEqual(report['newMatches'], 1)
        self.assertEqual(self.entry(self.fx(f))['state'], 'pending')
        # The addition never reached the published archive. Same old archive, later run.
        again, report = self.collect(old, [f], api, now=NOW + timedelta(days=2), through='2026-11-09')
        self.assertEqual(again, added)
        self.assertTrue(report['windowFollowsHold'])
        self.assertEqual(self.entry(self.fx(f))['state'], 'pending')
        self.assertEqual(api.price_requests(), ['id2'])  # Second pass came from the saved response.


class Window(Case):
    def test_hold_20_days_old_is_still_collected_after_through_moves_on(self):
        f = fixture('g2', 'Liverpool', 'Everton', day(20))
        api = API({PL: []}, {'id2': priced('id2', day(20))})
        _, report = self.collect(archive(), [f], api, through='2026-10-20')
        public = report['publicHolds']
        self.assertEqual(public['held'], 1)
        # A partial release moved `through` to yesterday. The strict window would now start 14 days back.
        api.feeds[PL] = [row('id2', 'Liverpool', 'Everton', day(20))]
        new, report = self.collect(archive(), [f], api, now=NOW + timedelta(days=1), through='2026-11-10', public=public)
        self.assertEqual([r[0] for r in new['fixtures']], ['papi-id2'])
        self.assertTrue(report['windowFollowsHold'])
        self.assertEqual(report['windowFrom'], '2026-10-21T00:00:00+00:00')
        self.assertEqual(report['windowBase'], (NOW + timedelta(days=1) - timedelta(days=14)).isoformat())

    def test_hold_40_days_old_is_aged_kept_and_does_not_stop_the_run(self):
        old_fixture = fixture('g2', 'Liverpool', 'Everton', day(20))
        api = API({PL: []}, {'id1': priced('id1', day(-17))})
        _, report = self.collect(archive(), [old_fixture], api, through='2026-10-20')
        public = report['publicHolds']
        later = NOW + timedelta(days=20)
        fresh = fixture('g1', 'Arsenal', 'Chelsea', day(-17))
        api.feeds[PL] = [row('id1', 'Arsenal', 'Chelsea', day(-17)), row('id2', 'Liverpool', 'Everton', day(20))]
        new, report = self.collect(archive(), [old_fixture, fresh], api, now=later, through='2026-11-25', public=public)
        self.assertEqual([r[0] for r in new['fixtures']], ['papi-id1'])  # The run goes on for everyone else.
        entry = self.entry(self.fx(old_fixture))
        self.assertEqual((entry['state'], entry['code'], entry['firstSeen']), ('aged', 'provider-missing', NOW.isoformat()))
        self.assertFalse(report['windowFollowsHold'])
        self.assertEqual(report['holds']['agedThisRun'], [self.fx(old_fixture)])
        self.assertEqual(report['publicHolds']['matches'][0]['state'], 'aged')
        self.assertEqual(report['holdStatus'], 'open')
        self.assertEqual(api.price_requests(), ['id1'])  # No request for the aged fixture.
        # Still aged and still counted a week later.
        _, report = self.collect(new, [old_fixture, fresh], api, now=later + timedelta(days=7), through='2026-11-27',
                                 public=report['publicHolds'])
        self.assertEqual(report['publicHolds']['held'], 1)
        # A reviewed backfill puts it in the archive: the aged hold closes on its own.
        backfilled = archive(*new['fixtures'], stored('manual-1', day(20).date().isoformat(), PL, 'Liverpool', 'Everton'))
        _, report = self.collect(backfilled, [old_fixture, fresh], api, now=later + timedelta(days=14), through='2026-11-27',
                                 public=report['publicHolds'])
        self.assertEqual(self.entry(self.fx(old_fixture))['resolution'], 'published')
        self.assertIsNone(report['publicHolds'])


class Quota(Case):
    def setUp(self):
        super().setUp()
        self.calendar = [fixture('g1', 'Arsenal', 'Chelsea', day(3)), fixture('g2', 'Liverpool', 'Everton', day(4)),
                         fixture('g3', 'Fulham', 'Brentford', day(5)), fixture('g4', 'Napoli', 'Parma', day(3), SA)]
        self.feeds = {PL: [row('id1', 'Arsenal', 'Chelsea', day(3)), row('id2', 'Liverpool', 'Everton', day(4)),
                           row('id3', 'Fulham', 'Brentford', day(5))], SA: [row('id4', 'Napoli', 'Parma', day(3), SA)]}
        self.prices = {f'id{n}': priced(f'id{n}', day(d)) for n, d in ((1, 3), (2, 4), (3, 5), (4, 3))}

    def test_provider_reports_allowance_exhausted_mid_run(self):
        # Decision under C9: what was verified before the stop is published; the rest is deferred.
        prices = {**self.prices, 'id2': RuntimeError('OddsPapi monthly request allowance exhausted')}
        api = API(self.feeds, prices)
        new, report = self.collect(archive(), self.calendar, api)
        self.assertEqual([r[0] for r in new['fixtures']], ['papi-id1'])
        self.assertEqual(api.log, [('fixtures', PL), ('price', 'id1'), ('price', 'id2')])  # Then it stops asking.
        self.assertEqual({code for _, code in self.held(report)}, {'quota-deferred'})
        self.assertEqual(report['quota'], {'before': 200, 'requestsThisRun': 3, 'exhausted': True, 'deferred': 3})
        self.assertEqual(report['holds']['byLeague'][SA]['feed'], 'not-requested')
        # Next month: the deferred fixtures are collected, the first is not requested again.
        api = API(self.feeds, self.prices)
        final, report = self.collect(new, self.calendar, api, now=NOW + timedelta(days=7), public=report['publicHolds'])
        self.assertEqual(len(final['fixtures']), 4)
        self.assertEqual(sorted(api.price_requests()), ['id2', 'id3', 'id4'])
        self.assertIsNone(report['publicHolds'])

    def test_counted_allowance_runs_out_before_the_provider_says_so(self):
        api = API(self.feeds, self.prices, quota=holds.QUOTA_FLOOR + 3)
        new, report = self.collect(archive(), self.calendar, api)
        self.assertEqual(sorted(r[0] for r in new['fixtures']), ['papi-id1', 'papi-id2'])
        self.assertEqual(api.log, [('fixtures', PL), ('price', 'id1'), ('price', 'id2')])
        self.assertEqual(report['quota']['deferred'], 2)
        self.assertEqual(api.quota_value - len(api.log), 20)

    def test_saved_prices_are_still_used_when_the_allowance_is_gone(self):
        api = API(self.feeds, self.prices)
        self.collect(archive(), self.calendar, api)  # Prices saved; pretend publication never happened.
        api = API(self.feeds, self.prices, quota=holds.QUOTA_FLOOR + 1)
        new, report = self.collect(archive(), self.calendar, api, now=NOW + timedelta(hours=2))
        self.assertEqual(sorted(r[0] for r in new['fixtures']), ['papi-id1', 'papi-id2', 'papi-id3'])
        self.assertEqual(api.price_requests(), [])
        self.assertEqual(report['holds']['byLeague'][SA]['feed'], 'not-requested')

    def test_price_source_down_stops_asking_after_three_failures(self):
        calendar = self.calendar[:3] + [fixture('g5', 'Chelsea', 'Fulham', day(6)), fixture('g6', 'Everton', 'Brentford', day(7))]
        feeds = {PL: self.feeds[PL] + [row('id5', 'Chelsea', 'Fulham', day(6)), row('id6', 'Everton', 'Brentford', day(7))]}
        down = RuntimeError('historical-odds returned HTTP 503')
        api = API(feeds, {f'id{n}': down for n in range(1, 7)})
        new, report = self.collect(archive(), calendar, api)
        self.assertEqual(new['fixtures'], [])
        self.assertEqual(len(api.price_requests()), holds.SOURCE_FAILURE_LIMIT)
        self.assertEqual({code for _, code in self.held(report)}, {'price-source-unavailable'})
        self.assertFalse(report['quota']['exhausted'])


class TerminalPriceHolds(Case):
    def setUp(self):
        super().setUp()
        self.f = fixture('g2', 'Liverpool', 'Everton', day(4))
        self.row = row('id2', 'Liverpool', 'Everton', day(4), updatedAt='2026-11-06T17:00:00Z')
        empty = {'fixtureId': 'id2', 'bookmakers': {}}
        self.api = API({PL: [self.row]}, {'id2': empty})

    def test_no_second_request_while_the_provider_row_is_unchanged(self):
        _, report = self.collect(archive(), [self.f], self.api)
        self.assertEqual(self.held(report), {(self.fx(self.f), 'price-not-validated')})
        for week in (1, 2, 3):
            _, report = self.collect(archive(), [self.f], self.api, now=NOW + timedelta(days=7 * week),
                                     public=report['publicHolds'])
            self.assertEqual(self.held(report), {(self.fx(self.f), 'price-not-validated')})
        self.assertEqual(self.api.price_requests(), ['id2'])
        entry = self.entry(self.fx(self.f))
        self.assertEqual((entry['attempts'], entry['skippedRequests'], entry['firstSeen']), (1, 3, NOW.isoformat()))

    def test_a_changed_provider_row_is_asked_once_more(self):
        _, report = self.collect(archive(), [self.f], self.api)
        self.api.feeds[PL] = [{**self.row, 'updatedAt': '2026-11-12T09:00:00Z'}]
        self.api.prices['id2'] = priced('id2', day(4))
        new, report = self.collect(archive(), [self.f], self.api, now=NOW + timedelta(days=7), public=report['publicHolds'])
        self.assertEqual(self.api.price_requests(), ['id2', 'id2'])
        self.assertEqual(report['newMatches'], 1)

    def test_league_outage_carries_the_hold_without_losing_its_terminal_state(self):
        _, report = self.collect(archive(), [self.f, fixture('g4', 'Napoli', 'Parma', day(3), SA)],
                                 API({PL: [self.row], SA: []}, self.api.prices))
        calendar = [self.f, fixture('g4', 'Napoli', 'Parma', day(3), SA)]
        outage = API({PL: RuntimeError('fixtures returned HTTP 503'), SA: []})
        _, report = self.collect(archive(), calendar, outage, now=NOW + timedelta(days=7), public=report['publicHolds'])
        entry = self.entry(self.fx(self.f))
        self.assertEqual((entry['code'], entry['attempts'], entry['carriedAt']),
                         ('price-not-validated', 1, (NOW + timedelta(days=7)).isoformat()))
        back = API({PL: [self.row], SA: []}, self.api.prices)
        _, report = self.collect(archive(), calendar, back, now=NOW + timedelta(days=14), public=report['publicHolds'])
        self.assertEqual(back.price_requests(), [])


class Durability(Case):
    def held_once(self):
        f = fixture('g2', 'Liverpool', 'Everton', day(20))
        api = API({PL: []}, {'id2': priced('id2', day(20))})
        _, report = self.collect(archive(), [f], api, through='2026-10-20')
        return f, api, report['publicHolds']

    def test_lost_state_directory_is_rebuilt_from_the_published_list(self):
        f, api, public = self.held_once()
        fresh = Path(self.tmp.name) / 'fresh-state'
        fresh.mkdir()
        api.feeds[PL] = [row('id2', 'Liverpool', 'Everton', day(20))]
        new, report = self.collect(archive(), [f], api, now=NOW + timedelta(days=1), through='2026-11-10',
                                   public=public, state=fresh)
        self.assertEqual(report['holds']['ledgerRebuilt'], 'missing')
        self.assertEqual([r[0] for r in new['fixtures']], ['papi-id2'])  # Still inside the window.
        entry = self.entry(self.fx(f), fresh)
        self.assertEqual(entry['firstSeen'], NOW.date().isoformat() + 'T00:00:00+00:00')
        self.assertTrue(entry['restored'])

    def test_lost_state_keeps_an_aged_match_on_the_public_list(self):
        f, api, public = self.held_once()
        public['matches'][0]['state'] = 'aged'
        fresh = Path(self.tmp.name) / 'fresh-state'
        fresh.mkdir()
        _, report = self.collect(archive(), [], api, now=NOW + timedelta(days=30), through='2026-12-05',
                                 public=public, state=fresh)
        self.assertEqual(report['publicHolds'], public)
        self.assertFalse(report['publicHoldsChanged'])

    def test_unreadable_ledger_is_kept_as_evidence_and_rebuilt(self):
        f, api, public = self.held_once()
        (self.state / holds.LEDGER).write_text('{"schema": 1, "holds": [{"id": ', encoding='utf-8')
        _, report = self.collect(archive(), [f], api, now=NOW + timedelta(days=1), through='2026-11-10', public=public)
        self.assertEqual(report['holds']['ledgerRebuilt'], 'unreadable')
        evidence = self.state / report['holds']['ledgerEvidence']
        self.assertEqual(evidence.read_text(encoding='utf-8'), '{"schema": 1, "holds": [{"id": ')
        self.assertEqual(self.held(report), {(self.fx(f), 'provider-missing')})
        self.assertEqual(report['publicHolds']['matches'][0]['since'], NOW.date().isoformat())

    def test_dry_run_that_closed_a_hold_early_is_corrected_by_the_published_list(self):
        f, api, public = self.held_once()
        ledger = self.ledger()
        ledger['holds'][0].update(state='resolved', resolution='no-longer-expected')
        (self.state / holds.LEDGER).write_text(json.dumps(ledger), encoding='utf-8')
        _, report = self.collect(archive(), [f], api, now=NOW + timedelta(days=1), through='2026-11-10', public=public)
        self.assertEqual(self.held(report), {(self.fx(f), 'provider-missing')})
        self.assertTrue(report['windowFollowsHold'])


class Release(Case):
    def release(self, module, root, old_manifest, index, **kwargs):
        (root / 'public/football-atlas').mkdir(parents=True, exist_ok=True)
        (root / 'src/data').mkdir(parents=True, exist_ok=True)
        with patch.object(module, 'ROOT', root):
            release, path = module.write_release(old_manifest, index, NOW, **kwargs)
        return release, (root / path).read_bytes(), (root / module.MANIFEST).read_bytes()

    def index(self):
        return archive(stored('papi-id1', '2026-11-07', PL, 'Arsenal', 'Chelsea'), stored('papi-id4', '2026-11-08', SA, 'Napoli', 'Parma'))

    def test_public_metadata_never_changes_archive_bytes_or_version(self):
        root = Path(self.tmp.name)
        summary = {'held': 1, 'matches': [{'date': '2026-11-01', 'league': PL, 'home': 'Liverpool', 'away': 'Everton',
                                           'since': '2026-11-03', 'state': 'held'}]}
        plain, plain_bytes, plain_manifest = self.release(w, root / 'a', {'title': 'x'}, self.index())
        empty, empty_bytes, empty_manifest = self.release(w, root / 'b', {'title': 'x'}, self.index(), holds_public={})
        held, held_bytes, _ = self.release(w, root / 'c', {'title': 'x'}, self.index(), holds_public=summary)
        self.assertEqual(plain_bytes, empty_bytes)
        self.assertEqual(plain_bytes, held_bytes)
        self.assertEqual(plain_manifest, empty_manifest)  # C5: no holds, no trace in the manifest.
        self.assertEqual(plain['version'], held['version'])
        self.assertEqual(held['through'], '2026-11-08')  # Unchanged meaning: last priced date.
        self.assertEqual(held['historyHolds'], {**summary, 'completeThrough': '2026-10-31'})
        self.assertNotIn('historyHolds', plain)

    def test_complete_through_never_runs_past_through(self):
        summary = {'held': 1, 'matches': [{'date': '2026-11-20', 'league': PL, 'home': 'Liverpool', 'away': 'Everton',
                                           'since': '2026-11-22', 'state': 'held'}]}
        held, _, _ = self.release(w, Path(self.tmp.name), {}, self.index(), holds_public=summary)
        self.assertEqual(held['historyHolds']['completeThrough'], '2026-11-08')

    def test_resolved_holds_leave_the_manifest_and_legacy_callers_change_nothing(self):
        root = Path(self.tmp.name)
        earlier = {'title': 'x', 'historyHolds': {'held': 1, 'matches': [], 'completeThrough': '2026-10-31'}}
        cleared, _, _ = self.release(w, root / 'a', earlier, self.index(), holds_public={})
        self.assertNotIn('historyHolds', cleared)
        legacy_call, _, _ = self.release(w, root / 'b', earlier, self.index())
        self.assertEqual(legacy_call['historyHolds'], earlier['historyHolds'])
        review_only, _, _ = self.release(w, root / 'c', {}, self.index(), holds_public={'held': 0, 'matches': [], 'review': 1})
        self.assertEqual(review_only['historyHolds'], {'held': 0, 'matches': [], 'review': 1})

    def test_zero_holds_is_byte_identical_to_the_strict_collector(self):
        folder = os.environ.get('F13_BASELINE_SCRIPTS')
        if not folder:
            self.skipTest('Set F13_BASELINE_SCRIPTS to the folder holding the pre-F13 football_atlas_weekly.py')
        spec = importlib.util.spec_from_file_location('football_atlas_weekly_strict', Path(folder) / 'football_atlas_weekly.py')
        strict = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(strict)
        self.assertFalse(hasattr(strict, 'holds'))
        calendar = [fixture('g1', 'Arsenal', 'Chelsea', day(3)), fixture('g2', 'Liverpool', 'Everton', day(4)),
                    fixture('g4', 'Napoli', 'Parma', day(3), SA), fixture('g0', 'Fulham', 'Brentford', day(9))]
        feeds = {PL: [row('id1', 'Arsenal', 'Chelsea', day(3)), row('id2', 'Liverpool', 'Everton', day(4),
                                                                    trueStartTime=(day(4) + timedelta(minutes=3)).isoformat()),
                      row('id0', 'Fulham', 'Brentford', day(9)), {**row('id8', 'Roma', 'Lazio', day(1)), 'statusId': 1}],
                 SA: [row('id4', 'Napoli', 'Parma', day(3), SA)]}
        prices = {'id1': priced('id1', day(3)), 'id2': priced('id2', day(4)), 'id4': priced('id4', day(3), 'bet365')}
        old = archive(stored('papi-id0', day(9).date().isoformat(), PL, 'Fulham', 'Brentford'))
        manifest = {'title': 'Football Atlas', 'through': '2026-11-01', 'version': 'aaaaaaaaaaaa', 'indexUrl': '/football-atlas/index-aaaaaaaaaaaa.json'}
        outputs = []
        for module, name in ((strict, 'strict'), (w, 'candidate')):
            root = Path(self.tmp.name) / name
            state = root / 'state'
            state.mkdir(parents=True)
            api = API(feeds, prices)
            with patch.object(w.legacy, 'calendar', return_value=copy.deepcopy(calendar)), \
                    patch.object(w.legacy, 'read', side_effect=lambda path: {}), patch('builtins.print'):
                first, report = module.collect(copy.deepcopy(old), manifest, state, NOW, api)
                kwargs = {'holds_public': report.get('publicHolds') or {}} if module is w else {}
                release, index_bytes, manifest_bytes = self.release(module, root, manifest, first, **kwargs)
                # A second, unchanged week on the new archive.
                second, again = module.collect(first, release, state, NOW + timedelta(days=1), API(feeds, prices))
            outputs.append((json.dumps(first).encode(), index_bytes, manifest_bytes, release['version'],
                            json.dumps(second).encode(), report['newMatches'], again['newMatches'], api.log,
                            {k: report[k] for k in ('windowFrom', 'windowTo', 'leagues', 'provenance', 'priceSources')
                             if k != 'leagues'}))
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(outputs[1][5:7], (3, 0))
        self.assertEqual(hashlib.sha256(outputs[1][1]).hexdigest()[:12], outputs[1][3])


class Main(Case):
    """The two changed lines in main(), with every network, git and publish step faked."""

    def setUp(self):
        super().setUp()
        self.root = Path(self.tmp.name) / 'checkout'
        (self.root / 'public/football-atlas').mkdir(parents=True)
        (self.root / 'src/data').mkdir(parents=True)
        self.index = archive(stored('papi-id1', '2026-11-07', PL, 'Arsenal', 'Chelsea'))
        payload = json.dumps(self.index, ensure_ascii=False, separators=(',', ':')).encode()
        self.version = hashlib.sha256(payload).hexdigest()[:12]
        (self.root / f'public/football-atlas/index-{self.version}.json').write_bytes(payload)
        self.manifest = {'version': self.version, 'indexUrl': f'/football-atlas/index-{self.version}.json', 'through': '2026-11-07'}
        (self.root / w.MANIFEST).write_text(json.dumps(self.manifest), encoding='utf-8')
        self.summary = {'held': 1, 'matches': [{'date': '2026-11-05', 'league': PL, 'home': 'Liverpool', 'away': 'Everton',
                                                'since': '2026-11-10', 'state': 'held'}]}
        managers = types.ModuleType('manager_atlas_weekly')
        managers.refresh_or_retain = lambda state: {'added': 0, 'manifest': {'version': 'm1', 'indexUrl': '/m'}, 'changed': False,
                                                    'paths': [], 'previous': '/m'}
        board = types.ModuleType('atlas_fixture_board')
        board.refresh = lambda state: {'report': {'version': 'b1'}, 'changed': False, 'paths': []}
        modules = patch.dict(sys.modules, {'manager_atlas_weekly': managers, 'atlas_fixture_board': board})
        modules.start()
        self.addCleanup(modules.stop)

    def report(self, new_matches, changed, public):
        return {'newMatches': new_matches, 'publicHoldsChanged': changed, 'publicHolds': public, 'status': 'validated'}

    def main(self, mode, collect, **extra):
        commands = []
        helper = types.SimpleNamespace(
            run=lambda args, cwd=None, **kwargs: commands.append(args) or '',
            fetch=lambda url: f'/football-atlas/index-{self.version}.json {self.version} m1 b1'.encode())
        patches = [patch.object(w, 'ROOT', self.root), patch.object(w, 'collect', **collect),
                   patch.object(w.legacy, 'load_module', return_value=helper), patch.object(w, 'synchronize_release'),
                   patch.object(w, 'stage_release'), patch.object(w, 'push_release'), patch.object(w, 'publish'),
                   patch.object(w, 'recover_fixture_board'), patch.object(sys, 'argv', ['weekly', '--state-directory', str(self.state), mode]),
                   patch.dict(os.environ, {'ODDSPAPI_API_KEY': 'test-only-key', 'VERCEL_TOKEN': 'test-only-token'}),
                   patch('builtins.print')]
        started = [p.start() for p in patches]
        try:
            w.main()
        finally:
            for p in reversed(patches):
                p.stop()
        return {'commands': commands, 'stage': started[4], 'publish': started[6], 'recover': started[7]}

    def manifest_now(self):
        return json.loads((self.root / w.MANIFEST).read_text(encoding='utf-8'))

    def test_publish_writes_a_changed_held_list_in_a_week_with_no_additions(self):
        seen = self.main('--publish', {'return_value': (self.index, self.report(0, True, self.summary))})
        release = self.manifest_now()
        self.assertEqual(release['historyHolds'], {**self.summary, 'completeThrough': '2026-11-04'})
        self.assertEqual(release['version'], self.version)  # Same archive, same version, nothing removed.
        self.assertEqual(release['through'], '2026-11-07')
        self.assertTrue((self.root / f'public/football-atlas/index-{self.version}.json').exists())
        self.assertFalse(any(args[:2] == ['git', 'rm'] for args in seen['commands']))
        staged = seen['stage'].call_args.args[2]
        self.assertEqual(staged, {w.MANIFEST.as_posix(), f'public/football-atlas/index-{self.version}.json'})
        seen['publish'].assert_called_once()

    def test_publish_leaves_the_manifest_alone_when_nothing_changed(self):
        before = (self.root / w.MANIFEST).read_bytes()
        seen = self.main('--publish', {'return_value': (self.index, self.report(0, False, None))})
        self.assertEqual((self.root / w.MANIFEST).read_bytes(), before)
        seen['stage'].assert_not_called()
        seen['publish'].assert_not_called()

    def test_publish_clears_the_held_list_once_resolved(self):
        (self.root / w.MANIFEST).write_text(json.dumps({**self.manifest, 'historyHolds': self.summary}), encoding='utf-8')
        self.main('--publish', {'return_value': (self.index, self.report(0, True, None))})
        self.assertNotIn('historyHolds', self.manifest_now())

    def test_dry_run_validates_with_the_held_list(self):
        self.main('--dry-run', {'return_value': (self.index, self.report(0, True, self.summary))})
        self.assertEqual(self.manifest_now()['historyHolds']['held'], 1)
        self.assertEqual(json.loads((self.state / 'publish-status.json').read_text())['status'], 'dry-run-passed')

    def test_fatal_collection_still_restores_the_fixture_board_and_writes_no_archive(self):
        before = (self.root / w.MANIFEST).read_bytes()
        with patch.object(w, 'write_release') as writer, self.assertRaises(SystemExit):
            seen = self.main('--dry-run', {'side_effect': ValueError('Duplicate existing fixture identity')})
        writer.assert_not_called()
        self.assertEqual((self.root / w.MANIFEST).read_bytes(), before)
        status = json.loads((self.state / 'publish-status.json').read_text())
        self.assertEqual(status['status'], 'failed')
        self.assertIn('Duplicate existing fixture identity', status['error'])

    def test_recovery_is_called_once_on_a_fatal_collection(self):
        recover = []
        with patch.object(w, 'ROOT', self.root), patch.object(w, 'collect', side_effect=ValueError('Incomplete calendar')), \
                patch.object(w, 'recover_fixture_board', side_effect=lambda *a, **k: recover.append(k)), \
                patch.object(sys, 'argv', ['weekly', '--state-directory', str(self.state), '--dry-run']), \
                patch.dict(os.environ, {'ODDSPAPI_API_KEY': 'test-only-key'}), patch('builtins.print'), \
                self.assertRaises(SystemExit):
            w.main()
        self.assertEqual(recover, [{'dry_run': True}])


class Board(unittest.TestCase):
    """Fixture board carries the held count only while something is held."""

    def refresh(self, release_extra):
        import atlas_fixture_board as fb
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / 'private-state'
            files = {'src/data/football-atlas-release.json': {'indexUrl': '/f.json', 'version': 'f', 'through': '2026-09-20', **release_extra},
                     'src/data/manager-atlas-release.json': {'indexUrl': '/m.json', 'version': 'm', 'through': '2026-09-20'},
                     'public/f.json': {'teams': [], 'leagues': [], 'fixtures': [], 'crests': {}},
                     'public/m.json': {'columns': [], 'rows': []},
                     'scripts/config/football-atlas-clubs.json': {},
                     'scripts/config/manager-atlas-identities.json': {'managers': []},
                     'scripts/config/manager-fotmob-identities.json': {},
                     'public/manager-atlas/portraits.json': {}}
            for name, data in files.items():
                fb.atomic(root / name, data)
            moment = datetime(2026, 9, 22, 18, tzinfo=UTC)
            for identity in fb.LEAGUES.values():
                fb.atomic(state / f'fixture-board/provider/leagues-{identity}.json', {'checkedAt': moment.isoformat(),
                          'payload': {'details': {'id': identity}, 'fixtures': {'allMatches': [{'status': {'finished': True}}] * 200}}})
            with patch.object(fb, 'ROOT', root), patch.object(fb.requests, 'get') as request:
                result = fb.refresh(state, offline=True, now=moment)
                request.assert_not_called()
            return result['report']['version'], fb.read(root / 'src/data/atlas-fixtures.json')

    def test_board_is_unchanged_without_holds_and_honest_with_them(self):
        plain_version, plain = self.refresh({})
        empty_version, empty = self.refresh({'historyHolds': {'held': 0, 'matches': [], 'review': 1}})
        held_version, held = self.refresh({'historyHolds': {'held': 2, 'matches': [], 'completeThrough': '2026-09-12'}})
        self.assertEqual((plain_version, plain), (empty_version, empty))
        self.assertNotIn('footballHeld', plain)
        self.assertNotEqual(held_version, plain_version)
        self.assertEqual((held['footballHeld'], held['footballCompleteThrough'], held['footballThrough']),
                         (2, '2026-09-12', '2026-09-20'))


if __name__ == '__main__':
    unittest.main()
