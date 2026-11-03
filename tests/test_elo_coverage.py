import copy, hashlib, importlib.util, json, sys, tempfile, unittest
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

HERE=Path(__file__).parent
SCRIPTS=HERE.parent/'scripts'
sys.path.insert(0,str(SCRIPTS))
import tennis_elo_health as H
import tennis_input_health as I
spec=importlib.util.spec_from_file_location('native',SCRIPTS/'tennis_elo_native_source.py')
N=importlib.util.module_from_spec(spec);spec.loader.exec_module(N)
NOW=datetime(2026,11,3,12,tzinfo=timezone.utc)

def rating(pid,surface='I.hard',value=1489,count=1):
    return dict(player_id=pid,surface=surface,elo=value,match_count=count,latest_result='2026-09-27')

class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.folder=self.root/'data/tennis-elo-source/native-adult-v1';self.folder.mkdir(parents=True)
        self.required={11:{'I.hard'},22:{'I.hard'}}
        self.method={'initial':1500,'overall_k':22,'surface_k':22}
        self.source()
    def save(self,path,value):path.write_text(json.dumps(value))
    def source(self):
        native=self.root/'data/oncourt';native.mkdir(parents=True,exist_ok=True)
        source_hashes={}
        for name in ('players_atp.csv','tours_atp.csv','games_atp.csv','courts.csv'):
            p=native/name;p.write_text('id,name\n')
            source_hashes['data/oncourt/'+name]=hashlib.sha256(p.read_bytes()).hexdigest()
        candidate={'version':'native-adult-elo-source-v1-20261101','live_writes':False,
                   'as_of_exclusive':'2026-11-03','latest_available_result':'2026-11-02',
                   'method':self.method,'source_hashes':source_hashes,
                   'ratings':[rating(11),rating(11,'Overall'),rating(22,'Overall')]}
        self.save(self.folder/'candidate.json',candidate)
        (self.folder/'history.json.gz').write_bytes(b'fixture-history')
        status={k:v for k,v in candidate.items() if k!='ratings'}
        status.update(checked_at='2026-11-03T10:00:00+00:00',state='VALIDATED_RESEARCH_SOURCE',
                      history_matches=10,rating_rows=3,missing_player_followup=[{'player_id':999}])
        for name,key in [('candidate.json','candidate_sha256'),('history.json.gz','history_file_sha256')]:
            status[key]=hashlib.sha256((self.folder/name).read_bytes()).hexdigest()
        self.save(self.folder/'status.json',status)
    def mutate_status(self,**kw):
        p=self.folder/'status.json';s=json.loads(p.read_text());s.update(kw);self.save(p,s)
    def status(self):
        return {'fixtures':[{'missing_elo_keys':[[11,'I.hard']]},{'missing_elo_keys':[[22,'I.hard']]}]}
    def annotate(self,status=None):
        status=copy.deepcopy(status or self.status())
        published={22:{'overall':1377,'surface_blended':{'Hard':1298.5}}}
        with patch.object(H,'published_source',return_value=({'state':'CURRENT'},published)):
            H.annotate_sources(self.root,status,[],NOW,{11:'Player One',22:'Player Two'})
        return status
    def test_followup_tracks_current_ids_not_saved_focus(self):
        r=H.native_research_source(self.root,NOW,self.required,{11:'Player One'})
        self.assertEqual([p['player_id'] for p in r['missing_player_followup']],[11,22])
        self.assertEqual(r['missing_player_followup'][0]['name'],'Player One')
    def test_required_surfaces_are_dynamic(self):
        s={'fixtures':[{'missing_elo_keys':[[44,'Clay'],[44,'Overall']]}]}
        self.assertEqual(H.missing_requirements(s),{44:{'Clay','Overall'}})
    def test_inactive_saved_rows_are_not_current_gaps(self):
        s=self.status();s['fixtures'][0]['active_for_coverage']=False
        self.assertEqual(H.missing_requirements(s),{22:{'I.hard'}})
    def test_missing_activity_marker_is_conservative(self):
        self.assertEqual(H.missing_requirements(self.status()),self.required)
    def test_one_match_vs_no_validated_history(self):
        s=self.annotate();a,b=s['missing_elo_players']
        self.assertEqual(a['assessments']['I.hard']['validated_match_count'],1)
        self.assertEqual(a['assessments']['I.hard']['reconstructed_rating'],1489)
        self.assertEqual(b['assessments']['I.hard']['state'],'NO_VALIDATED_SURFACE_HISTORY')
        self.assertEqual(s['missing_input_classification']['no_validated_surface_history'],1)
    def test_published_hard_blend_never_called_indoor_rating(self):
        p=self.annotate()['missing_elo_players'][1]['assessments']['I.hard']
        self.assertEqual(p['published_kind'],'hard_blend_proxy_not_indoor')
        self.assertFalse(p['live_changed'])
    def test_broken_hash_does_not_become_no_history(self):
        (self.folder/'candidate.json').write_text('{}')
        s=self.annotate()
        self.assertEqual(s['missing_input_classification']['history_unverified'],2)
        self.assertIsNone(s['missing_elo_players'][0]['assessments']['I.hard']['validated_match_count'])
    def test_stale_observation_does_not_become_no_history(self):
        self.mutate_status(checked_at=(NOW-timedelta(days=3)).isoformat())
        s=self.annotate();self.assertEqual(s['missing_input_classification']['history_unverified'],2)
    def test_future_cutoff_is_invalid(self):
        self.mutate_status(as_of_exclusive='2026-11-05')
        self.assertEqual(H.native_research_source(self.root,NOW,self.required)['state'],'INVALID_EVIDENCE')
    def test_new_export_requires_history_refresh_not_false_zero(self):
        (self.root/'data/oncourt/games_atp.csv').write_text('new result')
        s=self.annotate()
        self.assertEqual(s['elo_sources']['native_adult_research']['state'],'SOURCE_EXPORTS_CHANGED')
        self.assertEqual(s['missing_input_classification']['history_unverified'],2)
    def test_stale_result_cutoff_visible(self):
        self.mutate_status(latest_available_result='2026-10-20')
        self.assertFalse(H.native_research_source(self.root,NOW,self.required)['integrity_verified'])
    def test_duplicate_research_keys_rejected(self):
        with self.assertRaises(ValueError):H.research_followup([rating(11),rating(11)],self.required)
    def test_invalid_research_values_rejected(self):
        for value in (float('nan'),float('inf'),-1):
            with self.assertRaises(ValueError):H.research_followup([rating(11,value=value)],self.required)
    def test_zero_observations_not_real_rating(self):
        with self.assertRaises(ValueError):H.research_followup([rating(11,count=0)],self.required)
    def test_observer_does_not_change_rating_files(self):
        before={p.name:p.read_bytes() for p in self.folder.iterdir()}
        self.annotate()
        self.assertEqual(before,{p.name:p.read_bytes() for p in self.folder.iterdir()})
    def test_text_keeps_research_and_live_separate(self):
        s=self.annotate();s.update(status='MISSING',checked_at=NOW.isoformat(),active_fixtures_missing_elo=2,active_fixture_count=10)
        text=I.text(s)
        self.assertIn('1489.0 remains research-only',text)
        self.assertIn('no validated surface history',text)
        self.assertIn('not an indoor record',text)
        self.assertIn('2/10',text)
    def test_native_followup_reads_new_requirement_without_rebuild(self):
        d=self.root/'data/oncourt';d.mkdir(parents=True,exist_ok=True)
        (d/'players_atp.csv').write_text('id,name\n11,Player One\n22,Player Two\n')
        h=self.root/'data/tennis-input-health';h.mkdir(parents=True)
        self.save(h/'status.json',self.status())
        self.assertEqual(len(N.current_followup(self.root,[rating(11)])),2)
        self.save(h/'status.json',{'fixtures':[{'missing_elo_keys':[[22,'Clay']]}]})
        second=N.current_followup(self.root,[rating(11)])
        self.assertEqual([x['player_id'] for x in second],[22])
        self.assertEqual(second[0]['required_surfaces'],['Clay'])
    def test_observe_separates_active_from_inactive_and_keeps_unpriced(self):
        f1=dict(tour_id=1,round_id=4,player1_id=11,player2_id=22,surface='I.hard')
        f2=dict(tour_id=2,round_id=4,player1_id=33,player2_id=44,surface='Clay')
        f3=dict(tour_id=3,round_id=4,player1_id=55,player2_id=66,surface='Grass')
        def get(table,params):return [f1,f2] if table=='daily_fair_odds' else []
        with patch.object(I,'scheduled_candidates',return_value=([f1,f3],{})):
            out=I.observe(self.root,get,NOW)['status']
        self.assertEqual(out['active_fixture_count'],2)
        self.assertEqual(out['inactive_stored_forecasts_missing_elo'],1)
        self.assertEqual(out['unpriced_export_candidates'],1)
        self.assertNotIn(33,[p['player_id'] for p in out['missing_elo_players']])
    def test_missing_schedule_never_reports_empty_complete_coverage(self):
        f=dict(tour_id=1,round_id=4,player1_id=11,player2_id=22,surface='I.hard')
        def get(table,params):return [f] if table=='daily_fair_odds' else []
        with patch.object(I,'scheduled_candidates',return_value=([],{'export_missing':1})):
            out=I.observe(self.root,get,NOW)['status']
        self.assertEqual(out['active_elo_coverage'],'SCHEDULE_UNAVAILABLE')
        self.assertEqual(out['active_fixture_count'],1)
    def test_inactive_gap_retained_without_false_active_alarm(self):
        f1=dict(tour_id=1,round_id=4,player1_id=11,player2_id=22,surface='I.hard')
        f2=dict(tour_id=2,round_id=4,player1_id=33,player2_id=44,surface='Clay')
        elo=[rating(p,s) for p in (11,22) for s in ('Overall','I.hard')]
        def get(table,params):return [f1,f2] if table=='daily_fair_odds' else elo
        with patch.object(I,'scheduled_candidates',return_value=([f1],{})):
            out=I.observe(self.root,get,NOW)['status']
        self.assertEqual(out['active_elo_coverage'],'COMPLETE')
        self.assertEqual(out['status'],'ELO_LINEAGE_UNVERIFIED')
        self.assertEqual(out['inactive_stored_forecasts_missing_elo'],1)
        self.assertEqual(out['stored_forecasts_missing_elo'],1)

if __name__=='__main__':unittest.main()
