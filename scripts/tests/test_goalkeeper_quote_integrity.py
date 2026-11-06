"""Regression of the two 4+ prices wrongly attached to Over 2.5."""
import copy
import importlib.util
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import goalkeeper_quote_integrity as gate
import goalkeeper_price_selection as prices
import moviodds_prices as source

def load(name):
    spec=importlib.util.spec_from_file_location(name,Path(__file__).resolve().parents[1]/(name+'.py'))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

class ContractIncident(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,11,6,16,29,6,tzinfo=timezone.utc)
        self.row=dict(event_id='72513308',goalkeeper='Nahuel Noll',bookmaker='Bet365',
            line='2.5',side='over',odds_decimal='2.25',captured_at='2026-11-06T15:58:29Z',
            kickoff_at='2026-11-07T14:30:00Z',created_at='2026-11-06T16:00:00Z',
            status='pending',edge='.438',fair_odds='1.56',selection_policy='near_even_value_v2',
            signal_id='72513308|nahuel noll|2.5|over',candidate_status='eligible_shadow',
            strongest_for_fixture='yes',blockers='')

    def test_fresh_self_consistent_wrong_quotes_are_not_trusted(self):
        raw=json.loads((Path(__file__).parent/'fixtures/moviodds-gk-contract-incident.json').read_text())
        targets=[dict(id=m['id'],home=m['home'],away=m['away'],date=m['kickoff_utc'],
            league={'slug':source.LEAGUES[m['league']]}) for m in raw['matches']]
        events,excluded=source.normalize(raw,'soccer',self.now,targets=targets)
        self.assertFalse(events)
        self.assertEqual(excluded[gate.REASON],sum(len(m['quotes']) for m in raw['matches']))

    def test_older_saved_board_cannot_bypass_hold(self):
        row={**self.row,'captured_at':'2026-11-05T23:00:00Z'}
        self.assertEqual(load('goalkeeper-saves-shadow').latest_price_rows([row],self.now),[])
        self.assertEqual(prices.current_offers([self.row],self.now),[])
        self.assertFalse(load('goalkeeper-saves-alerts').eligible(self.row,self.now))
        self.assertEqual(load('football-daily-signal-digest').goalkeeper_candidates([self.row],'2026-11-07'),[])

    def test_best_valid_book_remains_available(self):
        valid={**self.row,'bookmaker':'Grosvenor','odds_decimal':'1.50'}
        self.assertEqual(prices.best_offers([self.row,valid],self.now),[valid])

    def test_records_are_annotated_without_relabel_or_reprice(self):
        original=copy.deepcopy(self.row)
        reviewed=gate.annotate_records([original])[0]
        self.assertEqual({k:reviewed[k] for k in original},original)
        self.assertEqual(reviewed['integrity_status'],'quote_quarantined')
        old={**self.row,'captured_at':'2026-11-05T12:00:00Z','status':'won'}
        self.assertEqual(gate.annotate_records([old]),[old])
        report=load('goalkeeper-saves-shadow').report_payload([], [self.row],self.now.isoformat(),0)
        self.assertEqual(report['evidence']['quote_quarantined'],1)
        self.assertEqual(report['evidence']['pending'],0)
        self.assertIsNone(report['evidence']['roi'])

    def test_sports_and_markets_other_than_gk_are_not_disabled(self):
        self.assertTrue(source.enabled('tennis'))
        self.assertIn('177727',source.GROUPS['soccer'])
