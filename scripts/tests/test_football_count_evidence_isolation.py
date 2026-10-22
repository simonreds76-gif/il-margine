import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
spec=importlib.util.spec_from_file_location('evidence_test',ROOT/'scripts/refresh-football-count-evidence.py')
E=importlib.util.module_from_spec(spec);spec.loader.exec_module(E)

class EvidenceIsolation(unittest.TestCase):
    def row(self,version,key):
        return dict(version=version,contract_id=key,match_date='2026-09-30',league='epl',
            home_team='Arsenal',away_team='Chelsea',team='Arsenal',line=10.5,
            kickoff_utc='2026-09-30T14:00:00Z',odds={'over':2,'under':2},
            models={m:{'p_over':.6,'mean':12,'selected_side':'over'} for m in E.P.MODELS})

    def test_unknown_change_blocks_capture_but_settles_and_preserves_all_cohorts(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);form=root/'data/football-form';form.mkdir(parents=True)
            old=self.row('paired-market-offset-20260930-v2','old')
            new=self.row(E.P.VERSION,'new');new['home_team']='Liverpool';new['team']='Liverpool'
            ledger=form/'team-shots-paired-reference.jsonl'
            ledger.write_text('\n'.join(json.dumps(r) for r in [old,new])+'\n')
            before=ledger.read_bytes()
            base=[dict(date=r['match_date'],league=r['league'],home_team=r['home_team'],away_team=r['away_team'],team=r['team'],shots_for=12) for r in [old,new]]
            with patch.object(E,'ROOT',root),patch.object(E.P,'main',side_effect=E.P.ModelFingerprintMismatch('changed')),patch.object(E.P.PUB,'load_csv',return_value=base),patch.object(sys,'argv',['evidence']):
                E.main()
            result=json.loads((form/'team-shots-paired-reference-status.json').read_text())
            self.assertEqual(result['capture_status'],'BLOCKED_MODEL_CHANGE')
            self.assertEqual(result['settled_contracts'],2)
            self.assertEqual(set(result['cohorts']),{old['version'],new['version']})
            self.assertEqual(ledger.read_bytes(),before)

    def test_other_failures_remain_visible(self):
        with patch.object(E.P,'main',side_effect=RuntimeError('bad input')),patch.object(sys,'argv',['evidence']):
            with self.assertRaises(RuntimeError):E.main()

    def test_registered_fingerprint_is_exact_and_empty_cohort_is_protected(self):
        fingerprint=E.P.model_fingerprint()
        E.P.check_registration(fingerprint)
        with self.assertRaises(E.P.ModelFingerprintMismatch):E.P.check_registration('changed')

    def test_alias_change_cannot_select_again_for_an_old_fixture(self):
        old=self.row('paired-market-offset-20260930-v2','old')
        old.update(home_team='AJ Auxerre',team='AJ Auxerre')
        new=copy.deepcopy(old);new.update(version=E.P.VERSION,home_team='Auxerre',team='Auxerre',contract_id='new')
        for model in new['models'].values():model['minimum_edge']=.01
        E.P.select_first_scan([new],[old])
        self.assertTrue(all(m['selected_side'] is None for m in new['models'].values()))

if __name__=='__main__':unittest.main()
