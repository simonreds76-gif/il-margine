from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

SCRIPTS=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(SCRIPTS))
import tennis_props_daily_summary as S


class DailyPaperSummaryTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root=Path(self.directory.name)
        self.today=datetime.now(ZoneInfo('Europe/London')).date().isoformat()
        self.write('data/tennis-props/player-history-status.json',dict(state='CURRENT',version=S.VERSION,as_of=self.today))
        self.write('data/tennis-props/pipeline-health.json',dict(as_of=self.today,state='MILESTONE_SHADOW_READY',structural_error=False))
        model=self.root/'model.json';model.write_text('fixed model')
        self.sha=hashlib.sha256(model.read_bytes()).hexdigest()
        self.write('data/tennis-props/backtest/aces-dfs-v3-all-tour-gate.json',dict(deployment_safe_aces={'ATP':{'model_path':'model.json'}}))

    def write(self,rel,payload):
        path=self.root/rel;path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(payload),encoding='utf-8')

    def rows(self,rows):
        path=self.root/S.LEDGER;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('w',newline='',encoding='utf-8') as handle:
            writer=csv.DictWriter(handle,fieldnames=list(dict.fromkeys(k for row in rows for k in row)))
            writer.writeheader();writer.writerows(rows)
        self.write(S.REPORT,dict(generated_at=datetime.now(timezone.utc).isoformat(),rows_registered=len(rows),
                                rows_settled=sum(r.get('settlement_status')=='settled' for r in rows),minimum_prefit_settled=200))

    def row(self,key,**extras):
        return dict(observation_id=key,history_version=S.VERSION,model_sha256=self.sha,date='2026-01-01',
                    event_id=key,player='One',opponent='Two',settlement_status='settled',actual='4',mu_v3='3',mu_mkt='3',
                    phase='PRE_FIT',v4_signal='false',pnl='',result='',**extras)

    def test_old_evidence_does_not_fill_current_training_progress(self):
        old=self.row('old');old['history_version']=''
        self.rows([old])
        text,state=S.build(self.root,self.today,{})
        self.assertIn('0 forecasts | 0 settled',text)
        self.assertIn('eligible this month: 0/200',text)
        self.assertIn('EARLIER INPUTS: 1 forecasts | 1 settled',text)
        self.assertIsNone(state['current_metrics']['roi'])

    def test_paper_roi_excludes_old_prefit_and_void_records(self):
        rows=[]
        for key,result,pnl in [('win','win','1.5'),('loss','loss','-1'),('push','push','0')]:
            row=self.row(key);row.update(phase='WALK_FORWARD',v4_signal='true',result=result,pnl=pnl);rows.append(row)
        warmup=self.row('warmup');warmup.update(result='win',pnl='100');rows.append(warmup)
        old=self.row('old');old.update(history_version='',phase='WALK_FORWARD',v4_signal='true',result='win',pnl='100');rows.append(old)
        void=self.row('void');void.update(phase='WALK_FORWARD',v4_signal='true',settlement_status='void',pnl='0');rows.append(void)
        self.rows(rows)
        text,state=S.build(self.root,self.today,{'date':'previous','settled_ids':['win']})
        metrics=state['current_metrics']
        self.assertEqual((metrics['wins'],metrics['losses'],metrics['pushes'],metrics['paper_settled']),(1,1,1,3))
        self.assertAlmostEqual(metrics['roi'],100*.5/3)
        self.assertIn('Profit +0.50u',text)
        self.assertEqual(metrics['newly_settled'],3)

    def test_once_daily_dedup_even_if_report_changes(self):
        self.rows([self.row('one')]);sender=Mock()
        self.assertEqual(S.daily_summary(self.root,self.today,sender),'dispatched')
        self.rows([self.row('one'),self.row('two')])
        self.assertEqual(S.daily_summary(self.root,self.today,sender),'already_dispatched')
        sender.assert_called_once()

    def test_failed_dispatch_is_retryable_and_preview_does_not_send(self):
        self.rows([self.row('one')])
        sender=Mock(side_effect=RuntimeError('relay failed'))
        with self.assertRaises(RuntimeError):S.daily_summary(self.root,self.today,sender)
        self.assertFalse((self.root/S.STATE).exists())
        S.daily_summary(self.root,self.today,sender,print_only=True)
        self.assertEqual(sender.call_count,1)
        self.assertFalse((self.root/S.STATE).exists())

    def test_stale_report_reports_health_problem_not_fresh_success(self):
        self.rows([self.row('one')])
        self.write(S.REPORT,dict(generated_at='2025-01-01T00:00:00Z',rows_registered=1,rows_settled=1))
        text,state=S.build(self.root,self.today,{})
        self.assertIn('DATA CHECK:',text)
        self.assertIn('not refreshed today',text)
        self.assertTrue(state['health_warnings'])
        self.assertLess(len(text),3800)

    def test_training_excludes_current_month_and_other_model(self):
        old_model=self.row('oldmodel');old_model['model_sha256']='different'
        today=self.row('today');today['date']=self.today
        self.rows([self.row('eligible'),old_model,today])
        text,_=S.build(self.root,self.today,{})
        self.assertIn('eligible this month: 1/200',text)

    def test_milestone_only_on_first_crossing(self):
        self.rows([self.row(str(i)) for i in range(50)])
        first,state=S.build(self.root,self.today,{})
        self.assertIn('REVIEW MILESTONE: 50',first)
        again,_=S.build(self.root,self.today,state)
        self.assertNotIn('REVIEW MILESTONE:',again)

    def test_hook_runs_even_when_no_betting_signals_ready(self):
        spec=importlib.util.spec_from_file_location('digest_paper_hook',SCRIPTS/'tennis-daily-signal-digest.py')
        module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
        with patch.object(sys,'argv',['digest','--paper-summary','--require-ready']), \
             patch.object(module,'signal_generation_is_ready',return_value=False), \
             patch.object(S,'daily_summary',return_value='dispatched') as summary, \
             patch.object(module,'collect_signals',side_effect=AssertionError('No selection replay')):
            self.assertEqual(module.main(),0)
            summary.assert_called_once()

    def test_existing_post_settlement_step_enables_summary(self):
        source=(SCRIPTS/'oncourt-am-refresh.ps1').read_text(encoding='utf-8')
        self.assertEqual(source.count('"--new-only", "--paper-summary", "--paper-signals"'),1)

    def test_summary_failure_does_not_block_existing_digest(self):
        spec=importlib.util.spec_from_file_location('digest_paper_failure',SCRIPTS/'tennis-daily-signal-digest.py')
        module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
        with patch.object(sys,'argv',['digest','--paper-summary','--require-ready']), \
             patch.object(module,'signal_generation_is_ready',return_value=False), \
             patch.object(S,'daily_summary',side_effect=RuntimeError('relay unavailable')):
            self.assertEqual(module.main(),0)


if __name__=='__main__':unittest.main()
