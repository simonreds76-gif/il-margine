import copy
from datetime import datetime, timezone, timedelta
import importlib.util
import json
from pathlib import Path
import runpy
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
import tennis_full_refresh_reporting as M


class ReportingTests(unittest.TestCase):
    def row(self, identifier, line=2.5, side='OVER', both=False):
        pred={'OVER': {'mean':4}}
        if both:pred['UNDER']={'mean':4}
        return dict(id=identifier,fixture_key='fixture',row=dict(market='aces',tour='ATP',line=str(line),over_odds='2.5',under_odds='1.8'),control=pred,candidate=pred,control_side=side,candidate_side=None)

    def test_over_milestones_roi_and_pending(self):
        rows=[self.row(str(i)) for i in range(4)]
        outcomes={'0':dict(status='settled',actual=3),'1':dict(status='settled',actual=2),'2':dict(status='void')}
        g=M.breakdown(rows,outcomes)[0]
        self.assertEqual(g['label'],'3+')
        self.assertEqual(g['fixtures'],1)
        self.assertEqual(g['control']['stake_units'],2)
        self.assertEqual(g['control']['pnl_units'],.5)
        self.assertEqual(g['control']['roi_pct'],25)
        self.assertEqual((g['control']['wins'],g['control']['losses'],g['control']['pending'],g['control']['void']),(1,1,1,1))
        self.assertIsNone(g['candidate']['roi_pct'])

    def test_only_real_offered_sides_and_thresholds(self):
        groups=M.breakdown([self.row('a'),self.row('b',4.5)],{})
        self.assertEqual({g['label'] for g in groups},{'3+','5+'})
        self.assertEqual({g['side'] for g in groups},{'OVER'})

    def test_under_and_integer_push_stay_separate(self):
        g=M.breakdown([self.row('a',4,'UNDER',True)],{'a':dict(status='settled',actual=4)})
        under=next(x for x in g if x['side']=='UNDER')
        self.assertEqual(under['label'],'Under 4')
        self.assertEqual(under['control']['pushes'],1)
        self.assertEqual(under['control']['roi_pct'],0)
        self.assertEqual(next(x for x in g if x['side']=='OVER')['control']['selected'],0)

    def test_atp_wta_and_markets_not_pooled(self):
        a=self.row('a');b=copy.deepcopy(a);b['row']['tour']='WTA';c=copy.deepcopy(a);c['row']['market']='double_faults'
        self.assertEqual(len(M.breakdown([a,b,c],{})),3)

    def test_corrupt_ledger_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            (p/'report.json').write_text('{}')
            (p/'observations.jsonl').write_text(json.dumps(dict(hash='bad',previous_hash='')))
            with self.assertRaisesRegex(ValueError,'integrity'):M.build(p)

    def test_missing_or_outdated_report_is_not_zero_performance(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);folder=root/M.RELATIVE;folder.mkdir(parents=True)
            self.assertEqual(M.load_summary(root)['status'],'SOURCE_MISSING')
            (folder/'milestones.json').write_text(json.dumps(dict(generated_at='old',markets={'aces':{}},milestones=[])))
            (folder/'report.json').write_text(json.dumps(dict(generated_at='new')))
            self.assertEqual(M.load_summary(root)['status'],'REPORT_OUTDATED')

    def test_all_weekly_formats_include_new_lane_and_split_safely(self):
        report=runpy.run_path(str(ROOT/'scripts/weekly-research-report.py'))
        payload=json.loads((ROOT/'data/football-form/weekly-research-report.json').read_text(encoding='utf-8'))
        payload['tennis_full_refresh']=dict(generated_at=(datetime.now(timezone.utc)-timedelta(days=4)).isoformat(),markets={'aces':dict(control={},candidate={})},milestones=[])
        for name in ('render_report','telegram_text','tennis_telegram_text'):
            text=report[name](payload)
            self.assertIn('Full input refresh | paper tracking only',text)
            self.assertIn('STALE: source evidence',text)
        chunks=report['telegram_chunks'](report['tennis_telegram_text'](payload))
        self.assertTrue(all(len(c)<=3900 for c in chunks))

    def test_snapshot_and_daily_hooks_present(self):
        snapshot=(ROOT/'scripts/tennis-evidence-snapshot.py').read_text(encoding='utf-8')
        self.assertIn('"tennis_full_refresh": module.full_refresh_summary()',snapshot)
        registry=json.loads((ROOT/'config/model-review-watchlist.json').read_text(encoding='utf-8'))
        self.assertEqual(sum(f['report_key']=='tennis_full_refresh' for f in registry['families']),1)


if __name__=='__main__':unittest.main()
