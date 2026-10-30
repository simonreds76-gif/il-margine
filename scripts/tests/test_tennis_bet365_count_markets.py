import copy
import importlib.util
import json
import sys
import unittest
from argparse import Namespace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import moviodds_prices as feed
import tennis_paper_prices as prices
import tennis_most_aces_current as current


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS/(name+'.py'))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


capture = load('tennis-most-aces-capture')
scraper = load('tennis-props-scrape-bet365')
compare = load('tennis-props-compare-bet365')
tracker = load('tennis-props-shadow-tracker')
digest = load('tennis-daily-signal-digest')


class VerifiedMarkets(unittest.TestCase):
    def setUp(self):
        self.raw = json.loads((SCRIPTS/'tests/fixtures/moviodds-tennis-counts.json').read_text(encoding='utf-8'))
        self.now = feed.utc(self.raw['server_time'])

    def markets(self):
        events, _ = feed.normalize(self.raw, 'tennis', self.now)
        return events, [m for e in events for m in e['bookmakers']['Bet365']]

    def test_real_contracts_parse_separately_with_evidence_and_fresh_poll(self):
        events, markets = self.markets()
        self.assertEqual({m['name'] for m in markets}, {'Most Aces','Most Double Faults','Totals (Aces)','Totals (Double Faults)'})
        most = capture.extract_rows(events, 'wrong', scraper)
        self.assertEqual(len(most), 1)
        self.assertEqual(len(most[0]['evidence_sha256']), 64)
        self.assertNotEqual(most[0]['capture_ts'], 'wrong')
        self.assertTrue(most[0]['raw_market_json'])
        rows = [r for e in events for m in e['bookmakers']['Bet365'] for r in scraper.extract_rows(e, 'Bet365', m, 'wrong')]
        self.assertEqual({r['market'] for r in rows}, {'match_aces','match_double_faults'})
        self.assertTrue(all(r['over_odds'] and r['under_odds'] for r in rows))
        self.assertTrue(all(r['player'] == events[0]['home'] and r['opponent'] == events[0]['away'] for r in rows))

    def test_missing_tie_never_becomes_two_way_most_aces(self):
        m = self.raw['matches'][0]
        m['quotes'] = [q for q in m['quotes'] if not (q['line']=='Aces' and q['side']=='Tie')]
        self.assertNotIn('Most Aces', [m['name'] for m in self.markets()[1]])

    def test_double_fault_1x2_is_never_aces(self):
        m = self.raw['matches'][0]
        m['quotes'] = [q for q in m['quotes'] if q['line']=='Double Faults']
        self.assertNotIn('Most Aces', [m['name'] for m in self.markets()[1]])

    def test_total_requires_matching_pair_threshold_and_exact_market(self):
        for change in ({'handicap':'14.5'}, {'market_id':'set-one'}, {'suspended':True}):
            original = copy.deepcopy(self.raw)
            q = next(q for q in self.raw['matches'][0]['quotes'] if q['group_id']=='130328' and q['line']=='Aces' and q['side']=='Under')
            q.update(change)
            self.assertNotIn('Totals (Aces)', [m['name'] for m in self.markets()[1]])
            self.raw = original

    def test_stale_poll_and_conflicting_prices_fail_closed(self):
        original = copy.deepcopy(self.raw)
        self.raw['matches'][0]['group_status']['130317']['stale'] = True
        self.assertNotIn('Most Aces', [m['name'] for m in self.markets()[1]])
        self.raw = original
        q = copy.deepcopy(next(q for q in self.raw['matches'][0]['quotes'] if q['line']=='Aces' and q['side']=='Tie'))
        q.update(odds_dec=51, odds_frac='50/1')
        self.raw['matches'][0]['quotes'].append(q)
        self.assertNotIn('Most Aces', [m['name'] for m in self.markets()[1]])

    def test_reversed_discovery_order_keeps_named_1x2_and_total_pair(self):
        m = self.raw['matches'][0]
        target = dict(id='api:1', home=m['away'], away=m['home'], date=m['kickoff_utc'], league={'name':m['league']})
        events, _ = feed.normalize(self.raw,'tennis',self.now,targets=[target])
        row = capture.extract_rows(events,'wrong',scraper)[0]
        expected = next(q['odds_dec'] for q in m['quotes'] if q['side']==m['away'] and q['line']=='Aces')
        self.assertEqual(float(row['player1_odds']), expected)

    def test_verified_bet365_evidence_reaches_frozen_count_model(self):
        events, _ = self.markets()
        quote = capture.extract_rows(events,'wrong',scraper)[0]
        board = dict(date=quote['date'],tour=quote['tour'],tournament=quote['tournament'],
                     player1=quote['player1'],player2=quote['player2'],p_player1='.05',p_draw='.05',p_player2='.90',
                     fair_player1='20',fair_draw='20',fair_player2='1.1111',quote_status='READY',
                     generated_at_utc=self.now.isoformat(),player1_confidence='MED',player2_confidence='MED',model=current.COUNT_MODEL)
        shadow = current.load_shadow()
        clock = type('Clock',(datetime,),{'now':classmethod(lambda cls,tz=None:self.now)})
        with patch.object(shadow,'datetime',clock):
            candidate = shadow.registration_row(board,quote)
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate['bookmaker'],'Bet365')
        self.assertEqual(candidate['p_player1'],'.05')
        self.assertEqual(candidate['raw_market_json'],quote['raw_market_json'])

    def test_most_aces_best_book_and_duplicate_state(self):
        start = (self.now+timedelta(hours=2)).isoformat()
        candidate = dict(date=self.now.date().isoformat(),tournament='Basel',player1='Player A',player2='Player B',
                         model=current.COUNT_MODEL,bet_eligible='yes',recommended_side='P1',selected_odds='2.2',
                         value_player1_pct='20',fair_player1='1.833',match_start_utc=start,
                         price_captured_at=self.now.isoformat(),bookmaker='Bet365')
        worse = dict(candidate,bookmaker='Grosvenor',selected_odds='2.0',value_player1_pct='9')
        report = {'generated_at':self.now.isoformat(),'matches':[{'model':current.COUNT_MODEL,'prices':[{'candidate':worse},{'candidate':candidate}]}]}
        self.assertEqual(current.alert_rows(report,self.now),[candidate])
        state = {'signal_ids':[f"{candidate['date']}|player a|player b|player a|most_aces_1x2|basel"]}
        with patch.object(digest.json,'loads',return_value=report),patch.object(Path,'read_text',return_value='{}'):
            signals=digest.most_aces_signals(candidate['date'],now=self.now)
        self.assertEqual(len(signals),1)
        self.assertEqual(digest.new_signals_since_state(signals,state,candidate['date']),[])
        report['matches'][0]['prices'][1]['candidate']['price_captured_at']=(self.now-timedelta(minutes=31)).isoformat()
        self.assertEqual(current.alert_rows(report,self.now),[worse])


