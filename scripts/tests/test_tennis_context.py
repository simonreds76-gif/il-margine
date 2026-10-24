import csv
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tennis_match_context import build_context

class ContextTests(unittest.TestCase):
    def test_all_opponents_walkovers_duplicates_retirement_and_cutoff(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            def write(name,rows):
                with (root/name).open('w',newline='',encoding='utf-8') as f:
                    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
            write('players_atp.csv',[{'id':'1','name':'First Player'},{'id':'2','name':'Outside Player'}])
            write('tours_atp.csv',[dict(id='t',name='Test',court_id='1',country='GBR')])
            def game(day,score,rd):return dict(date=day,result=score,round_id=rd,tour_id='t',winner_id='1',loser_id='2')
            played=game('2026-10-23','6-3 2-1 ret.','4')
            write('games_atp.csv',[played,played,game('2026-10-22','w/o','3'),game('2026-10-24','6-0 6-0','5')])
            out=build_context(root,[{'name':'First Player'},{'name':'Unknown Player'}],'2026-10-24')
            self.assertEqual(len(out['players']['0']),1)
            row=out['players']['0'][0]
            self.assertEqual(row['sets'],1);self.assertEqual(row['games'],12)
            self.assertTrue(row['retired']);self.assertFalse(out['mapped']['1'])
            self.assertEqual(out['through'],'2026-10-23')
