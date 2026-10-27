import csv
from pathlib import Path
import sys,tempfile,unittest,importlib.util
from datetime import date
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tennis_strict_schedule_reconciliation import reconcile
spec=importlib.util.spec_from_file_location('strict_performance_schedule',Path(__file__).resolve().parents[1]/'strict-policy-performance.py')
perf=importlib.util.module_from_spec(spec);sys.modules[spec.name]=perf;spec.loader.exec_module(perf)

class Reconciliation(unittest.TestCase):
    def fixture(self,folder,wrong_league=False,wrong_score=False):
        root=Path(folder)
        def save(path,rows):
            p=root/path;p.parent.mkdir(parents=True,exist_ok=True)
            with p.open('w',newline='') as f:
                w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
        old=dict(player1='A',player2='B',generation_date='2026-10-09',date='2026-10-13',scheduled_date='2026-10-13',settlement_status='no_match',side='P1',pin_odds1='2.28',stake_units='1')
        new=dict(old,generation_date='2026-10-10',date='2026-10-11',scheduled_date='2026-10-11',match_date='2026-10-11',settlement_status='settled',pin_odds1='2.34',winner_id='1',loser_id='2',settlement_tour_id='21356',settlement_round_id='6',settlement_score='6-4 6-4',bet_outcome='WIN')
        for day,match,league in [('09','13','ATP Shanghai - R3'),('10','11','Other event' if wrong_league else 'ATP Shanghai - R3')]:
            save(f'data/pinnacle-odds-2026-10-{day}.csv',[dict(player1_name='A',player2_name='B',match_date=f'2026-10-{match}',league_name=league,kickoff_iso=f'2026-10-{match}T10:00:00Z')])
        save('data/oncourt/games_atp.csv',[dict(tour_id='21356',round_id='6',winner_id='1',loser_id='2',date='2026-10-11',result='6-0 6-0' if wrong_score else '6-4 6-4')])
        return root,[old,new]
    def test_exact_fixture_first_price_preserved_idempotent(self):
        with tempfile.TemporaryDirectory() as f:
            root,rows=self.fixture(f);journal=reconcile(rows,root)
            self.assertEqual(len(journal),1);self.assertEqual(rows[0]['match_date'],'2026-10-11')
            self.assertEqual(rows[0]['pin_odds1'],'2.28');self.assertEqual(rows[0]['date'],'2026-10-13')
            self.assertEqual(len(rows),2);self.assertEqual(reconcile(rows,root),[])
            self.assertTrue(rows[1]['duplicate_of'])
            deduped=perf.dedupe_rows(rows)
            self.assertEqual(len(deduped),1);self.assertEqual(deduped[0]['pin_odds1'],'2.28')
            self.assertEqual(perf.performance_date(deduped[0]),date(2026,10,11))
            self.assertEqual(perf.filter_window(deduped,date(2026,10,12),date(2026,10,18)),[])
    def test_wrong_edition_or_result_not_reconciled(self):
        for kwargs in ({'wrong_league':True},{'wrong_score':True}):
            with tempfile.TemporaryDirectory() as f:
                root,rows=self.fixture(f,**kwargs);self.assertEqual(reconcile(rows,root),[])
    def test_forecast_after_result_not_reconciled(self):
        with tempfile.TemporaryDirectory() as f:
            root,rows=self.fixture(f);rows[0]['generation_date']='2026-10-12'
            self.assertEqual(reconcile(rows,root),[])

if __name__=='__main__':unittest.main()
