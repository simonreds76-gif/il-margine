from pathlib import Path
import sys
import unittest
from unittest.mock import Mock,patch
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from penalty_review_hot import merge_rows,notify,select_due,validate_payload,run
from datetime import datetime,timezone,timedelta
import copy,json,tempfile,contextlib,io

def row(mid,date='2026-10-25'):
    return {'date':date,'actual_taker':'Player','event_evidence':[{'match_id':str(mid)}]}

class HotPenaltyTests(unittest.TestCase):
    def test_retains_other_matches_and_replaces_exact_fixture(self):
        old=[row(1),row(2)];fresh=[{**row(2),'actual_taker':'Correct player'}]
        result=merge_rows(old,fresh,{'2'},'2026-10-17')
        self.assertEqual(len(result),2);self.assertIn(row(1),result);self.assertIn(fresh[0],result)
    def test_failed_fixture_keeps_prior_evidence(self):
        self.assertEqual(merge_rows([row(1)],[],set(),'2026-10-17'),[row(1)])
    def test_verified_no_penalty_removes_stale_fixture(self):
        self.assertEqual(merge_rows([row(1)],[],{'1'},'2026-10-17'),[])
    def test_prunes_only_expired_window(self):
        self.assertEqual(merge_rows([row(1,'2026-10-01'),row(2)],[],set(),'2026-10-17'),[row(2)])
    def test_existing_undelivered_recent_rows_are_retried(self):
        older=row(1,'2026-10-24');recent=row(2)
        a=SimpleNamespace(DEFAULT_ALERT_STATE=Path('state.json'),REVIEW_FILES=[],
            load_alert_state=Mock(return_value={'items':{'already_sent':{}}}),load_reviews=Mock(return_value={'tickets':{}}),
            previous_rows=Mock(return_value=[older,recent]),current_rows=Mock(return_value=[older,recent]),
            priority_hierarchy_teams=Mock(return_value={}),new_actionable_rows=Mock(return_value=[]))
        with patch('penalty_review_hot.load',return_value=a),patch.object(Path,'exists',return_value=False):
            notify(Path('/isolated'),dry_run=True)
        args=a.new_actionable_rows.call_args.args
        self.assertEqual(args[1],[older]);self.assertEqual(args[3],{'already_sent'});a.load_reviews.assert_called_once()


def fixture(mid=1, kickoff='2026-10-25T12:00:00Z'):
    return {'state':'pending','league':'test','league_id':55,'date':kickoff[:10],
            'first_seen':'2026-10-25T12:00:00+00:00',
            'match':{'id':mid,'home':{'id':10,'name':'Home'},'away':{'id':20,'name':'Away'},
                     'status':{'utcTime':kickoff,'finished':True}}}

def payload(mid=1):
    return {'props':{'pageProps':{
        'general':{'matchId':mid,'parentLeagueId':55,'homeTeam':{'id':10,'name':'Home'},
                   'awayTeam':{'id':20,'name':'Away'},'matchTimeUTCDate':'2026-10-25T12:00:00Z','finished':True},
        'header':{'status':{'finished':True,'scoreStr':'0 - 0'}},
        'content':{'shotmap':{'shots':[{'id':1,'teamId':10,'eventType':'Miss','situation':'RegularPlay'}]},
                   'matchFacts':{'events':{'ongoing':False,'events':[]}}}}}}

