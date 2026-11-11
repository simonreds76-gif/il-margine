import csv
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tennis_paper_quote_identity import match_quote, tables


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        folder=self.root/'data/oncourt';folder.mkdir(parents=True)
        (folder/'tours_atp.csv').write_text('id,name,date\n22197,Brisbane 3 Challenger,2026-11-09\n')
        (folder/'today_atp.csv').write_text('tour_id,round_id,player1_id,player2_id,result,live\n22197,5,11,12,,\n')
        self.row=dict(tour_id=22197,round_id=5,player1_id=11,player2_id=12,player1='Dane Sweeny',player2='Casey Hoole',tour_name='Brisbane 3 Challenger',official_category='Challenger')
        self.quote=dict(player1_name='Dane Sweeny',player2_name='Casey Hoole',odds1='1.4',odds2='3.0',captured_at='2026-11-11T10:00:00Z',kickoff_iso='2026-11-12T00:00:00Z',league='Challenger',league_name='ATP Challenger Brisbane - R16')
    def tearDown(self): self.tmp.cleanup();tables.cache_clear()
    def test_numbered_edition_maps_only_after_fixture_validation(self):
        q,why=match_quote(self.root,self.row,[self.quote]);self.assertIsNone(why);self.assertEqual(q['tour_id'],'22197')
    def test_other_year_rejected(self):
        self.quote['kickoff_iso']='2025-11-12T00:00:00Z';self.assertIsNone(match_quote(self.root,self.row,[self.quote])[0])
    def test_wrong_round_rejected(self):
        self.quote['league_name']='ATP Challenger Brisbane - QF';self.assertIsNone(match_quote(self.root,self.row,[self.quote])[0])
    def test_wrong_opponent_rejected(self):
        self.quote['player2_name']='Other Hoole';self.assertIsNone(match_quote(self.root,self.row,[self.quote])[0])
    def test_wrong_tournament_rejected(self):
        self.quote['league_name']='ATP Challenger Monastir - R16';self.assertIsNone(match_quote(self.root,self.row,[self.quote])[0])
    def test_reversed_pair_preserves_side_prices(self):
        self.quote.update(player1_name='Casey Hoole',player2_name='Dane Sweeny')
        q,_=match_quote(self.root,self.row,[self.quote]);self.assertEqual((q['odds1'],q['odds2']),(3,1.4))
    def test_conflicting_latest_quote_is_not_best_price_cherry_pick(self):
        self.assertIsNone(match_quote(self.root,self.row,[self.quote,dict(self.quote,odds1='2.0')])[0])
    def test_superseded_start_does_not_block_unique_current_quote(self):
        old=dict(self.quote,captured_at='2026-11-11T09:30:00Z',kickoff_iso='2026-11-12T01:00:00Z')
        q,_=match_quote(self.root,self.row,[old,self.quote]);self.assertEqual(q['kickoff_iso'],self.quote['kickoff_iso'])
    def test_completed_local_fixture_is_not_upcoming(self):
        (self.root/'data/oncourt/today_atp.csv').write_text('tour_id,round_id,player1_id,player2_id,result,live\n22197,5,11,12,6-2 6-3,\n')
        self.assertIsNone(match_quote(self.root,self.row,[self.quote])[0])
    def test_ambiguous_numbered_edition_rejected(self):
        with (self.root/'data/oncourt/tours_atp.csv').open('a') as f:f.write('22199,Brisbane 4 Challenger,2026-11-16\n')
        with (self.root/'data/oncourt/today_atp.csv').open('a') as f:f.write('22199,5,11,12,,\n')
        self.assertIsNone(match_quote(self.root,self.row,[self.quote])[0])
    def test_generic_qualifying_quote_cannot_join_two_rounds(self):
        self.row['round_id']=1
        self.quote['league_name']='ATP Challenger Brisbane - Qualifying'
        (self.root/'data/oncourt/today_atp.csv').write_text('tour_id,round_id,player1_id,player2_id,result,live\n22197,1,11,12,,\n22197,3,11,12,,\n')
        self.assertIsNone(match_quote(self.root,self.row,[self.quote])[0])


if __name__=='__main__':unittest.main()
