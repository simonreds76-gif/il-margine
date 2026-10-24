import copy
import csv
from datetime import datetime, timedelta, timezone
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import goalkeeper_price_selection as prices

def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name+'.py'))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module

shadow = load('goalkeeper-saves-shadow')
alerts = load('goalkeeper-saves-alerts')


class BestPrices(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)

    def row(self, book='Bet365', odds=2.5, **changes):
        r = dict(event_id='72221342', goalkeeper='Caoimhin Kelleher', line='2.5', side='over',
                 bookmaker=book, odds_decimal=str(odds), fair_odds='1.86', edge='.2', model_probability='.5376',
                 captured_at=self.now.isoformat(), created_at=self.now.isoformat(), generated_at=self.now.isoformat(),
                 kickoff_at=(self.now+timedelta(hours=20)).isoformat(), candidate_status='eligible_shadow',
                 strongest_for_fixture='yes', selection_policy='near_even_value_v2', status='pending',
                 lineup_status='predicted_starter', home_team='A', away_team='Brentford', blockers='',
                 contract_scope='named_player', identity_basis='bookmaker_named_player')
        if book == 'Kambi':
            r.update(contract_scope='team_goalkeeper_away', identity_basis='same_event_bet365_and_lineup_side')
        r.update(changes)
        r['signal_id'] = (book.lower()+'|' if book != 'Bet365' else '')+f"{r['event_id']}|{r['goalkeeper']}|{r['line']}|{r['side']}"
        return r

    def test_kelleher_250_beats_223_despite_distance_from_even_money(self):
        rows = [self.row('Kambi', 2.23), self.row()]
        shadow.mark_primary_selections(rows)
        self.assertEqual([r['bookmaker'] for r in rows if r['strongest_for_fixture']=='yes'], ['Bet365'])

    def test_kambi_can_win_and_tie_is_only_one_offer(self):
        for odds, expected in [(2.7, 'Kambi'), (2.5, 'Bet365')]:
            rows = [self.row('Kambi', odds), self.row()]
            shadow.mark_primary_selections(rows)
            self.assertEqual([r['bookmaker'] for r in rows if r['strongest_for_fixture']=='yes'], [expected])

    def test_higher_price_outside_policy_does_not_choose_inferior_same_line(self):
        rows = [self.row('Kambi', 2.8), self.row(odds=3.2, candidate_status='value_ladder')]
        shadow.mark_primary_selections(rows)
        self.assertFalse(any(r['strongest_for_fixture']=='yes' for r in rows))

    def test_different_lines_keepers_and_sides_are_not_conflated(self):
        rows = [self.row(), self.row('Kambi', 2.8, line='3.5'), self.row('Kambi', 2.9, goalkeeper='Other'), self.row('Kambi', 2.9, side='under')]
        self.assertEqual(len(prices.best_offers(rows, self.now)), 4)
        self.assertIsNone(prices.alert_price_check(rows[0], rows, self.now)[0])

    def test_stale_future_started_and_unmapped_quotes_do_not_win(self):
        for changes in [dict(captured_at=(self.now-timedelta(hours=7)).isoformat()),
                        dict(captured_at=(self.now+timedelta(minutes=1)).isoformat()),
                        dict(kickoff_at=self.now.isoformat()), dict(identity_basis='unresolved_team_keeper')]:
            rows = [self.row(), self.row('Kambi', 3, **changes)]
            self.assertEqual([r['bookmaker'] for r in prices.best_offers(rows, self.now)], ['Bet365'])

    def test_previous_capture_not_mistaken_for_current_availability(self):
        rows = [self.row(captured_at=(self.now-timedelta(minutes=2)).isoformat()), self.row('Kambi', 2.23)]
        self.assertEqual([r['bookmaker'] for r in prices.best_offers(rows, self.now)], ['Kambi'])

    def test_only_one_new_fixture_record_and_original_price_never_changed(self):
        rows = [self.row('Kambi', 2.23), self.row()]
        shadow.mark_primary_selections(rows)
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'ledger.csv'
            n, first = shadow.append_signals(p, rows, self.now.isoformat())
            self.assertEqual(n, 1); self.assertEqual(first[0]['bookmaker'], 'Bet365')
            original = p.read_bytes()
            later = [self.row('Kambi', 2.9)]
            shadow.mark_primary_selections(later)
            self.assertEqual(shadow.append_signals(p, later, self.now.isoformat())[0], 0)
            self.assertEqual(p.read_bytes(), original)

    def test_alert_compares_before_claim_and_lists_prices(self):
        rows = [self.row('Kambi', 2.23), self.row()]; state = {}
        self.assertEqual(alerts.claim(rows, state, 'x:1', self.now, rows), 1)
        signal = next(iter(state['signals'].values()))['signal']
        self.assertEqual(signal['bookmaker'], 'Bet365')
        self.assertIn('Bet365 2.50 | Kambi 2.23', alerts.message(signal))

    def test_old_bet365_receipt_blocks_later_kambi_even_if_365_quote_is_old(self):
        earlier = self.row(); later = self.row('Kambi', 2.23)
        state = {'signals':{earlier['signal_id']:{'status':'sent', 'signal':earlier}}}
        original = copy.deepcopy(state['signals'])
        self.assertEqual(alerts.claim([later], state, 'x:2', self.now, [later]), 0)
        self.assertEqual(state['signals'], original)

    def test_missing_or_changed_current_price_is_not_advertised(self):
        r = self.row()
        self.assertEqual(prices.alert_price_check(r, [], self.now)[0], 'current_quote_unavailable')
        self.assertEqual(prices.alert_price_check(r, [self.row(odds=2.4)], self.now)[0], 'recorded_price_changed')

    def test_send_rechecks_and_blocks_a_newly_better_price_without_network(self):
        r = self.row('Kambi', 2.23); state = {}
        alerts.claim([r], state, 'x:1', self.now, [r])
        with tempfile.TemporaryDirectory() as d:
            statefile=Path(d)/'state.json'; board=Path(d)/'board.csv'
            statefile.write_text(json.dumps(state))
            shadow.write_csv(board, [r, self.row()], shadow.CANDIDATE_FIELDS)
            env={'GITHUB_RUN_ID':'x','GITHUB_RUN_ATTEMPT':'1','OPS_ALERT_TELEGRAM_BOT_TOKEN':'fake','OPS_ALERT_TELEGRAM_CHAT_ID':'fake'}
            with patch.object(sys,'argv',['alerts','--send','--state',str(statefile),'--candidates',str(board)]), patch.dict(os.environ,env), patch.object(alerts.requests,'post') as post:
                alerts.main(); post.assert_not_called()
            saved=json.loads(statefile.read_text())['signals'][r['signal_id']]
            self.assertEqual(saved['suppression_reason'], 'better_bookmaker_price_available')

    def test_paper_keeper_watch_remains_separate_from_current_model(self):
        current=self.row(); state={'signals':{current['signal_id']:{'status':'sent','signal':current}}}
        watch=dict(current, alert_model='keeper_watch_v1', signal_id='keeper_watch_v1:42',
                   selection_policy='keeper_watch_v1', paper_stake=.5, actual_stake=0)
        self.assertEqual(alerts.claim([watch],state,'x:1',self.now,[]),1)

if __name__ == '__main__': unittest.main()
