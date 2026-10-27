import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
from odds_api_allocation import selected_bookmakers
from tennis_count_settlement import determined_count

def module(name, file):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS/file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

capture = module('sisal_capture','tennis-props-scrape-bet365.py')
settle = module('sisal_settle','tennis-props-settle-shadow.py')

class SisalIntegration(unittest.TestCase):
    def test_scope_keeps_football_unchanged(self):
        for old in ('Bet365','Paddy Power,Kambi',''):
            self.assertEqual(selected_bookmakers(old),'Kambi')
            self.assertEqual(selected_bookmakers(old,scope='tennis_props'),'Sisal IT,Kambi')

    def test_exact_sides_prices_source(self):
        event = dict(id=75991582,home='Kym, Jerome',away='Rinderknech, Arthur',date='2026-10-27T12:10:00Z',
                     league={'name':'ATP - Basel, Switzerland'},urls={'Sisal IT':'https://www.sisal.it/example'})
        for market, expected in [('Aces','aces'),('Double Faults','double_faults')]:
            for side, player in [('Home','Jerome Kym'),('Away','Arthur Rinderknech')]:
                raw=dict(name=f'Team Total ({market}) {side}',updatedAt='2026-10-27T09:11:00Z',odds=[dict(hdp=2.5,over='1.90',under='1.80')])
                rows=capture.extract_rows(event,'Sisal IT',raw,'2026-10-27T09:23:00Z')
                self.assertEqual(len(rows),1)
                row=rows[0]
                self.assertEqual((row['player'],row['market'],row['over_odds'],row['under_odds']),(player,expected,'1.9000','1.8000'))
                self.assertEqual(json.loads(row['raw_market_json']),raw)
                self.assertEqual(row['provider_updated_at'],raw['updatedAt'])
                self.assertEqual(row['source_url'],event['urls']['Sisal IT'])

    def test_other_sisal_contracts_excluded(self):
        e=dict(id=1,home='Player One',away='Player Two',date='2026-10-27T12:00:00Z')
        for name in ('Most Aces 3-Way','Total Aces','Total Double Faults'):
            self.assertEqual(capture.extract_rows(e,'Sisal IT',dict(name=name,odds=[dict(hdp=5.5,over=2,under=2)])),[])

    def test_retirement_rules_and_walkover(self):
        for market in ('aces','double_faults'):
            self.assertTrue(determined_count('Sisal IT',market,7,6.5,'6-4 1-0 RET'))
            for actual in (6,None,float('nan')):
                self.assertFalse(determined_count('Sisal IT',market,actual,6.5,'RET'))
            self.assertFalse(determined_count('Sisal IT',market,7,7,'RET'))
            self.assertFalse(determined_count('Sisal IT',market,7,6.5,'W/O'))
        self.assertFalse(determined_count('Other','aces',7,6.5,'RET'))

    def test_incomplete_match_does_not_discard_determined_stat(self):
        m=dict(score='6-4 1-0 RET')
        with patch.object(settle,'choose_candidate',return_value=m),patch.object(settle,'market_count',return_value=(7,'ok')):
            candidate,actual,note=settle.resolve_count_candidate(dict(player='A',market='aces'),[m],[])
        self.assertEqual(actual,7)
        self.assertTrue(determined_count('Sisal IT','aces',actual,6.5,candidate['score']))

    def test_history_dedup_ignores_added_provenance(self):
        row=dict(event_id='1',capture_ts='now',player='Player',market='aces',line='5.5')
        self.assertEqual(capture.history_row_key(row),capture.history_row_key(dict(row,source_url='url',provider_updated_at='then',raw_market_json='{}')))

if __name__=='__main__': unittest.main()
