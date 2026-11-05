"""Real 5 November regional-feed regression; no network or Telegram requests."""
import copy
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import moviodds_prices as source
from scripts.tests.test_moviodds_prices import load
import goalkeeper_price_selection as prices

capture = load('goalkeeper-saves-capture')
shadow = load('goalkeeper-saves-shadow')
alerts = load('goalkeeper-saves-alerts')


class GoalkeeperRegions(unittest.TestCase):
    def setUp(self):
        self.raw = json.loads((Path(__file__).parent/'fixtures/moviodds-gk-regions.json').read_text())
        self.now = datetime(2026, 11, 5, 23, 6, 10, tzinfo=timezone.utc)
        self.target = {'id':71945404, 'home':'Venezia FC', 'away':'Udinese Calcio',
                       'date':'2026-11-06T19:45:00Z', 'league':{'slug':'italy-serie-a'}}

    def response(self, data):
        r = Mock()
        r.iter_content.return_value = [json.dumps(data).encode()]
        return r

    def test_default_board_empty_but_com_has_verified_okoye_225(self):
        au, _ = source.normalize(self.raw['com.au'], 'soccer', self.now, targets=[self.target])
        com, _ = source.normalize(self.raw['com'], 'soccer', self.now, targets=[self.target])
        self.assertEqual(au, [])
        rows = capture.extract_rows(com, {}, bookmaker_name='Bet365', captured_at='wrong', capture_mode='publication')
        okoye = next(r for r in rows if r['player']=='Maduka Okoye' and r['line']=='3.5')
        self.assertEqual(float(okoye['odds_decimal']), 2.25)
        self.assertEqual(okoye['captured_at'], '2026-11-05T23:04:33.219399259Z')
        market = com[0]['bookmakers']['Bet365'][0]
        self.assertEqual(market['source_site'], 'com')
        self.assertIn('&site=com', market['source_url'])

    def test_verified_alaves_alias_still_requires_exact_fixture(self):
        raw = self.raw['alaves']
        now = datetime.fromisoformat(raw['server_time'].replace('Z', '+00:00'))
        target = dict(id=72478700, home='Sevilla FC', away='Deportivo Alaves',
                      date='2026-11-06T20:00:00Z', league={'name':'Spain - LaLiga'})
        events, _ = source.normalize(raw, 'soccer', now, targets=[target])
        self.assertEqual(events[0]['id'], 72478700)
        self.assertEqual(source.goalkeeper_coverage(raw, [target], events, now)[0]['status'], 'CAPTURED')
        for changed in [dict(away='Alaves B'), dict(date='2026-11-06T20:01:00Z'),
                        dict(home='Deportivo Alaves', away='Sevilla FC')]:
            self.assertEqual(source.normalize(raw, 'soccer', now, targets=[{**target, **changed}])[0], [])

    def test_gk_route_pins_com_and_retains_grosvenor(self):
        other = [{**self.target, 'bookmakers':{'Grosvenor':[{'name':'Goalkeeper Saves Away'}]}}]
        get = Mock(return_value=self.response(self.raw['com']))
        with patch.object(source, 'datetime') as clock:
            clock.now.return_value = self.now
            clock.fromisoformat.side_effect = datetime.fromisoformat
            result, receipt = source.merge_football(other, [self.target], get=get, force=True)
        self.assertEqual(get.call_count, 1)
        self.assertEqual(get.call_args.kwargs['params']['site'], 'com')
        self.assertEqual(result[0]['bookmakers']['Grosvenor'], other[0]['bookmakers']['Grosvenor'])
        self.assertEqual(receipt['source_site'], 'com')
        self.assertEqual(receipt['goalkeeper_coverage_status'], 'COMPLETE')
        self.assertEqual(receipt['goalkeeper_fixture_coverage'][0]['quote_count'], 10)

    def test_unconfirmed_com_response_does_not_fall_back_to_au(self):
        get = Mock(return_value=self.response(self.raw['com.au']))
        events, receipt = source.merge_football([], [self.target], get=get, force=True)
        self.assertEqual(events, [])
        self.assertEqual(receipt['status'], 'SOURCE_FAILED')
        self.assertEqual(get.call_count, 1)

    def test_every_shared_collector_explicitly_requests_com(self):
        for sport in ('soccer', 'tennis'):
            get = Mock(return_value=self.response(self.raw['com']))
            source.download(sport, get=get)
            self.assertEqual(get.call_args.kwargs['params']['site'], 'com')
            get = Mock(return_value=self.response(self.raw['com.au']))
            with self.assertRaises(ValueError):
                source.download(sport, get=get)

    def test_count_market_group_filter_uses_same_verified_region(self):
        get = Mock(return_value=self.response(self.raw['com']))
        source.download('soccer', get=get, groups={'50532':(), '10235':()})
        self.assertEqual(get.call_args.kwargs['params'],
                         {'sport':'soccer','groups':'50532,10235','links':'1','site':'com'})

    def test_fixture_heartbeat_cannot_revive_missing_or_stale_gk_market(self):
        au = self.raw['com.au']
        coverage = source.goalkeeper_coverage(au, [self.target], [], self.now)
        self.assertEqual(coverage[0]['status'], 'NO_GK_MARKET_IN_FEED')
        com = copy.deepcopy(self.raw['com'])
        com['matches'][0]['polled_at'] = self.now.isoformat()
        com['matches'][0]['group_status']['177703']['polled_at'] = '2026-11-05T22:00:00Z'
        events, _ = source.normalize(com, 'soccer', self.now, targets=[self.target])
        self.assertEqual(events, [])
        self.assertEqual(source.goalkeeper_coverage(com, [self.target], events, self.now)[0]['status'], 'STALE_OR_MISSING_GK_POLL')

    def test_missing_fixture_reported_independently_of_working_fixture(self):
        missing = {**self.target, 'id':2, 'date':'2026-11-07T19:45:00Z'}
        get = Mock(return_value=self.response(self.raw['com']))
        with patch.object(source, 'datetime') as clock:
            clock.now.return_value = self.now
            clock.fromisoformat.side_effect = datetime.fromisoformat
            _, receipt = source.merge_football([], [self.target, missing], get=get, force=True)
        self.assertEqual(receipt['goalkeeper_coverage_status'], 'INCOMPLETE')
        self.assertEqual([r['status'] for r in receipt['goalkeeper_fixture_coverage']], ['CAPTURED','FIXTURE_NOT_FOUND'])

    def test_exact_prices_select_225_and_do_not_resend_existing_205(self):
        base = dict(event_id='71945404', goalkeeper='Maduka Okoye', line='3.5', side='over',
                    fair_odds='1.894', model_probability='0.527967',
                    captured_at=self.now.isoformat(), created_at=self.now.isoformat(),
                    generated_at=self.now.isoformat(), kickoff_at=self.target['date'],
                    candidate_status='eligible_shadow', selection_policy='near_even_value_v2', status='pending',
                    lineup_status='predicted_starter', home_team=self.target['home'], away_team=self.target['away'],
                    blockers='', strongest_for_fixture='no')
        old = dict(base, bookmaker='Grosvenor', odds_decimal='2.05', edge='0.082332',
                   contract_scope='team_goalkeeper_away', identity_basis='same_fixture_lineup_side',
                   signal_id='grosvenor|71945404|maduka okoye|3.5|over')
        new = dict(base, bookmaker='Bet365', odds_decimal='2.25', edge='0.187926',
                   captured_at='2026-11-05T23:04:33.219399259Z',
                   contract_scope='named_player', identity_basis='bookmaker_named_player',
                   signal_id='71945404|maduka okoye|3.5|over')
        offers = [old, new]
        shadow.mark_primary_selections(offers)
        self.assertEqual([r['bookmaker'] for r in offers if r['strongest_for_fixture']=='yes'], ['Bet365'])
        self.assertEqual(prices.alert_price_check(old, offers, self.now)[0], 'better_bookmaker_price_available')
        reason, comparison = prices.alert_price_check(new, offers, self.now)
        self.assertIsNone(reason)
        self.assertEqual([(r['bookmaker'], r['odds']) for r in comparison], [('Bet365',2.25),('Grosvenor',2.05)])
        state = {'signals':{old['signal_id']:{'status':'sent', 'signal':copy.deepcopy(old)}}}
        before = copy.deepcopy(state['signals'])
        self.assertEqual(alerts.claim([new], state, 'repair:1', self.now, offers), 0)
        self.assertEqual(state['signals'], before)


if __name__ == '__main__':
    unittest.main()