class CoverageTests(unittest.TestCase):
    def test_verified_scoreless_match(self):
        self.assertEqual(validate_payload(payload(),fixture()),set())
    def test_incomplete_data_never_means_no_penalty(self):
        for field,value,reason in [
            ('shots',[],'empty_or_missing_shotmap'),('score','1 - 0','shotmap_score_disagreement'),
            ('name','','missing_match_metadata'),('team',30,'unrecognized_shot_team'),
            ('id',2,'match_identity_mismatch'),('ongoing',True,'incomplete_event_timeline')]:
            with self.subTest(field=field):
                p=payload();v=p['props']['pageProps']
                if field=='shots':v['content']['shotmap']['shots']=value
                elif field=='score':v['header']['status']['scoreStr']=value
                elif field=='name':v['general']['homeTeam']['name']=value
                elif field=='team':v['content']['shotmap']['shots'][0]['teamId']=value
                elif field=='id':v['general']['matchId']=value
                else:v['content']['matchFacts']['events']['ongoing']=value
                with self.assertRaisesRegex(ValueError,reason):validate_payload(p,fixture())
    def test_timeline_penalty_missing_from_shots_rejected(self):
        p=payload();p['props']['pageProps']['content']['matchFacts']['events']['events']=[{'goalDescriptionKey':'penalty','shotmapEvent':{'id':99}}]
        with self.assertRaisesRegex(ValueError,'penalty_event_shotmap_disagreement'):validate_payload(p,fixture())
    def test_saved_penalty_without_link_uses_exact_player_side_and_minute(self):
        p=payload();v=p['props']['pageProps']
        v['content']['shotmap']['shots'][0].update(situation='Penalty',playerId=7,fullName='Player',min=68)
        e={'type':'MissedPenalty','player':{'id':7},'isHome':True,'time':68}
        v['content']['matchFacts']['events']['events']=[e]
        self.assertEqual(validate_payload(p,fixture()),{'1'})
        e['isHome']=False
        with self.assertRaisesRegex(ValueError,'penalty_event_shotmap_disagreement'):validate_payload(p,fixture())
    def test_penalty_requires_identity(self):
        p=payload();shot=p['props']['pageProps']['content']['shotmap']['shots'][0];shot['situation']='Penalty'
        with self.assertRaisesRegex(ValueError,'incomplete_penalty_identity'):validate_payload(p,fixture())
        shot.update(playerId=7,fullName='Player')
        self.assertEqual(validate_payload(p,fixture()),{'1'})
    def test_shootout_does_not_create_league_penalty(self):
        p=payload();v=p['props']['pageProps'];v['content']['shotmap']['shots'][0].update(situation='Penalty',period='PenaltyShootout')
        v['content']['matchFacts']['events']['events']=[{'isPenaltyShootoutEvent':True,'goalDescriptionKey':'penalty'}]
        self.assertEqual(validate_payload(p,fixture()),set())
    def test_failures_cannot_starve_new_matches(self):
        now=datetime(2026,10,25,20,tzinfo=timezone.utc)
        fs={str(i):{**fixture(i),'last_attempt':now.isoformat()} for i in range(16)}
        fs['new']=fixture(99)
        self.assertEqual(select_due(fs,now)[0][0],'new')
    def test_old_pending_fixture_does_not_age_out(self):
        now=datetime(2026,10,25,20,tzinfo=timezone.utc)
        self.assertEqual(select_due({'1':fixture(1,'2026-09-01T12:00:00Z')},now)[0][0],'1')
    def test_retry_backoff_and_future_matches(self):
        now=datetime(2026,10,25,20,tzinfo=timezone.utc)
        fs={'1':{**fixture(),'next_attempt':(now+timedelta(minutes=30)).isoformat()},'2':fixture(2,'2026-10-26T12:00:00Z')}
        self.assertEqual(select_due(fs,now),[])
    def test_unresolved_evidence_retained_beyond_display_window(self):
        old=row(1,'2026-09-01')
        self.assertEqual(merge_rows([old],[],set(),'2026-10-17',{'1'}),[old])
    def scenario(self, mode):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            root=Path(tmp);d=root/'data/goalscorer';d.mkdir(parents=True)
            statepath=d/'penalty-hot-capture-state.json';out=d/'review.json'
            old=row(1);out.write_text(json.dumps({'rows':[old]}),encoding='utf-8')
            f=fixture(1,'2026-09-01T12:00:00Z');f['first_seen']='2026-09-01T12:00:00+00:00'
            statepath.write_text(json.dumps({'fixtures':{'1':f},'discovery':{}}),encoding='utf-8')
            p=payload()
            if mode=='empty':p['props']['pageProps']['content']['shotmap']['shots']=[]
            if mode=='unknown':p['props']['pageProps']['content']['shotmap']['shots'][0].update(situation='Penalty',playerId=7,fullName='Player')
            def build(league,dates,health):
                health.update(complete=True,matches_checked=1)
                return [{**row(1),'event_evidence':[{'match_id':'1','source_event_id':'1'}]}] if mode=='unknown' else []
            fetch=Mock(return_value={'leagues':[]})
            if mode=='outage':fetch.side_effect=TimeoutError()
            if mode=='malformed':fetch.return_value={'leagues':[{'id':55,'matches':[{},fixture(2)['match']]}]}
            review=SimpleNamespace(MATCHES_URL='daily',LEAGUE_CONFIGS={'test':{'league_id':55,'output_json':out,'output_csv':d/'review.csv'}},
                _fetch_json=fetch,_fetch_match_payload=Mock(return_value=p),build_live_review_rows=build,
                _write_csv=Mock(),_write_json=lambda path,obj:path.write_text(json.dumps(obj),encoding='utf-8'))
            alerts=SimpleNamespace(has_reliable_pitch_context=lambda r:False)
            with patch('penalty_review_hot.load',side_effect=[review,alerts]), patch.dict('os.environ',{'GITHUB_STEP_SUMMARY':''}), contextlib.redirect_stdout(io.StringIO()):
                result=run(root,datetime(2026,10,25,20,tzinfo=timezone.utc))
            return result,json.loads(out.read_text(encoding='utf-8'))
    def test_bad_listing_row_does_not_hide_following_fixture(self):
        state,_=self.scenario('malformed')
        self.assertIn('2',state['fixtures'])
        self.assertEqual(len(state['coverage']['failed_discovery_days']),3)
    def test_empty_match_retains_saved_evidence_and_pending_status(self):
        state,queue=self.scenario('empty')
        self.assertEqual(queue['rows'],[row(1)])
        self.assertEqual(state['fixtures']['1']['reason'],'empty_or_missing_shotmap')
        self.assertEqual(state['checked'],{})
    def test_backlog_recovers_after_calendar_window(self):
        state,_=self.scenario('good')
        self.assertEqual(state['fixtures']['1']['state'],'verified')
    def test_listing_outage_does_not_block_known_backlog(self):
        state,_=self.scenario('outage')
        self.assertEqual(len(state['coverage']['failed_discovery_days']),3)
        self.assertEqual(state['fixtures']['1']['state'],'verified')
    def test_uncertain_player_timeline_remains_pending_and_visible(self):
        state,queue=self.scenario('unknown')
        self.assertEqual(state['fixtures']['1']['reason'],'unresolved_player_timeline')
        self.assertEqual(state['coverage']['stalled'],1)
        self.assertTrue(queue['rows'])

if __name__=='__main__':unittest.main()
