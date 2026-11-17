import csv
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

scripts = Path(__file__).resolve().parents[1]/'scripts'
if not scripts.is_dir():
    scripts = Path('D:/IlMargine/il-margine/scripts')
sys.path.insert(1,str(scripts))
import tennis_ace_compass as compass
import tennis_sisal_5050 as sisal
from oncourt_nonplayed import FIELDS

class WalkoverTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.data=self.root/'data/oncourt'
        self.data.mkdir(parents=True)
        self.g=dict(winner_id='1',loser_id='2',tour_id='11',round_id='4',result='w/o',date='2026-11-10',date_source='match',status='walkover')
        self.row=dict(id='x',registered_at='2026-11-09T10:00:00Z',native=dict(tid='11',round='4',pid='2',opp='1'),row=dict(match_start_utc='2026-11-10T13:30:00Z'))
        self.now=datetime(2026,11,17,tzinfo=timezone.utc)
        self.save('nonplayed-results',FIELDS,[self.g])
        self.save('games',FIELDS[:6],[])
        self.save('stat',FIELDS[:4],[])

    def save(self,table,fields,rows):
        with (self.data/(table+'_atp.csv')).open('w',newline='') as f:
            w=csv.DictWriter(f,fields,extrasaction='ignore')
            w.writeheader();w.writerows(rows)

    def check(self, grade):
        for model in [compass,sisal]:
            with self.subTest(model=model.__name__):
                outcomes={'old':{'status':'settled','actual':4}}
                model.settle(self.root,[self.row],outcomes,self.now)
                self.assertEqual(outcomes.get('x',{}).get('status'),grade)
                if grade: self.assertIsNone(outcomes['x']['actual'])
                saved=json.dumps(outcomes)
                model.settle(self.root,[self.row],outcomes,self.now)
                self.assertEqual(saved,json.dumps(outcomes))
                self.assertEqual(outcomes['old'],{'status':'settled','actual':4})

    def test_native_wo_and_duplicate(self):
        for word in ['w/o','W.O.','walk over','walkover','WO']:
            row=dict(self.g,result=word);self.save('nonplayed-results',FIELDS,[row,row]);self.check('void')

    def test_conflicting_played_row(self):
        self.save('games',FIELDS[:6],[dict(self.g,result='6-3 6-4')]);self.check(None)

    def test_conflicting_stat_either_orientation(self):
        for a,b in [('1','2'),('2','1')]:
            self.save('stat',FIELDS[:4],[dict(self.g,winner_id=a,loser_id=b)]);self.check(None)

    def test_conflicting_native_dates(self):
        self.save('nonplayed-results',FIELDS,[self.g,dict(self.g,date='2026-11-11')]);self.check(None)

    def test_non_actionable_evidence(self):
        for change in [dict(round_id='5'),dict(tour_id='12'),dict(loser_id='3'),
                       dict(date='2026-11-14'),dict(date='2026-11-08'),dict(date_source='tournament_fallback'),
                       dict(status='unresolved'),dict(result='ret'),dict(date='')]:
            self.save('nonplayed-results',FIELDS,[dict(self.g,**change)]);self.check(None)

    def test_started_capture(self):
        self.row['registered_at']=self.row['row']['match_start_utc'];self.check(None)

if __name__=='__main__':unittest.main()

