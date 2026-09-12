import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from datetime import date

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
def module(name,file):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/file)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
S=module('publication_settle','settle-football-research-lanes.py')
T=module('publication_team_clv','team-shots-v1-clv-monitor.py')
C=module('publication_corner_clv','corners-v0-clv-monitor.py')

class PublicationOddsTests(unittest.TestCase):
    def pick(self):
        return dict(pick_id='example',match='Arsenal vs Chelsea',home_team='Arsenal',away_team='Chelsea',team='Arsenal',league='epl',kickoff_utc='2026-09-12T14:00:00Z',published_at_utc='2026-09-12T12:00:00Z',line='9.5',side='over',book_odds='1.8',result='pending',current_model_would_have_priced='true')
    def test_both_clv_builders_retain_entry_price_and_use_it_for_clv(self):
        for m,field in [(T,'book_price_at_publication'),(C,'pinnacle_price_at_publication')]:
            with self.subTest(field=field),patch.object(m,'price_at_or_before',return_value=2.2),patch.object(m,'snapshot_at_or_before',return_value=None):
                row=m.build_pick_row(self.pick(),{},allow_canonical_only=False,allowed_leagues={'epl'},config_valid=True,config_error='')
                self.assertEqual(row[field],1.8)
    def test_missing_entry_price_never_settles_at_close(self):
        key=S.build_fixture_key(date(2026,9,12),'Arsenal','Chelsea')
        results={key:dict(home_shots=12,away_shots=8,total_corners=12)}
        for fn,entry,close in [(S.settle_team_shots,'book_price_at_publication','book_price_close'),(S.settle_corners,'pinnacle_price_at_publication','pinnacle_price_close')]:
            for value in ('','nan','0'):
                row=dict(self.pick(),**{entry:value,close:'2.2'})
                self.assertEqual(fn([row],results),0)
                self.assertEqual(row['result'],'pending')
    def test_valid_entry_price_and_settled_losses_remain_immutable(self):
        key=S.build_fixture_key(date(2026,9,12),'Arsenal','Chelsea')
        results={key:dict(home_shots=12,away_shots=8,total_corners=12)}
        for fn,entry in [(S.settle_team_shots,'book_price_at_publication'),(S.settle_corners,'pinnacle_price_at_publication')]:
            row=dict(self.pick(),**{entry:'1.8'})
            self.assertEqual(fn([row],results),1)
            self.assertEqual(row['pnl_units'],.8)
            row.update(result='lost',pnl_units=-1)
            self.assertEqual(fn([row],results),0)
            self.assertEqual(row['pnl_units'],-1)

if __name__=='__main__':unittest.main()
