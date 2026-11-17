import csv,json,sys,tempfile,unittest
from contextlib import nullcontext
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch
src=Path(__file__).resolve().parents[1]
if (src/'tennis_nonplay_reconcile.py').is_file():sys.path.insert(0,str(src))
import tennis_nonplay_reconcile as m
import tennis_breakpoint_results as bp
from oncourt_nonplayed import FIELDS
from tennis_hardcourt_scout import atomic
now=datetime(2026,11,17,tzinfo=timezone.utc)
class Reconcile(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup)
        self.root=Path(t.name);self.base=self.root/'data/oncourt';self.base.mkdir(parents=True)
        self.g=dict(winner_id='1',loser_id='2',tour_id='12',round_id='4',date='2026-11-10',status='walkover',result='w/o',date_source='match')
        self.key='12|4|1|2';self.folder=self.root/m.SCOUT
        self.capture=dict(fixture_key=self.key,quote={'kickoff_iso':'2026-11-10T12:00:00Z'},registered_at='2026-11-10T06:00:00Z',registration_sha256='test',selection={'qualifies':True},actual_stake=0)
        (self.folder/'captures').mkdir(parents=True);atomic(self.folder/'registration.json',{})
        atomic(self.folder/'captures/x.json',self.capture);atomic(self.folder/'outcomes.json',{self.key:{'status':'pending'}})
        for file,rows in [('nonplayed-results',[self.g]),('games',[]),('stat',[])]:self.write(file,rows)
    def write(self,file,rows):
        with (self.base/(file+'_atp.csv')).open('w',newline='') as f:
            w=csv.DictWriter(f,FIELDS);w.writeheader();w.writerows(rows)
    def verify(self):return m.evidence_for_lane(self.root,m.SCOUT,now)
    def test_scout_persistence_and_display(self):
        self.assertEqual(self.verify()['new'],1)
        self.assertEqual(self.verify()['new'],0)
        self.write('nonplayed-results',[]);self.assertEqual(self.verify()['retained'],1)
        raw=dict(generated_at=now.isoformat(),pending=1,void=0,overdue=1,quarantined=0,input_revisions={'original':dict(pending=1,void=0)},selections=[dict(fixture_key=self.key,status='pending')])
        with patch('tennis_hardcourt_scout.active_registration',return_value=('test',{})),patch('tennis_hardcourt_scout.registrations',return_value=[('test',{})]):
            v=m.report(self.root,m.SCOUT,raw)
        self.assertEqual((v['pending'],v['overdue'],v['void'],v['selections'][0]['pnl_units']),(0,0,1,0))
        self.assertEqual(raw['pending'],1)
    def test_conflicting_stats_winner_or_loser(self):
        for a,b in [('1','2'),('2','1')]:
            self.write('stat',[dict(self.g,winner_id=a,loser_id=b)]);self.assertEqual(self.verify()['retained'],0)
    def test_collision_after_prior_grade(self):
        self.verify();self.write('games',[dict(self.g,result='6-4 6-2')]);self.verify()
        self.assertEqual(m.read(self.folder/m.EVIDENCE)[self.key]['status'],'quarantined')
    def test_wrong_round_and_tournament(self):
        for k in ('round_id','tour_id'):
            self.write('nonplayed-results',[dict(self.g,**{k:'44'})]);self.assertEqual(self.verify()['retained'],0)
    def test_post_start_capture(self):
        r=dict(self.capture,registered_at=self.capture['quote']['kickoff_iso']);atomic(self.folder/'captures/x.json',r)
        self.assertEqual(self.verify()['retained'],0)
    def test_terminal_untouched(self):
        atomic(self.folder/'outcomes.json',{self.key:dict(status='settled',winner_id='1')});self.assertEqual(self.verify()['retained'],0)
    def test_most_df_distinguishes_review(self):
        d=self.root/m.DF;(d/'captures').mkdir(parents=True);atomic(d/'registration.json',{})
        atomic(d/'captures/x.json',dict(id='x',tour='ATP',tour_id='12',round_id='4',players=['2','1'],start=self.capture['quote']['kickoff_iso'],captured_at=self.capture['registered_at']))
        m.evidence_for_lane(self.root,m.DF,now);v=m.report(self.root,m.DF,dict(selections=[dict(id='x',status='pending')]))
        self.assertEqual(v['verified_walkovers_for_contract_review'],['x']);self.assertEqual(v['selections'][0]['status'],'pending')
    def test_exact_venue(self):
        t={'name':'BNP Paribas Nordic Open - Stockholm'}
        self.assertTrue(bp.walkover_venue('ATP','Stockholm Open',t))
        self.assertFalse(bp.walkover_venue('WTA','Stockholm Open',t))
        self.assertFalse(bp.walkover_venue('ATP','Stockholm Open',{'name':'Stockholm Challenger'}))
    def test_valid_known_cancellation_timing(self):
        self.assertTrue(m.in_time('2026-11-03T11:30:00Z','2026-11-03T09:30:00Z','2026-11-02',now))
        self.assertFalse(m.in_time('2026-11-03T11:30:00Z','2026-11-03T12:30:00Z','2026-11-02',now))
        self.assertFalse(m.in_time('2026-11-03T11:30:00Z','2026-11-03T09:30:00Z','2026-10-02',now))
if __name__=='__main__':unittest.main()

