import copy
from datetime import datetime, timedelta, timezone
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location('keeper_alerts', Path(__file__).resolve().parents[1] / 'goalkeeper-saves-alerts.py')
alerts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(alerts)


class KeeperWatchAlerts(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.path = self.folder / 'report.json'
        self.row = dict(model='keeper_watch', match_id='42', player_id='9', team_id='3',
            captured_at=self.now.isoformat(), registered_at=self.now.isoformat(),
            kickoff_at=(self.now+timedelta(hours=2)).isoformat(), home='A & B', away='C',
            goalkeeper='Test Keeper', bookmaker='Bet365', side='over', line=3.5,
            odds=2.2, fair_odds=2, edge=.1, status='pending', lineup_status='predicted_starter')
        self.report = dict(status='TRACKING', generated_at=self.now.isoformat(),
            start_at=(self.now-timedelta(days=1)).isoformat(), actual_stake=0,
            paper_stake=.5, auto_promote=False, selections=[self.row])

    def rows(self):
        self.path.write_text(json.dumps({'keeper_watch':self.report}), encoding='utf-8')
        return alerts.keeper_watch_rows(self.path, self.now)

    def test_only_candidate_and_independent_claims_with_frozen_prices(self):
        self.report['selections'].append({**self.row, 'model':'current'})
        rows=self.rows()
        self.assertEqual(len(rows),1)
        state={'signals':{'42':{'status':'sent'}}}
        self.assertEqual(alerts.claim(rows,state,'run:1',self.now),1)
        rows[0]['odds_decimal']=1.9
        self.assertEqual(alerts.claim(rows,state,'run:2',self.now),0)
        self.assertEqual(state['signals']['keeper_watch_v1:42']['signal']['odds_decimal'],2.2)

    def test_blocked_stale_and_nonpaper_reports_are_suppressed(self):
        original=copy.deepcopy(self.report)
        for change in ({'status':'BLOCKED'},{'actual_stake':.5},{'auto_promote':True},
                       {'generated_at':(self.now-timedelta(hours=7)).isoformat()}):
            self.report={**original,**change}
            self.assertEqual(self.rows(),[],change)

    def test_old_replay_and_missing_identity_are_not_loaded(self):
        for change in ({'captured_at':(self.now-timedelta(days=2)).isoformat()}, {'player_id':None}):
            self.report['selections']=[{**self.row,**change}]
            self.assertEqual(self.rows(),[])

    def test_expired_settled_bad_prices_and_nonstarters_are_not_alerted(self):
        row=self.rows()[0]
        for change in ({'status':'won'}, {'kickoff_at':self.now.isoformat()},
                       {'created_at':(self.now-timedelta(hours=7)).isoformat()},
                       {'captured_at':(self.now-timedelta(hours=7)).isoformat()},
                       {'odds_decimal':float('nan')}, {'fair_odds':float('inf')},
                       {'bookmaker':'Other'}, {'lineup_status':'bench'}, {'edge':.01}):
            self.assertFalse(alerts.eligible({**row,**change},self.now),change)

    def test_message_is_separate_paper_and_links_to_candidate_record(self):
        text=alerts.message(self.rows()[0])
        for expected in ('Keeper Watch v1 | PAPER selection','Real stake: 0u',
                         '0.5u paper','A &amp; B','#keeper-watch','2.20','+10.0%'):
            self.assertIn(expected,text)
        self.assertNotIn('GK saves | New tracked signal',text)

    def delivery(self, timeout=False):
        self.rows()
        ledger=self.folder/'signals.csv'
        ledger.write_text('signal_id,status\n',encoding='utf-8')
        state=self.folder/'state.json'
        env={'OPS_ALERT_TELEGRAM_BOT_TOKEN':'fake','OPS_ALERT_TELEGRAM_CHAT_ID':'fake',
             'GITHUB_RUN_ID':'test','GITHUB_RUN_ATTEMPT':'1'}
        args=['alerts','--state',str(state),'--ledger',str(ledger),'--report',str(self.path)]
        response=Mock(ok=True,status_code=200)
        response.json.return_value={'ok':True,'result':{'message_id':77}}
        with patch.dict(os.environ,env), patch('builtins.print'), patch.object(alerts.requests,'post',return_value=response) as post:
            with patch.object(sys,'argv',args+['--prepare']):
                alerts.main()
            self.assertEqual(post.call_count,0)
            self.assertEqual(json.loads(state.read_text())['signals']['keeper_watch_v1:42']['status'],'claimed')
            if timeout: post.side_effect=alerts.requests.exceptions.ReadTimeout()
            with patch.object(sys,'argv',args+['--send']):
                if timeout:
                    with self.assertRaises(SystemExit): alerts.main()
                else: alerts.main()
                alerts.main()
            self.assertEqual(post.call_count,1)
            self.assertIn('Keeper Watch v1 | PAPER',post.call_args.kwargs['json']['text'])
        return json.loads(state.read_text())['signals']['keeper_watch_v1:42']

    def test_existing_prepare_send_protocol_records_delivery_once(self):
        self.assertEqual(self.delivery()['status'],'sent')

    def test_candidate_timeout_is_not_retried(self):
        self.assertEqual(self.delivery(timeout=True)['status'],'delivery_unconfirmed')


if __name__ == '__main__':
    unittest.main()