class PaperSelection(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026,10,30,10,tzinfo=timezone.utc)
        self.args = Namespace(min_value=.10,min_novig_edge=.05,max_model_market_gap=.12)

    def row(self, **change):
        return dict(dict(date='2026-10-30',tour='ATP',tournament='Basel',player='Player A',opponent='Player B',
            market='match_aces',scope='match_total',bookmaker='Grosvenor',line='10.5',over_odds='2.0',under_odds='1.8',
            capture_ts=(self.now-timedelta(minutes=2)).isoformat(),match_start_utc=(self.now+timedelta(hours=3)).isoformat(),
            matched_board='yes',price_pair_status='two_way',line_quality='complete',totals_stage0_passed='true',
            projection_mean='11',projection_p1='6',projection_p2='5',confidence='MED',combined_surface_svpt_sample='2500',
            novig_p_over='.48',model_market_gap_pp='8',value_over_pct='15',value_under_pct='-5',edge_over_novig_pct='12',
            edge_under_novig_pct='-2',notes='TOURNAMENT_DEBUT|SAME_TOURNAMENT_N1|EVENT_ENV_N28|SURFACE_BASELINE_ONLY'),**change)

    def gate(self, rows):
        compare.apply_decision_gates(rows,self.args,self.now)
        return rows

    def test_informational_notes_only_open_paper_not_live(self):
        row = self.gate([self.row()])[0]
        self.assertEqual(row['bettable'],'false')
        self.assertIn('BOARD_WARNINGS',row['block_reasons'])
        self.assertEqual(row['decision_mode'],'two_way_match_total_shadow')
        self.assertEqual(row['trackable_shadow'],'true')
        args = Namespace(allow_medium=False,min_value=8,allow_watch=False,bookmaker='Bet365')
        signal = tracker.build_signal(row,Path('fixture.csv'),args)
        self.assertEqual(signal['selected_odds'],'2.000')
        self.assertEqual(signal['settlement_status'],'pending')

    def test_real_unknown_warnings_and_failed_stage_still_block(self):
        for change in ({'notes':'NO_PLAYER_DATA'},{'notes':'NEW_UNRECOGNISED_WARNING'}, {'totals_stage0_passed':'false'},
                       {'projection_p2':''},{'combined_surface_svpt_sample':'100'},{'confidence':'LOW'}):
            with self.subTest(change=change):
                self.assertEqual(self.gate([self.row(**change)])[0]['trackable_shadow'],'false')

    def test_best_exact_contract_not_first_book_and_no_synthetic_pair(self):
        rows = self.gate([self.row(),self.row(bookmaker='Bet365',over_odds='2.2',under_odds='1.7',value_over_pct='26',novig_p_over='.44')])
        chosen = prices.best_total_rows(rows,self.now)
        self.assertEqual(len(chosen),1)
        self.assertEqual(chosen[0]['bookmaker'],'Bet365')
        self.assertEqual(chosen[0]['under_odds'],'1.7')
        self.assertEqual(chosen[0]['bettable'],'false')

    def test_stale_future_naive_or_started_prices_never_signal(self):
        for change in ({'capture_ts':(self.now-timedelta(minutes=31)).isoformat()},
                       {'capture_ts':(self.now+timedelta(minutes=1)).isoformat()},
                       {'capture_ts':'2026-10-30T09:59:00'}, {'match_start_utc':self.now.isoformat()}):
            with self.subTest(change=change):
                self.assertFalse(prices.best_total_rows(self.gate([self.row(**change)]),self.now))

    def test_newer_same_book_snapshot_removes_old_high_price(self):
        rows = self.gate([self.row(over_odds='3.0'),self.row(line='11.5',capture_ts=self.now.isoformat())])
        self.assertFalse(any(r['line']=='10.5' for r in prices.best_total_rows(rows,self.now)))

    def test_reversed_players_and_integer_line_format_still_one_contract(self):
        rows = self.gate([self.row(),self.row(player='Player B',opponent='Player A',bookmaker='Bet365',line='10.50',over_odds='2.2',value_over_pct='26')])
        self.assertEqual(len(prices.best_total_rows(rows,self.now)),1)

    def test_bookmaker_change_does_not_resend_and_alert_is_paper_only(self):
        rows = self.gate([self.row(),self.row(bookmaker='Bet365',over_odds='2.2',value_over_pct='26')])
        with patch.object(digest,'read_csv',return_value=rows):
            signals = digest.props_signals('2026-10-30',now=self.now)
        self.assertEqual(len(signals),1)
        self.assertIn('PAPER ONLY',signals[0].section)
        self.assertEqual(signals[0].performance_source['bookmaker'],'Bet365')
        state = {'signal_ids':[digest.signal_id(signals[0])]}
        rows[0].update(over_odds='2.4',value_over_pct='38')
        with patch.object(digest,'read_csv',return_value=rows):
            updated = digest.props_signals('2026-10-30',now=self.now)
        self.assertEqual(updated[0].performance_source['bookmaker'],'Grosvenor')
        self.assertEqual(digest.new_signals_since_state(updated,state,'2026-10-30'),[])


if __name__=='__main__':unittest.main()
