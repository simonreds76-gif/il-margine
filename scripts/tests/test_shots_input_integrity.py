import copy,csv,importlib.util,json,sys,tempfile,unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
import football_shots_inputs as I
import football_shots_completed as E
import team_shots_ema20_features as OLD
import team_shots_strength_paper as S
NOW=datetime(2026,11,13,13,tzinfo=timezone.utc)
def module(name,file):
    sp=importlib.util.spec_from_file_location(name,ROOT/'scripts'/file);m=importlib.util.module_from_spec(sp);sys.modules[name]=m;sp.loader.exec_module(m);return m
B=module('integrity_builder','build-football-form-layer.py')
P=module('integrity_paired','team-shots-paired-reference.py')

def fixture():
    common=dict(date='2026-10-29',league='serie-a',home_team='Fiorentina',away_team='Atalanta',xg_for='1.2',xg_against='1.5')
    return [dict(common,team='Fiorentina',opponent='Atalanta',venue='home',shots_for='14',shots_against='2',sot_for='4'),dict(common,team='Atalanta',opponent='Fiorentina',venue='away',shots_for='2',shots_against='14',sot_for='5')]

class Integrity(unittest.TestCase):
    def test_exact_correction_does_not_mutate_original(self):
        rows=fixture();before=copy.deepcopy(rows);cfg=json.loads((ROOT/I.CONFIG).read_text())
        out,health=I.prepare(rows,cfg,NOW)
        self.assertEqual(rows,before);self.assertEqual([r['shots_for'] for r in out],['26','10'])
        twice,_=I.prepare(out,cfg,NOW);self.assertEqual(twice,out)
        self.assertEqual(len(health['applied_corrections']),1)

    def test_conflicting_revision_quarantines_whole_fixture(self):
        rows=fixture();rows[0]['shots_for']='99';cfg=json.loads((ROOT/I.CONFIG).read_text())
        out,h=I.prepare(rows,cfg,NOW);self.assertEqual(out,[]);self.assertEqual(h['quarantined_fixtures'][0]['reason'],'correction_source_conflict')

    def test_other_identity_not_corrected(self):
        rows=fixture()
        for r in rows:r['date']='2026-10-28'
        out,h=I.prepare(rows,json.loads((ROOT/I.CONFIG).read_text()),NOW)
        self.assertEqual(h['applied_corrections'],[]);self.assertEqual(out,[])

    def test_missing_xg_denominator_and_true_zero(self):
        rows=[dict(xg_for='1',shots_for='10',xg_against='0',shots_against='8'),dict(xg_for='',shots_for='30',xg_against='',shots_against='20')]
        f=I.quality_fields(rows)
        self.assertEqual(f['r10_xg_per_shot_for'],'0.1');self.assertEqual(f['r10_xg_per_shot_against'],'0')
        self.assertEqual(f['r10_xg_shots_paired_for'],1)
        self.assertEqual(I.quality_fields([rows[1]])['r10_xg_per_shot_for'],'')

    def test_fully_observed_summaries_have_exact_parity(self):
        rows=[dict(xg_for=str(i*.2),xg_against=str(i*.1),shots_for=str(i+3),shots_against=str(i+4)) for i in range(1,26)]
        f=I.quality_fields(rows)
        legacy={**OLD.summarize_window(rows,10),**OLD.summarize_ema_window(rows)}
        for k,v in f.items():
            if k in legacy:self.assertEqual(v,legacy[k],k)

    def test_missing_count_is_not_zero(self):
        self.assertIsNone(B.optional_count(''));self.assertIsNone(B.optional_count(None))
        self.assertIsNone(B.optional_count('NaN'));self.assertEqual(B.optional_count('0'),0)
        rows=fixture();rows[1]['shots_for']=''
        out,_=I.prepare(rows,{},NOW);self.assertEqual(out,[])

    def test_break_is_fresh_but_missing_completed_match_blocks_its_league(self):
        check=dict(observed_at=NOW.isoformat(),leagues={k:dict(status='VERIFIED',completed=[]) for k in I.LEAGUES})
        self.assertEqual(I.freshness([],check,NOW)['blocked_leagues'],{})
        check['leagues']['serie-a']['completed']=[fixture()[0]]
        self.assertEqual(set(I.freshness([],check,NOW)['blocked_leagues']),{'serie-a'})
        self.assertEqual(I.freshness(fixture(),check,NOW)['blocked_leagues'],{})

    def test_stale_or_failed_discovery_cannot_claim_healthy(self):
        check=dict(observed_at=(NOW-timedelta(days=2)).isoformat(),leagues={k:dict(status='VERIFIED',completed=[]) for k in I.LEAGUES})
        self.assertEqual(len(I.freshness([],check,NOW)['blocked_leagues']),5)
        check['observed_at']=NOW.isoformat();check['leagues']['epl']['status']='UNVERIFIED'
        self.assertEqual(set(I.freshness([],check,NOW)['blocked_leagues']),{'epl'})

    def test_missing_fixture_is_not_filtered_out_by_latest_date(self):
        check=dict(observed_at=NOW.isoformat(),leagues={k:dict(status='VERIFIED',completed=[]) for k in I.LEAGUES})
        check['leagues']['serie-a']['completed']=[fixture()[0]]
        newer=[dict(r,date='2026-11-08') for r in fixture()]
        self.assertEqual(len(I.freshness(newer,check,NOW)['missing_completed']),1)

    def test_hash_binds_read_bytes_not_later_file(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'a.csv';p.write_bytes(b'a,b\n1,2\n');rows,h=I.read_csv_bound(p);p.write_bytes(b'a,b\n9,9\n')
            self.assertEqual(rows,[{'a':'1','b':'2'}]);self.assertNotEqual(h,I.read_csv_bound(p)[1])

    def test_failed_csv_write_retains_last_good(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'a.csv';p.write_bytes(b'last good\n')
            with patch.object(B.csv.DictWriter,'writerows',side_effect=ValueError('invalid new rows')):
                with self.assertRaises(ValueError):B.write_csv(p,[{'x':1}],['x'])
            self.assertEqual(p.read_bytes(),b'last good\n')
            self.assertEqual(list(Path(d).glob('*.tmp')),[])

    def test_input_marker_enables_fix_only_for_new_v3_and_v4_forms(self):
        rows=[]
        for i in range(12):
            rows.append(dict(date=f'2026-10-{i+1:02}',league='epl',team='Arsenal',opponent='Chelsea',venue='home',home_team='Arsenal',away_team='Chelsea',shots_for='10',shots_against='12',xg_for='1' if i<8 else '',xg_against='1.2' if i<8 else '',sot_for='3',sot_against='4'))
        teams,leagues=P.PUB.build_base_indexes(rows)
        a=P.old_form(teams,'epl','Arsenal','home')
        args=dict(league='epl',fixture_date=NOW.date(),team='Arsenal',opponent='Chelsea',venue='home',home='Arsenal',away='Chelsea')
        v=P.PUB.live_form_row(by_team=teams,by_league=leagues,**args)
        for r in rows:r['_shots_input_policy']=I.POLICY
        teams,leagues=P.PUB.build_base_indexes(rows)
        b=P.old_form(teams,'epl','Arsenal','home');w=P.PUB.live_form_row(by_team=teams,by_league=leagues,**args)
        self.assertEqual(a['r10_xg_per_shot_for'],'0.06');self.assertEqual(b['r10_xg_per_shot_for'],'0.1')
        self.assertEqual(v['r10_xg_per_shot_for'],'0.06');self.assertEqual(w['r10_xg_per_shot_for'],'0.1')

    def test_empty_error_envelope_not_verified_break(self):
        with self.assertRaises(ValueError):E.completed({},'serie-a',NOW,NOW-timedelta(days=10))
        with self.assertRaises(ValueError):E.completed({'events':[],'leagues':[{'slug':'eng.1'}]},'serie-a',NOW,NOW-timedelta(days=10))

    def test_provider_alias_is_id_scoped(self):
        self.assertEqual(E.canonical_team({'id':'90','displayName':'Deportivo'},'la-liga'),'La Coruna')
        self.assertEqual(E.canonical_team({'id':'91','displayName':'Deportivo'},'la-liga'),'Deportivo')

    def test_new_cohort_does_not_rewrite_old_predictions(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'ledger.jsonl';old=dict(contract_id='x',version='old',probability=.4)
            P.append_new(path,[old]);before=path.read_bytes()
            P.append_new(path,[old]);self.assertEqual(path.read_bytes(),before)

if __name__=='__main__':unittest.main()
