import importlib.util
import csv
import json
import tempfile
import unittest
from pathlib import Path

spec=importlib.util.spec_from_file_location('matchup_builder',Path(__file__).resolve().parents[1]/'build-tennis-matchup.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class MatchupBuildTests(unittest.TestCase):
    def test_completed_score_rejects_walkovers_retirements_and_partial_sets(self):
        for score in ['6-4 6-4','6-4 5-7 6-4','6-4 6-4 6-4','7-6(2) 7-6(5)']:
            self.assertTrue(module.completed(score),score)
        for score in ['6-2 ret.','w/o','6-2 3-2','6-2 6-2 1-0','4-2 4-1 4-0']:
            self.assertFalse(module.completed(score),score)

    def test_normalization_is_exact_full_name_not_surname_guess(self):
        self.assertEqual(module.norm('João-Sousa'),module.norm('Joao Sousa'))
        self.assertNotEqual(module.norm('J. Sousa'),module.norm('Joao Sousa'))

    def test_counts_reject_missing_negative_and_impossible_ratios(self):
        self.assertEqual(module.ratio({'n':'0','d':'10'},'n','d'),[0,10])
        for n,d in [('', '10'),('-1','10'),('11','10'),('0','0'),('1.5','10')]:
            self.assertIsNone(module.ratio({'n':n,'d':d},'n','d'))

    def test_service_denominator_must_reconcile(self):
        row={'w_w1s':'6','w_w1sof':'8','w_w2s':'2','w_w2sof':'4','w_svpt':'12'}
        self.assertEqual(module.point_stats(row,'w')['serve'],[8,12])
        row['w_svpt']='13'
        self.assertIsNone(module.point_stats(row,'w')['serve'])

    def test_venue_mapping_is_explicit(self):
        self.assertEqual(module.REGION_OF['CHN'],'Asia')
        self.assertEqual(module.REGION_OF['QAT'],'Asia')
        self.assertIsNone(module.REGION_OF.get('UNKNOWN'))

    def test_reconciled_match_date_controls_export_and_ambiguous_stats_stay_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); oc=root/'oncourt'; oc.mkdir()
            atlas=root/'version-one'; (atlas/'players').mkdir(parents=True)
            def write(name,rows):
                with (oc/name).open('w',newline='',encoding='utf-8') as f:
                    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
            write('players_atp.csv',[dict(id='1',name='First Player'),dict(id='2',name='Second Player')])
            write('tours_atp.csv',[dict(id='t',name='Beijing',court_id='1',rank='2',country='CHN')])
            write('games_atp.csv',[
                dict(winner_id='1',loser_id='2',tour_id='t',round_id='4',result='6-2 6-2',date='2026-09-24'),
                dict(winner_id='1',loser_id='2',tour_id='t',round_id='5',result='6-3 6-3',date='2026-09-26')])
            stat=dict(winner_id='1',loser_id='2',tour_id='t',round_id='4',w_svpt='10')
            write('stat_atp.csv',[stat,stat])
            (atlas/'index.json').write_text(json.dumps({'players':[{'id':'a','name':'First Player'},{'id':'b','name':'Second Player'}],
                'surfaces':['outdoor-hard'],'sources':['Archive'],
                'matches':[['past','2026-09-24',0,1,2,2,0,0,0],['future','2026-09-25',0,1,2,2,0,0,0]]}),encoding='utf-8')
            (atlas/'players'/'a.json').write_text(json.dumps({'version':'version-one','matches':[
                ['past','Beijing','6-2 6-2'],['future','Beijing','6-3 6-3']]}),encoding='utf-8')
            module.build(atlas,oc,root/'preview','2026-09-26')
            result=json.loads((root/'preview'/'data.json').read_text(encoding='utf-8'))
            self.assertEqual([m['id'] for m in result['matches']],['past'])
            self.assertIsNone(result['matches'][0]['stats1'])
            self.assertEqual(result['audit']['on_or_after_cutoff'],1)
            self.assertEqual(result['audit']['ambiguous_stats'],1)

if __name__=='__main__':unittest.main()
