import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ops_tennis_recovery import discover_props_recovery, verified_props_recovery
from ops_morning_failures import check_morning_failure


def entry(text):
    return {'content':text, 'size_bytes':len(text.encode()), 'sha256':hashlib.sha256(text.encode()).hexdigest()}


class PropsRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.row = {'run_id':'failed-run', 'status':'failed', 'error_type':'TennisPropsRefreshFailed',
                    'started_at':'2026-11-04T10:05:00Z', 'finished_at':'2026-11-04T10:38:00Z', 'details':{}}
        self.health = {'generated_at':'2026-11-04T12:22:00Z', 'as_of':'2026-11-04',
            'state':'HEALTHY_NO_QUALIFYING_EDGE', 'structural_error':False,
            'player_history':{'state':'CURRENT','as_of':'2026-11-04','version':'v3','output_hashes':{'player-props-baseline.csv':'a'*64}},
            'baseline_source_health':{'state':'CURRENT'}, 'fixture_quarantine':{'held_fixtures':[]},
            'fresh_upcoming_line_rows':1,'upcoming_line_rows':1,'uncompared_upcoming_rows':0,
            'unmatched_rows':0,'matched_rows':1,'comparison_rows':1,'eligible_line_rows':1,'line_rows':1,
            'freshness_problems':{},'latest_capture_utc':'2026-11-04T10:21:00Z','max_capture_age_hours':6,
            'lines_file':'D:/runtime/data/tennis-props/inbox/bet365-lines-2026-11-04.csv',
            'comparison_file':'D:/runtime/data/tennis-props/comparison-2026-11-04.csv'}
        self.snapshot = {'source':'windows_local_tennis_pipeline','schema':3,'payload_hash':'b'*64,
                         'generated_at':'2026-11-04T13:04:00Z','updated_at':'2026-11-04T13:04:00Z',
                         'bundle':{'status':'AVAILABLE','missing_required_files':[]}}
        columns='event_id,player,opponent,market,line,capture_ts,bookmaker'
        values='123,A,B,aces,5.5,2026-11-04T10:21:00Z,Example'
        self.files={'payload_hash':'b'*64,'lines':entry(columns+'\n'+values+'\n'),
          'comparison':entry(columns+',matched_board,history_as_of,history_version,history_fingerprint\n'+values+',yes,2026-11-04,v3,'+'a'*64+'\n')}
        self.env={'NEXT_PUBLIC_SUPABASE_URL':'https://db.example','SUPABASE_SERVICE_ROLE_KEY':'fake'}

    def responses(self):
        return [[{**self.snapshot,'health_file':entry(json.dumps(self.health))}],[self.files]]

    def recover(self):
        return discover_props_recovery(self.row,'https://db.example',{},Mock(side_effect=self.responses()))

    def test_later_verified_recovery_and_readonly_never_write_or_send(self):
        proof=self.recover();self.assertTrue(verified_props_recovery(self.row,{'ops_failure_resolution':proof}))
        transport=Mock(side_effect=[[self.row]]+self.responses())
        self.assertFalse(check_morning_failure(self.env,transport,read_only=True))
        self.assertEqual([c.args[0] for c in transport.call_args_list],['GET']*3)

    def test_records_only_recovery_details_with_cas_retaining_failure_and_ack(self):
        self.row['details']={'ops_failure_notified_at':'2026-11-04T17:59:00Z','existing':'kept'}
        transport=Mock(side_effect=[[self.row]]+self.responses()+[[self.row]])
        self.assertFalse(check_morning_failure(self.env,transport))
        call=transport.call_args_list[-1];self.assertEqual(call.args[0],'PATCH')
        self.assertIn('details=eq.',call.args[1]);payload=call.args[3]
        self.assertEqual(set(payload),{'details'});self.assertEqual(payload['details']['existing'],'kept')
        self.assertEqual(payload['details']['ops_failure_notified_at'],self.row['details']['ops_failure_notified_at'])
        self.assertTrue(all('telegram' not in c.args[1] for c in transport.call_args_list))

    def test_persisted_receipt_avoids_repeated_snapshot_reads(self):
        self.row['details']={'ops_failure_resolution':self.recover()}
        t=Mock(return_value=[self.row]);self.assertFalse(check_morning_failure(self.env,t));self.assertEqual(t.call_count,1)

    def test_failed_cas_does_not_send_or_overwrite(self):
        t=Mock(side_effect=[[self.row]]+self.responses()+[[]])
        with self.assertRaises(RuntimeError):check_morning_failure(self.env,t)
        self.assertEqual(t.call_args_list[-1].args[0],'PATCH')

    def test_old_future_or_naive_health_cannot_clear(self):
        for date in ['2026-11-04T10:00:00Z','2099-11-04T12:00:00Z','2026-11-04T12:22:00']:
            with self.subTest(date=date):
                self.health['generated_at']=date;self.assertIsNone(self.recover())

    def test_unhealthy_incomplete_or_stale_inputs_cannot_clear(self):
        baseline=copy.deepcopy(self.health)
        for change in [{'state':'CORE_RUN_FAILED'},{'structural_error':True},{'unmatched_rows':1},
                       {'fresh_upcoming_line_rows':0},{'uncompared_upcoming_rows':1},
                       {'freshness_problems':{'old':1}},{'latest_capture_utc':'2026-11-03T10:00:00Z'},
                       {'player_history':{**baseline['player_history'],'state':'BLOCKED'}},
                       {'fixture_quarantine':{'held_fixtures':['x']}}]:
            with self.subTest(change=change):
                self.health={**copy.deepcopy(baseline),**change};self.assertIsNone(self.recover())

    def test_bad_source_bundle_or_hash_cannot_clear(self):
        baseline=copy.deepcopy(self.snapshot)
        for change in [{'source':'unknown'},{'schema':2},{'payload_hash':'wrong'},
                       {'bundle':{'status':'REQUIRED_INPUTS_MISSING','missing_required_files':['x']}}]:
            self.snapshot={**baseline,**change};self.assertIsNone(self.recover())
        self.snapshot=baseline;self.files['lines']['sha256']='0'*64;self.assertIsNone(self.recover())

    def test_concurrent_snapshot_or_wrong_history_or_missing_rows_cannot_clear(self):
        baseline=copy.deepcopy(self.files)
        for kind in ['changed_snapshot','wrong_history','missing_rows','wrong_fixture']:
            self.files=copy.deepcopy(baseline)
            if kind=='changed_snapshot':self.files['payload_hash']='c'*64
            else:
                txt=self.files['comparison']['content']
                txt=txt.replace(',v3,',',v2,') if kind=='wrong_history' else txt.splitlines()[0]+'\n' if kind=='missing_rows' else txt.replace('123,','999,')
                self.files['comparison']=entry(txt)
            self.assertIsNone(self.recover())

    def test_unrelated_or_newer_failure_never_uses_old_receipt(self):
        proof=self.recover()
        for change in [{'error_type':'ReturnAtlasRefreshFailed'},{'run_id':'new-run'},
                       {'finished_at':'2026-11-04T14:00:00Z'}]:
            self.assertFalse(verified_props_recovery({**self.row,**change},{'ops_failure_resolution':proof}))

    def test_empty_snapshot_and_transport_failure_are_not_recovery(self):
        self.assertIsNone(discover_props_recovery(self.row,'https://db.example',{},Mock(return_value=[])))
        with self.assertRaises(RuntimeError):discover_props_recovery(self.row,'https://db.example',{},Mock(side_effect=RuntimeError('offline')))


if __name__=='__main__':unittest.main()
