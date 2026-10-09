import importlib.util
import csv
import tempfile
import unittest
from pathlib import Path

spec=importlib.util.spec_from_file_location('prices',Path(__file__).resolve().parents[1]/'h2h_historical_prices.py')
prices=importlib.util.module_from_spec(spec);spec.loader.exec_module(prices)

class HistoricalPriceTests(unittest.TestCase):
    def test_partial_source_score_must_not_contradict_completed_result(self):
        for s in ('','6-4 6-6','6-4 5-4','6-4 7-6(2)'):
            self.assertTrue(prices.compatible_score('6-4 7-6(5)',s),s)
        for s in ('6-3 5-4','6-4 7-5','6-4 5-4 ret.','6-4 5-7','6-4 7-6 1-0'):
            self.assertFalse(prices.compatible_score('6-4 7-6(5)',s),s)

    def test_fallback_uses_whole_opening_pair_not_mixed_snapshots(self):
        row=dict(cote1_cloture='1.8',cote2_cloture='',cote1_ouverture='1.9',cote2_ouverture='2.1')
        self.assertEqual(prices.paired_prices(row),([1.9,2.1],'ouverture'))
        row.update(cote2_cloture='2.2')
        self.assertEqual(prices.paired_prices(row),([1.8,2.2],'cloture'))

    def test_matching_orientation_conflicts_and_existing_prices(self):
        players=[dict(id='vbt-1',name='First Player'),dict(id='vbt-2',name='Second Player')]
        result=dict(id='oc-22-11-99-4',date='2023-04-02',event='Lugano',score='6-4 7-6(4)',
                    surface='indoor-hard',p1=1,p2=0,o1=None,o2=None)
        row=dict(match_id='123',date='2023-04-01 23:00:00',tournoi='Lugano',tour='4',genre='atp',
                 joueur1_id='1',joueur2_id='2',joueur1='First Player',joueur2='Second Player',vainqueur_id='2',
                 score='4-6 6-7',surface='dur intérieur',cote1_cloture='',cote2_cloture='',
                 cote1_ouverture='2.8',cote2_ouverture='1.5')
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'odds.csv'
            def run(rows, target):
                with path.open('w',encoding='utf-8',newline='') as f:
                    writer=csv.DictWriter(f,fieldnames=list(row),delimiter=';');writer.writeheader();writer.writerows(rows)
                prices.fill_prices([target],players,[path]);return target
            joined=run([row],dict(result))
            self.assertEqual((joined['o1'],joined['o2']),(1.5,2.8))
            self.assertIn('opening',joined['priceBasis'])
            for field,value in [('vainqueur_id','1'),('score','4-6 4-6'),('date','2023-04-12'),('tournoi','Other'),('surface','gazon'),('tour','5'),('joueur2','Different Player')]:
                self.assertIsNone(run([{**row,field:value}],dict(result))['o1'],field)
            self.assertEqual(run([{**row,'date':'2023-03-30'}],dict(result))['o1'],1.5)
            self.assertIsNone(run([{**row,'date':'2023-03-30','score':'4-6 6-6'}],dict(result))['o1'])
            self.assertEqual(run([{**row,'surface':'dur'}],dict(result))['o1'],1.5)
            players[1]['id']='oc-22'
            self.assertEqual(run([row],dict(result))['o1'],1.5)
            players.append(dict(id='oc-999',name='Second Player'))
            self.assertIsNone(run([row],dict(result))['o1'])
            players.pop();players[1]['id']='vbt-2'
            self.assertIsNone(run([row,{**row,'cote1_ouverture':'3.0'}],dict(result))['o1'])
            preserved=run([row],{**result,'o1':1.6,'o2':2.6})
            self.assertEqual((preserved['o1'],preserved['o2']),(1.6,2.6))
