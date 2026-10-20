import copy
from datetime import UTC, datetime, timedelta
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import goalkeeper_keeper_watch as w
from football_identity import write, read


class KeeperWatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.now=datetime(2026,1,19,9,tzinfo=UTC)
        self.params={'alpha':.1,'beta':[0]*10,'centers':[0]*9,'scales':[1]*9,
                     'features':[str(i) for i in range(9)],'fallback_mean':3,'league_venue_means':{}}
        config={'start_at':(self.now-timedelta(hours=1)).isoformat(),'candidate_params':self.params,
                'candidate_params_sha256':w.digest(self.params),'control_params_sha256':w.digest(self.params)}
        write(self.root/'data/goalkeeper-saves/keeper-watch-v1.json',config)
        self.row={'captured_at':(self.now-timedelta(minutes=1)).isoformat(),'kickoff_at':'2026-01-20T18:00:00Z',
            'event_id':'10','blockers':'','lineup_status':'predicted_starter','venue':'home',
            '_research_features':[0]*9,'_research_lineup':{'fotmob_match_id':'100','home_fotmob_team_id':'2',
                'home_starters':[{'role_group':'GK','name':'Keeper One','player_id':1}]},
            'bookmaker':'Bet365','odds_decimal':2,'line':2.5,'side':'over','model_mean':3,
            'league':'epl','goalkeeper':'Keeper One','home_team':'Home','away_team':'Away'}

    def result(self, saves=4, conflict=False, starter=True):
        keepers=[{'player_id':1,'team_id':2,'started':starter,'minutes':90,'saves':saves,'event_saves':saves,'target_conflict':conflict},
                 {'player_id':3,'team_id':4,'started':True,'minutes':90,'saves':2,'event_saves':2,'target_conflict':False}]
        write(self.root/'data/aerial/keeper-history.json.gz',{'fixtures':{'100':[{
            'observed_at':'2026-01-20T22:00:00Z','kickoff':'2026-01-20T18:00:00Z',
            'league_id':'47','keepers':keepers,'source_sha256':str(saves)}]}})

    def run_watch(self, rows=None, now=None):
        return w.run([self.row] if rows is None else rows,self.params,self.root,now=now or self.now)

    def test_verified_alternative_starter_voids_predicted_keeper(self):
        self.run_watch(); self.result()
        path=self.root/'data/aerial/keeper-history.json.gz'
        data=read(path); data['fixtures']['100'][0]['keepers'][0]['player_id']=99
        write(path,data)
        result=self.run_watch([],self.now+timedelta(days=3))
        for arm in ('current','keeper_watch'):
            self.assertEqual(result['records'][arm]['voids'],1)
            self.assertEqual(result['records'][arm]['overdue'],0)
            self.assertEqual(result['records'][arm]['profit'],0)

    def test_incomplete_alternative_starter_stays_review(self):
        row={'match_id':'100','player_id':'1','team_id':'2','kickoff_at':'2026-01-20T18:00:00Z'}
        source={'kickoff':row['kickoff_at'],'source_hash':'test','full_match_agreement':False,
                'keepers':[{'player_id':99,'team_id':2,'started':True,'minutes':45}]}
        self.assertEqual(w.outcome(row,{'100':source},self.now)['status'],'review')

    def test_capture_is_paired_and_idempotent_with_locked_odds(self):
        a=self.run_watch();self.assertEqual(a['forecast_keepers'],1);self.assertEqual(a['new_selections'],2)
        row=copy.deepcopy(self.row);row['odds_decimal']=2.5
        b=self.run_watch([row]);self.assertEqual(b['new_forecasts'],0);self.assertEqual(b['new_selections'],0)
        self.assertTrue(all(r['odds']==2 for r in b['selections']))

    def test_no_old_or_late_capture(self):
        old=copy.deepcopy(self.row);old['captured_at']='2026-01-18T23:00:00Z'
        self.assertEqual(self.run_watch([old])['forecast_keepers'],0)
        self.assertEqual(self.run_watch(now=self.now+timedelta(days=3))['forecast_keepers'],0)

    def test_identity_and_blockers_fail_closed(self):
        row=copy.deepcopy(self.row);row['_research_lineup']['home_starters'][0]['name']='Other Keeper'
        self.assertEqual(self.run_watch([row])['forecast_keepers'],0)
        row=copy.deepcopy(self.row);row['blockers']='missing_history'
        self.assertEqual(self.run_watch([row])['forecast_keepers'],0)

    def test_future_outcomes_not_used(self):
        self.result();a=self.run_watch();self.assertEqual(a['paired_settled_fixtures'],0)
        forecasts=w.load_records(self.root/'data/goalkeeper-saves/keeper-watch/forecasts')
        self.assertTrue(all(r['history']['appearances']==0 for r in forecasts))

    def test_settlement_and_roi(self):
        self.run_watch();self.result();a=self.run_watch([],self.now+timedelta(days=3))
        self.assertEqual(a['paired_settled_fixtures'],1)
        self.assertEqual(a['records']['keeper_watch']['profit'],.5)
        self.assertEqual(a['records']['keeper_watch']['roi'],1)
        self.assertEqual(a['records']['current']['wins'],1)

    def test_conflicts_not_graded(self):
        self.run_watch();self.result(conflict=True);a=self.run_watch([],self.now+timedelta(days=4))
        self.assertEqual(a['paired_settled_fixtures'],0)
        self.assertEqual(a['records']['keeper_watch']['review'],1)
        self.assertEqual(a['records']['keeper_watch']['overdue'],1)

    def test_result_revisions_require_review(self):
        self.run_watch();self.result();self.run_watch([],self.now+timedelta(days=3))
        self.result(1);a=self.run_watch([],self.now+timedelta(days=4))
        self.assertEqual(a['paired_settled_fixtures'],0)
        self.assertEqual(a['records']['keeper_watch']['review'],1)

    def test_nonstarter_void_and_no_probability_score(self):
        self.run_watch();self.result(starter=False);a=self.run_watch([],self.now+timedelta(days=3))
        self.assertEqual(a['paired_settled_fixtures'],0)
        self.assertEqual(a['records']['keeper_watch']['voids'],1)
        self.assertIsNone(a['records']['keeper_watch']['roi'])

    def test_configuration_change_blocks(self):
        self.run_watch();p=self.root/'data/goalkeeper-saves/keeper-watch-v1.json'
        r=read(p);r['start_at']='2026-01-19T07:00:00Z';write(p,r)
        with self.assertRaisesRegex(ValueError,'configuration'):self.run_watch()

    def test_live_change_blocks(self):
        self.params['fallback_mean']=4
        with self.assertRaisesRegex(ValueError,'Current model changed'):self.run_watch()

    def test_feature_parity_with_registered_formula(self):
        ids={'player_id':'1','team_id':'2'};h={('1','2','epl'):[{'date':'2026-01-18','saves':5}]}
        f,c=w.keeper_feature(0,ids,'epl',self.now,h)
        self.assertAlmostEqual(w.math.exp(f),15/11)
        h[('1','2','epl')].append({'date':'2026-01-19','saves':999})
        self.assertEqual(w.keeper_feature(0,ids,'epl',self.now,h)[0],f)

    def test_weekly_empty_state_clear(self):
        text=w.weekly_text(self.run_watch([]))
        self.assertIn('AWAITING_FIRST_CAPTURE',text);self.assertIn('awaiting settlement',text)

if __name__=='__main__':unittest.main()
