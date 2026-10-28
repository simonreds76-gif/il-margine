import copy
import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest
from unittest.mock import patch

import requests
import tennis_grosvenor as g

ROOT = Path(__file__).resolve().parents[2]


def module(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), ROOT / 'scripts' / f'{name}.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class GrosvenorTests(unittest.TestCase):
    def setUp(self):
        self.raw = json.loads((Path(__file__).parent / 'fixtures/grosvenor-aces.json').read_text())
        self.stamp = '2026-10-28T11:00:00Z'

    def parse(self):
        return g.normalize(self.raw, 1029614433, self.stamp)

    def test_real_payload_contracts_and_decimal_scaling(self):
        event = self.parse()
        common = module('tennis-props-scrape-bet365')
        rows = [r for m in event['bookmakers']['Grosvenor'] for r in common.extract_rows(event, 'Grosvenor', m, self.stamp)]
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]['market'], rows[0]['line'], rows[0]['over_odds'], rows[0]['under_odds']),
                         ('match_aces', '21.5', '1.5300', '2.3000'))
        self.assertIn('2709213195', rows[0]['raw_market_json'])
        most = module('tennis-most-aces-capture').extract_rows([event], self.stamp, common)
        self.assertEqual(len(most), 1)
        self.assertEqual([most[0][k] for k in ('player1_odds', 'draw_odds', 'player2_odds')], ['2.5000', '11.5000', '1.6800'])
        self.assertEqual(most[0]['bookmaker'], 'Grosvenor')
        self.assertIn('grosvenorcasinos.com', most[0]['source_url'])

    def test_live_past_unknown_and_wrong_event_are_rejected(self):
        original = copy.deepcopy(self.raw)
        for change in ({'state': 'STARTED'}, {'start': '2026-10-28T10:59:59Z'}, {'state': 'UNKNOWN'}, {'id': 123}):
            self.raw = copy.deepcopy(original)
            self.raw['events'][0].update(change)
            self.assertIsNone(self.parse())

    def test_only_full_match_open_complete_contracts(self):
        original = copy.deepcopy(self.raw)
        cases = ('first_set', 'missing_draw', 'wrong_player', 'suspended', 'line_mismatch', 'future_change', 'decimal_not_integer')
        for case in cases:
            self.raw = copy.deepcopy(original)
            total, most = self.raw['betOffers']
            if case == 'first_set':
                for o in self.raw['betOffers']: o['criterion']['englishLabel'] += ' - Set 1'
                self.assertEqual(self.parse()['bookmakers']['Grosvenor'], [])
                continue
            if case == 'missing_draw': most['outcomes'].pop(1)
            if case == 'wrong_player': most['outcomes'][0]['participant'] = 'Someone Else'
            if case == 'suspended': most['outcomes'][1]['status'] = 'SUSPENDED'
            if case == 'future_change': most['outcomes'][0]['changedDate'] = '2026-10-28T15:00:00Z'
            if case == 'decimal_not_integer': most['outcomes'][0]['odds'] = 2.5
            if case == 'line_mismatch': total['outcomes'][0]['line'] = 22500
            markets = self.parse()['bookmakers']['Grosvenor']
            self.assertEqual(len(markets), 1, case)
            self.assertEqual(markets[0]['name'], 'Most Aces' if case == 'line_mismatch' else 'Total Aces')

    def test_public_request_failure_is_isolated(self):
        def fail(*a, **k): raise requests.HTTPError('blocked')
        events, receipt = g.capture(get=fail)
        self.assertEqual(events, [])
        self.assertEqual(receipt['requests'], 1)
        self.assertEqual(receipt['status'], 'NO_VERIFIED_MARKETS')

    def test_request_budget_and_singles_scope(self):
        now = datetime.now(timezone.utc)
        e = dict(self.raw['events'][0], start=(now + timedelta(hours=1)).isoformat())
        catalog = {'events': [{'event': dict(e, id=i)} for i in range(20)]}
        class Response:
            def __init__(self, data): self.data = data
            def raise_for_status(self): pass
            def json(self): return self.data
        calls = []
        def get(url, **kwargs):
            calls.append(url)
            return Response(catalog if 'listView' in url else {'events': []})
        _, receipt = g.capture(max_events=999, get=get)
        self.assertEqual(len(calls), 13)
        self.assertEqual(receipt['eligible_events'], 20)
        self.assertFalse(g.eligible(dict(e, homeName='One / Two'), now))

    def test_forward_registration_identity_and_dedupe(self):
        shadow = module('tennis-most-aces-shadow')
        tests = module('tests/test_tennis_most_aces_shadow')
        old = tests.MostAcesShadowTests()
        now = datetime.now(timezone.utc)
        board = dict(old.board(), date=now.date().isoformat(), generated_at_utc=now.isoformat())
        capture = dict(old.capture(), bookmaker='Grosvenor', date=board['date'], tournament=board['tournament'],
                       capture_ts=now.isoformat(), match_start_utc=(now + timedelta(hours=1)).isoformat())
        ledger = []
        self.assertEqual(shadow.register([board], [capture], ledger), 1)
        self.assertEqual(shadow.register([board], [capture], ledger), 0)
        self.assertTrue(ledger[0]['observation_id'].startswith('grosvenor|'))
        self.assertNotEqual(shadow.market_key(capture), shadow.market_key(dict(capture, bookmaker='BetMGM')))
        self.assertIsNone(shadow.registration_row(board, dict(capture, match_start_utc=(now-timedelta(minutes=1)).isoformat())))
        self.assertIsNone(shadow.registration_row(board, dict(capture, capture_ts=(now-timedelta(hours=1)).isoformat())))
        self.assertIsNone(shadow.registration_row(dict(board, generated_at_utc=(now-timedelta(days=1)).isoformat()), capture))
        self.assertIsNone(shadow.registration_row(board, dict(capture, tournament='Another event')))
        self.assertEqual(shadow.update_closes(ledger, [dict(capture, bookmaker='BetMGM')]), 0)

    def test_grosvenor_exact_result_and_retirement_hold(self):
        shadow = module('tennis-most-aces-shadow')
        tests = module('tests/test_tennis_most_aces_shadow')
        old = tests.MostAcesShadowTests()
        row = shadow.registration_row(old.board(), old.capture())
        row['bookmaker'] = 'Grosvenor'
        match = dict(tourney_name='Washington', tourney_date='20260729', winner_name='Player One', loser_name='Player Two', w_ace='7', l_ace='3', score='6-4 6-4')
        key = shadow.pair_key('Player One', 'Player Two')
        self.assertEqual(shadow.settle([row], {key: [match]}), 0)  # old week-date source is not enough
        retired = dict(match, score='6-4 2-1 RET')
        self.assertEqual(shadow.settle([row], {}, direct_index={key: [retired]}), 0)
        self.assertIn('contract_review', row['settlement_note'])
        self.assertEqual(shadow.settle([row], {}, direct_index={key: [dict(match, tourney_name='Elsewhere')]}), 0)
        self.assertEqual(shadow.settle([row], {}, direct_index={key: [dict(match, tourney_date='20260728')]}), 0)
        future = dict(row, match_start_utc=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat())
        self.assertEqual(shadow.settle([future], {}, direct_index={key: [match]}), 0)
        self.assertEqual(shadow.settle([row], {}, direct_index={key: [match]}), 1)
        self.assertEqual((row['outcome'], row['result'], row['pnl']), ('P1', 'win', '0.800'))


if __name__ == '__main__': unittest.main()
