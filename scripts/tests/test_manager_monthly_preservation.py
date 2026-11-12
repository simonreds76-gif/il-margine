"""Exercise a real offline weekly append without changing the public archive."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

ROOT=Path(__file__).parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
import manager_atlas_weekly as weekly
spec=importlib.util.spec_from_file_location('monthly_refresh',ROOT/'scripts/refresh-manager-atlas.py')
collector=importlib.util.module_from_spec(spec);spec.loader.exec_module(collector)
pack=weekly.package

def read(path):return json.loads(path.read_text(encoding='utf-8'))
def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')

class MonthlyPreservationTests(unittest.TestCase):
    def fixture_tree(self,root):
        manifest=read(ROOT/'src/data/manager-atlas-release.json')
        data=read(ROOT/'public'/manifest['indexUrl'].lstrip('/'))
        write(root/'src/data/manager-atlas-release.json',manifest)
        write(root/'public'/manifest['indexUrl'].lstrip('/'),data)
        for name in ['manager-atlas-identities.json','manager-fotmob-identities.json','manager-fixture-reviews.json']:
            write(root/'scripts/config'/name,read(ROOT/'scripts/config'/name))
        for name in ['config/manager-atlas-activity.json','public/manager-atlas/activity.json']:
            write(root/name,read(ROOT/name))
        write(root/'src/data/football-atlas-release.json',{'indexUrl':'/football-test.json','version':'offline-test'})
        # No invented betting price: this test-only result is deliberately unpriced.
        write(root/'public/football-test.json',{'teams':['Villarreal','Espanyol'],'leagues':['la-liga'],
            'seasons':['2026-2027'],'fixtures':[['test-only-new-atlas-id','2026-10-30',0,0,0,1,0,1,None,None,None,None]]})
        state=root/'state/managers'
        write(state/'dates-v2/2026-10-30.json',{'schemaVersion':2,'date':'2026-10-30','leagues':[{'league':'la-liga','matches':[{'id':5868120,
            'home':{'name':'Villarreal'},'away':{'name':'Espanyol'},'status':{'finished':True}}]}]})
        review=read(ROOT/'scripts/config/manager-fixture-reviews.json')['fotmob:5868120']
        raw={**review,'coaches':review['observedCoaches']}
        write(state/'matches/5868120.json',raw)
        return data

    def run_offline(self,root):
        def execute(command,**kwargs):
            with patch.object(collector,'ROOT',root),patch.object(sys,'argv',command[1:]):
                try:collector.main()
                except SystemExit as exc:
                    if exc.code:raise subprocess.CalledProcessError(exc.code,command)
        package=SimpleNamespace(unpack=pack.unpack,package=lambda data:pack.package(data,root))
        with patch.object(weekly,'ROOT',root),patch.object(weekly,'package',package),patch.object(weekly.subprocess,'run',side_effect=execute):
            return weekly.refresh(root/'state',offline=True)

    def test_exact_standin_review_survives_next_and_repeated_weekly_refresh(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);before=self.fixture_tree(root)
            status_paths=[root/'config/manager-atlas-activity.json',root/'public/manager-atlas/activity.json']
            statuses=[p.read_bytes() for p in status_paths]
            result=self.run_offline(root)
            self.assertEqual(result['added'],1);self.assertEqual(result['pending'],[])
            current=read(root/'public'/result['manifest']['indexUrl'].lstrip('/'))
            rows={r[0]:r for r in current['rows']}
            self.assertTrue(all(rows[row[0]]==row for row in before['rows']))
            added=rows['test-only-new-atlas-id']
            self.assertEqual(added[10:12],['mgr-0271','mgr-0168'])
            self.assertIsNone(added[8]);self.assertIsNone(added[9])
            self.assertEqual([p.read_bytes() for p in status_paths],statuses)
            again=self.run_offline(root)
            self.assertEqual(again['added'],0);self.assertFalse(again['changed'])
            self.assertEqual([p.read_bytes() for p in status_paths],statuses)

    def test_conflicting_exact_match_score_is_held_without_changing_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);self.fixture_tree(root)
            path=root/'scripts/config/manager-fixture-reviews.json';reviews=read(path)
            reviews['fotmob:5868120']['ag']=2;write(path,reviews)
            before=(root/'src/data/manager-atlas-release.json').read_bytes()
            result=self.run_offline(root)
            self.assertFalse(result['changed']);self.assertEqual(result['added'],0)
            self.assertEqual((root/'src/data/manager-atlas-release.json').read_bytes(),before)
            report=read(root/'state/managers/refresh-report.json')
            self.assertEqual(report['failures'],[]);self.assertEqual(report['added'],0)
            self.assertEqual(report['pending'][0]['code'],'fixture_conflict')

    def test_stale_public_activity_blocks_before_history_writer(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);self.fixture_tree(root)
            path=root/'public/manager-atlas/activity.json';old=read(path)
            old['entries']['mgr-0239']['status']='active';write(path,old)
            with self.assertRaisesRegex(ValueError,'activity source/public copy mismatch'):
                self.run_offline(root)
            self.assertFalse((root/'state/managers/candidate.json').exists())

if __name__=='__main__':unittest.main()
