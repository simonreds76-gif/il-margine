import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import moviodds_prices as source
import moviodds_count_prices as counts
from football_count_markets import build_control_odds_rows

class CountCaptureTests(unittest.TestCase):
    def setUp(self):
        self.raw=json.loads((Path(__file__).parent/'fixtures/moviodds-counts.json').read_text())
        self.now=datetime(2026,10,28,18,45,25,tzinfo=timezone.utc)
        self.targets=[dict(id=m['id'],home=m['home'],away=m['away'],date=m['kickoff_utc'],
                          league={'slug':'italy-serie-a'}) for m in self.raw['matches']]
        counts._board=None;counts._attempted=False

    def norm(self,raw=None):
        return source.normalize(raw or self.raw,'soccer',self.now,targets=self.targets,groups=counts.GROUPS)[0]

    def test_real_board_stale_shots_rejected_fresh_corners_retained(self):
        events=self.norm()
        genoa=next(e for e in events if e['home']=='Genoa')
        monza=next(e for e in events if e['home']=='Monza')
        self.assertEqual({m['name'] for m in genoa['bookmakers']['Bet365']},{'Corners Totals'})
        self.assertEqual({m['name'] for m in monza['bookmakers']['Bet365']},{'Corners Totals','Total Shots Home','Total Shots Away'})
        rows=build_control_odds_rows(events,'Serie A','WRONG_TIMESTAMP')
        self.assertTrue(rows)
        self.assertTrue(all(r['captured_at']!='WRONG_TIMESTAMP' and r['source']=='moviodds_bet365' for r in rows))
        self.assertTrue(all(r['market']=='MATCH_CORNERS' and r['bookmaker']=='Bet365' for r in rows))

    def test_bad_contracts_cannot_become_team_shots(self):
        raw=copy.deepcopy(self.raw);raw['matches']=[next(m for m in raw['matches'] if m['home']=='Monza')]
        q=next(q for q in raw['matches'][0]['quotes'] if q['group_id']=='50532')
        for change in [{'group_name':'Team Shots on Target'},{'market_id':'first_half'},
                       {'side':'Unknown club'},{'odds_frac':'999/1'},{'handicap':'99.5'},{'suspended':True}]:
            test=copy.deepcopy(raw);test['matches'][0]['quotes']=[{**q,**change}]
            self.assertEqual(self.norm(test),[])

    def test_one_board_request_shared_and_other_books_preserved_on_failure(self):
        original=[{**self.targets[0],'bookmakers':{'Grosvenor':[{'name':'ML'}]}}]
        with tempfile.TemporaryDirectory() as folder,patch.object(source,'download',return_value=self.raw) as get:
            first,receipt=counts.capture_and_merge(original,self.targets,now=self.now,raw_path=Path(folder)/'raw.gz')
            second,_=counts.capture_and_merge(original,self.targets,now=self.now,raw_path=Path(folder)/'raw.gz')
        self.assertEqual(get.call_count,1)
        self.assertEqual(first,second)
        self.assertEqual(first[0]['bookmakers']['Grosvenor'],original[0]['bookmakers']['Grosvenor'])
        self.assertGreater(receipt['team_shots_quotes'],0)
        counts._board=None;counts._attempted=False
        with patch.object(source,'download',side_effect=ValueError('bad feed')):
            result,receipt=counts.capture_and_merge(original,self.targets,now=self.now)
        self.assertEqual(result,original);self.assertEqual(receipt['status'],'SOURCE_FAILED')

if __name__=='__main__':unittest.main()
