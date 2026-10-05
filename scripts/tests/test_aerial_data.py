import copy
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from aerial_data import make_fixture, player_history, height_summary, utc, save, read
spec=importlib.util.spec_from_file_location('aerial_refresh',Path(__file__).resolve().parents[1]/'refresh-aerial.py')
refresh=importlib.util.module_from_spec(spec);spec.loader.exec_module(refresh)

class AerialTests(unittest.TestCase):
    def setUp(self):
        self.now=utc('2026-10-10T12:00:00+00:00')
        self.row=dict(id='1',date='2026-10-10T13:00:00Z',league='League',season='2026/2027',home='Home',away='Away',home_id='10',away_id='20',match_url='https://www.fotmob.com/matches/test#1')
        self.line=dict(fotmob_match_id=1,kickoff_utc=self.row['date'],lineup_type='predicted',observed_at=self.now.isoformat())
        self.heights={}
        for side,tid in [('home','10'),('away','20')]:
            self.line[side+'_fotmob_team_id']=tid
            self.line[side+'_starters']=[dict(player_id=str(int(tid)*100+i),name=f'{side} {i}',line_index=-1 if i==0 else 0,line_size=1 if i==0 else 4) for i in range(11)]
            for i,p in enumerate(self.line[side+'_starters']):
                self.heights[p['player_id']]=dict(height_cm=180+i,positions='GK' if i==0 else 'CB')
        self.history=[]
        for mid,date in [('1','2026-10-01T00:00:00Z'),('2','2026-10-09T13:00:00Z'),('3','2026-10-10T10:00:00Z'),('4','2026-10-11T00:00:00Z')]:
            self.history.append(dict(id=mid,date=date,season='2026/2027',home_id='10',away_id='20',home='Home',away='Away',delivery=[],players=[dict(id='1001',minutes=90,aerials_won=2,aerials_attempted=4,headed_shots=1)]))
    def fixture(self,line=None):
        return make_fixture(self.row,line or self.line,self.history,self.heights,self.now)
    def test_strict_cutoff_and_target_exclusion(self):
        f=self.fixture();h=f['teams'][0]['players'][1]['histories']['recent']
        self.assertEqual([r['fixture_id'] for r in h['appearances']],['2'])
        self.assertEqual(h['minutes'],90)
    def test_confirmed_replaces_expected_player(self):
        a=self.fixture();line=copy.deepcopy(self.line);line['lineup_type']='standard';line['home_starters'][1]['player_id']='99999'
        b=self.fixture(line);self.assertEqual(a['state'],'expected');self.assertEqual(b['state'],'confirmed')
        self.assertEqual(b['teams'][0]['players'][1]['id'],'99999');self.assertIsNone(b['teams'][0]['height']['mean_cm'])
    def test_stale_lineup_suppresses_players(self):
        line=copy.deepcopy(self.line);line.update(lineup_type='standard',observed_at='2026-10-10T09:00:00Z')
        f=self.fixture(line);self.assertEqual(f['state'],'stale');self.assertFalse(f['teams'][0]['players'])
    def test_duplicate_or_cross_team_identity_rejected(self):
        for field,value in [('home_fotmob_team_id','99'),('fotmob_match_id','99')]:
            line=copy.deepcopy(self.line);line[field]=value
            with self.assertRaises(ValueError):self.fixture(line)
        line=copy.deepcopy(self.line);line['away_starters'][1]['player_id']='1001'
        with self.assertRaises(ValueError):self.fixture(line)
    def test_held_height_cannot_influence_average(self):
        self.heights['1001'].update(status='held',height_cm=193)
        f=self.fixture();self.assertEqual(f['teams'][0]['height']['known'],9);self.assertIsNone(f['teams'][0]['height']['mean_cm'])
    def test_primary_role_does_not_follow_secondary_position_substrings(self):
        self.heights['1001'].update(positions='CDM,RB,CAM,CM',role_group='midfielders')
        self.heights['1002'].update(positions='LM,LW',role_group='midfielders')
        self.assertEqual([p['role'] for p in self.fixture()['teams'][0]['players'][1:3]],['MID','MID'])
    def test_unknown_not_zero_and_zero_attempts_not_zero_percent(self):
        h=player_history([dict(fixture_id='a',date='2026-01-01',match='A v B',minutes=90,aerials_won=0,aerials_attempted=0,headed_shots=None)])
        self.assertIsNone(h['aerial_win_pct']);self.assertIsNone(h['headers_per90']);self.assertEqual(h['head_minutes'],0)
    def test_failure_preserves_public_snapshot_and_observation(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);client=Mock();save(root/'public/fair-odds-lab/aerial.json',{'version':'last-good'})
            with patch.object(refresh,'refresh',side_effect=ValueError('calendar invalid')):
                self.assertFalse(refresh.publish(client,root,self.now))
            client.put.assert_not_called();self.assertEqual(read(root/'public/fair-odds-lab/aerial.json')['version'],'last-good')
            self.assertEqual(read(root/'data/aerial/health.json')['last_error'],'calendar invalid')

if __name__=='__main__':unittest.main()

