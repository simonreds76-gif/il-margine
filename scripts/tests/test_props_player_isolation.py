import csv
from datetime import date, datetime, timezone, timedelta
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(SCRIPTS))
import tennis_props_identity_health as I
import tennis_props_current_history as H
import tennis_props_full_refresh as A
import tennis_pairing_consistency as P
spec=importlib.util.spec_from_file_location('isolation_board',SCRIPTS/'build-tennis-props-board.py')
B=importlib.util.module_from_spec(spec);spec.loader.exec_module(B)

def write(path,rows,fields=None):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields or list(rows[0]));w.writeheader();w.writerows(rows)

class IsolationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        for tour in ('atp','wta'):
            write(self.root/f'data/oncourt/players_{tour}.csv',[dict(id='33355',name='Jodie Anna Burrage',birthdate='1999-05-28',country='GBR')])
            write(self.root/f'data/sackmann/{tour}_players.csv',[dict(player_id='214839',name_first='Jodie',name_last='Burrage',dob='19990528',ioc='GBR')])
        self.good=[dict(tour='ATP',player_id='p1',player_name='Player One'),dict(tour='WTA',player_id='p2',player_name='Player Two')]
        self.bad=[dict(tour='WTA',player_id='oc:33355',player_name='Jodie Anna Burrage'),dict(tour='WTA',player_id='214839',player_name='Jodie Burrage')]
        self.baseline=self.good+self.bad
    def status(self):
        clean,audit=I.quarantine_identity_buckets(self.root,self.baseline)
        return dict(state='CURRENT',version=H.VERSION,as_of='2026-11-04',identity_audit=audit,output_hashes={'player-props-baseline.csv':'x'})
    def test_verified_conflict_is_local_and_strict_check_remains(self):
        with self.assertRaisesRegex(ValueError,'verified_split'):I.verify_identity_buckets(self.root,self.baseline)
        clean,audit=I.quarantine_identity_buckets(self.root,self.baseline)
        self.assertEqual(clean,self.good);self.assertEqual(self.baseline,self.good+self.bad)
        self.assertEqual(audit['excluded_baseline_rows'],2)
    def test_fixture_with_conflicted_opponent_is_held_but_other_tour_is_not(self):
        fixtures=[dict(tour='WTA',player1_id='9',player2_id='33355'),dict(tour='ATP',player1_id='9',player2_id='33355'),dict(tour='WTA',player1_id='9',player2_id='8')]
        ready,held=I.partition_schedules(fixtures,self.status(),'2026-11-04')
        self.assertEqual(ready,fixtures[1:]);self.assertEqual(len(held),1)
        self.assertEqual(held[0]['quarantine_reason'],'VERIFIED_SPLIT_IDENTITY')
    def test_canonical_alias_is_also_held_and_stale_receipt_is_rejected(self):
        row=dict(tour='WTA',player1='Jodie Burrage',player2='Someone Else')
        self.assertEqual(I.partition_schedules([row],self.status(),'2026-11-04')[0],[])
        with self.assertRaisesRegex(ValueError,'not from current'):I.partition_schedules([row],self.status(),'2026-11-05')
    def test_activity_does_not_reintroduce_native_or_archive_bucket(self):
        self.assertEqual(I.exclude_quarantined_activity(self.baseline,self.status()['identity_audit']),self.good)
    def test_same_name_different_person_not_automatically_merged_or_quarantined(self):
        write(self.root/'data/oncourt/players_wta.csv',[dict(id='33355',name='Jodie Anna Burrage',birthdate='2000-01-01',country='GBR')])
        clean,audit=I.quarantine_identity_buckets(self.root,self.baseline)
        self.assertEqual(clean,self.baseline);self.assertEqual(len(audit['unverified_name_candidates']),1)
    def test_resolution_automatically_restores_fixture(self):
        _,audit=I.quarantine_identity_buckets(self.root,self.good+[self.bad[1]])
        status=dict(self.status(),identity_audit=audit)
        row=dict(tour='WTA',player1_id='33355',player2_id='8')
        self.assertEqual(I.partition_schedules([row],status,'2026-11-04'),([row],[]))
    def test_prepare_publishes_other_players_when_split_injected(self):
        for tour in ('atp','wta'):
            for kind in ('tours','games','stat'):
                write(self.root/f'data/oncourt/{kind}_{tour}.csv',[dict(id='1')])
        write(self.root/'data/oncourt/courts.csv',[dict(id='1')])
        write(self.root/'data/tennis-props/player-name-aliases.csv',[],['tour','alias','player_name'])
        baseline=self.good*51+self.bad
        audit={tour:dict(overlap_matches=150,latest_appended='2026-11-03',parity={field:dict(n=150,exact=150) for field in ('w_ace','l_ace','w_df','l_df')}) for tour in ('atp','wta')}
        def sources(as_of,out):
            (out/'source-audit.json').write_text(json.dumps({'hashes':{}}));return {},[],audit
        with patch.object(A,'ROOT',A.ROOT),patch.object(A,'sources',side_effect=sources),patch.object(A,'build',return_value=baseline),patch.object(H,'activity',return_value=(self.baseline,{},{})),patch('tennis_source_contract.court_surfaces',return_value={'1':'Hard','2':'Clay','3':'Hard','4':'Carpet','5':'Grass','6':'Hard'}):
            status=H.prepare(self.root,date(2026,11,4),self.root/'prepared')
        self.assertEqual(status['state'],'CURRENT');self.assertEqual(status['coverage'],'PARTIAL_QUARANTINE')
        self.assertEqual(H.read(self.root/'prepared/player-props-baseline.csv'),self.good*51)
        self.assertEqual(H.read(self.root/'prepared/player-props-activity.csv'),self.good)
        self.assertEqual(H.history_health(self.root/'prepared','2026-11-04')['state'],'CURRENT')
    def test_completeness_accepts_only_declared_held_fixture_not_other_missing_rows(self):
        props=self.root/'data/tennis-props';props.mkdir(exist_ok=True)
        (props/'player-history-status.json').write_text('{}')
        good=dict(tour='ATP',tour_id='1',round='R1',player1_id='1',player2_id='2')
        bad=dict(tour='WTA',tour_id='2',round='R1',player1_id='33355',player2_id='3')
        rows=[dict(tour='ATP',tour_id='1',round='R1',player_id=a,opponent_id=b,generation_date='2026-11-04',history_as_of='2026-11-04',history_version=H.VERSION,history_fingerprint='x') for a,b in [('1','2'),('2','1')]]
        write(self.root/P.BOARD,rows)
        with patch.object(P,'native_epoch',return_value={'native':{'mtime_ns':1}}),patch.object(H,'history_health',return_value=self.status()):
            s=P.board_state(self.root,'2026-11-04',expected=[good,bad]);self.assertEqual(s['state'],'CURRENT');self.assertEqual(s['coverage'],'PARTIAL_QUARANTINE')
            write(self.root/P.BOARD,rows[:1]);self.assertEqual(P.board_state(self.root,'2026-11-04',expected=[good,bad])['state'],'REBUILD_REQUIRED')
            write(self.root/P.BOARD,[dict(r,history_fingerprint='old') for r in rows]);self.assertEqual(P.board_state(self.root,'2026-11-04',expected=[good,bad])['state'],'REBUILD_REQUIRED')
    def test_missing_native_name_and_surface_hold_only_their_fixtures(self):
        rows=[dict(tour_id='1',player1_id='1',player2_id='2',date='2026-11-04',round_id='4',result=''),dict(tour_id='1',player1_id='1',player2_id='999',date='2026-11-04',round_id='4',result=''),dict(tour_id='2',player1_id='1',player2_id='2',date='2026-11-04',round_id='4',result='')]
        tours={'1':dict(id='1',name='Paris',court_id='3',rank='4',date='2026-11-02'),'2':dict(id='2',name='Paris',court_id='999',rank='4',date='2026-11-02')}
        held=[]
        with patch.object(B,'court_surfaces',return_value={'3':'Hard'}),patch.object(B,'load_oncourt_player_names',return_value={'1':'Player One','2':'Player Two'}),patch.object(B,'load_oncourt_tours',return_value=tours),patch.object(B,'read_csv',return_value=rows):
            ready=B.oncourt_schedule_rows('ATP',False,'2026-11-04',3,held)
        self.assertEqual(len(ready),1);self.assertEqual([r['quarantine_reason'] for r in held],['MISSING_PLAYER_IDENTITY','UNKNOWN_EVENT_SURFACE'])

    def receipt(self, now=None):
        held=[dict(tour='WTA',tour_id='1',round='R1',player1='Jodie Anna Burrage',player2='Player Two',player1_id='33355',player2_id='2',quarantine_reason='VERIFIED_SPLIT_IDENTITY')]
        return I.publish_quarantine(self.root,self.status(),[],held,'2026-11-04',now)

    def test_holds_do_not_silently_expire_and_resolved_rebuild_clears_them(self):
        now=datetime(2026,11,4,tzinfo=timezone.utc)
        first=self.receipt(now);later=self.receipt(now+timedelta(days=3))
        self.assertEqual(first['held_fixtures'][0]['first_seen_at'],later['held_fixtures'][0]['first_seen_at'])
        self.assertTrue(later['review_required'])
        row=dict(tour='WTA',players=['33355','2'])
        self.assertTrue(I.fixture_blocked(row,later))
        clear=I.publish_quarantine(self.root,self.status(),[],[],'2026-11-07',now+timedelta(days=3))
        self.assertFalse(I.fixture_blocked(row,clear))

    def test_current_views_drop_held_fixtures_without_touching_historical_records(self):
        receipt=self.receipt();folder=self.root/'data/tennis-props/shadow';folder.mkdir(parents=True)
        bad=dict(tour='WTA',player1='Jodie Anna Burrage',player2='Player Two')
        good=dict(tour='ATP',player1='Player Three',player2='Player Four')
        for name in ('most-aces-1x2-board.csv','most-aces-direct-1x2-board.csv'):
            write(folder/name,[bad,good])
        historical=folder/'most-aces-1x2-observations.csv';historical.write_text('historical unchanged\n')
        current=folder/'most-aces-current.json';current.write_text(json.dumps(dict(matches=[bad,good],records=[{'losses':22}],generated_at='old')))
        removed=I.remove_held_current_rows(self.root,receipt)
        self.assertEqual(len(removed),3)
        for name in ('most-aces-1x2-board.csv','most-aces-direct-1x2-board.csv'):
            self.assertEqual(I.read(folder/name),[good])
        saved=json.loads(current.read_text());self.assertEqual(saved['matches'],[good]);self.assertEqual(saved['records'],[{'losses':22}]);self.assertEqual(saved['generated_at'],'old')
        self.assertEqual(historical.read_text(),'historical unchanged\n')

    def test_stale_count_direct_and_df_candidates_cannot_reach_digest(self):
        self.receipt();folder=self.root/'data/tennis-props/shadow';folder.mkdir(parents=True)
        (folder/'most-aces-current.json').write_text('{}')
        spec=importlib.util.spec_from_file_location('isolation_digest',SCRIPTS/'tennis-daily-signal-digest.py')
        digest=importlib.util.module_from_spec(spec);sys.modules[spec.name]=digest;spec.loader.exec_module(digest)
        import tennis_most_aces_current as current
        import tennis_most_df_delivery as df
        # Exercise the final operational guard even if an upstream caller hands
        # it stale eligible rows from either model.
        rows=[dict(tour='WTA',player1='Jodie Anna Burrage',player2='Player Two',model=m) for m in ('count','direct')]
        with patch.object(digest,'ROOT',self.root),patch.object(digest,'PROPS',self.root/'data/tennis-props'),patch.object(current,'alert_rows',return_value=rows),patch.object(df,'alert_rows',return_value=[dict(tour='WTA',players=['33355','2'],names=['Jodie Anna Burrage','Player Two'])]):
            self.assertEqual(digest.most_aces_signals('2026-11-04'),[])
            self.assertEqual(digest.most_df_signals('2026-11-04'),[])

if __name__=='__main__':unittest.main()
