import copy, json, sys, tempfile, unittest
from pathlib import Path
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import tennis_sisal_5050 as T
import sisal_event_comparison as E
from sisal_5050_reporting import weekly_text

NOW=datetime(2026,10,28,10,tzinfo=timezone.utc)

def record():
    return dict(id='target',hash='basehash',fixture_key='77:4:1:2',registered_at=NOW.isoformat(),
        native=dict(tid='77',round='4',pid='1',opp='2'),best_of=3,mean=5.,expected_points=65.,
        row=dict(player='One',opponent='Two',tournament='Basel',capture_ts=(NOW-timedelta(minutes=1)).isoformat(),
                 match_start_utc='2099-10-28T12:00:00+00:00',line='4.5',over_odds='2.5',under_odds='1.6'),
        board=dict(tournament='Basel',current_env_ace_factor='1',ace_rate_adj='.07'),
        features=dict(incumbent_aces=5.),arms=T.arms(5.,4.5,2.5,1.6))

def evidence(**kw):
    return dict(dict(id='previous',tid='77',result_date='2026-10-27',first_observed_complete_at='2026-10-28T08:00:00+00:00',
                     actual_aces=1,expected_aces_on_actual_points=10,source_hash='raw'),**kw)

class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.p=E.folder(self.root)
        for name in E.FROZEN:
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('# frozen')
        E.register(self.root,NOW-timedelta(hours=1))
        T.atomic(self.p/'evidence-status.json',dict(state='READY',prepared_at='2026-10-28T09:00:00+00:00',editions=['77'],missing_by_edition={}))
        self.ev=[];T.append(self.p/'evidence.jsonl',self.ev,evidence())
        self.pred=patch.object(E,'predictor',return_value=lambda f:[5.]*len(f));self.pred.start()
        self.module=patch.object(E.runpy,'run_path',return_value={'SLAM_COUNT_BIAS_CORRECTION':{}});self.module.start()
    def tearDown(self):self.pred.stop();self.module.stop();self.tmp.cleanup()
    def test_same_quote_independent_arms_no_rewrite_or_duplicate(self):
        r=record();old=copy.deepcopy(r);E.capture_pairs(self.root,[r],NOW);E.capture_pairs(self.root,[r],NOW)
        rows=T.ledger(self.p/'pairs.jsonl');self.assertEqual(len(rows),1);self.assertEqual(r,old)
        x=rows[0];self.assertEqual(x['state'],'PAIRED');self.assertAlmostEqual(x['mean'],5*101/110)
        self.assertEqual(x['original'],r['arms']);self.assertEqual(x['adjusted'],T.arms(x['mean'],4.5,2.5,1.6))
    def test_evidence_after_quote_same_day_other_edition_never_used(self):
        cap=NOW-timedelta(minutes=1)
        rows=[evidence(),evidence(id='late',first_observed_complete_at=NOW.isoformat()),evidence(id='today',result_date='2026-10-28'),evidence(id='other',tid='88')]
        self.assertEqual([x['id'] for x in E.choose_evidence(rows,'77',cap)],['previous'])
    def test_corrections_only_affect_quotes_after_observation(self):
        earlier=evidence();later=evidence(actual_aces=7,first_observed_complete_at=NOW.isoformat())
        self.assertEqual(E.choose_evidence([earlier,later],'77',NOW-timedelta(minutes=1))[0]['actual_aces'],1)
        self.assertEqual(E.choose_evidence([earlier,later],'77',NOW)[0]['actual_aces'],7)
    def test_unavailable_does_not_look_like_zero_evidence(self):
        T.atomic(self.p/'evidence-status.json',dict(state='READY',prepared_at=NOW.isoformat(),editions=['77'],missing_by_edition={}))
        E.capture_pairs(self.root,[record()],NOW)
        x=T.ledger(self.p/'pairs.jsonl')[0];self.assertEqual(x['state'],'UNAVAILABLE');self.assertNotIn('mean',x)
    def test_real_zero_evidence_uses_neutral(self):
        self.ev=[];(self.p/'evidence.jsonl').write_text('')
        E.capture_pairs(self.root,[record()],NOW)
        x=T.ledger(self.p/'pairs.jsonl')[0];self.assertEqual(x['evidence_rows'],0);self.assertEqual(x['mean'],5.)
    def test_incomplete_edition_rejected(self):
        T.atomic(self.p/'evidence-status.json',dict(state='READY',prepared_at='2026-10-28T09:00:00+00:00',editions=['77'],missing_by_edition={'77':1}))
        E.capture_pairs(self.root,[record()],NOW);self.assertEqual(T.ledger(self.p/'pairs.jsonl')[0]['reason'],'incomplete_event_evidence')
    def test_pre_registration_quote_cannot_backfill(self):
        r=record();r['row']['capture_ts']='2026-10-28T08:00:00+00:00'
        E.capture_pairs(self.root,[r],NOW);self.assertEqual(T.ledger(self.p/'pairs.jsonl')[0]['reason'],'price_precedes_comparison_registration')
    def test_frozen_artifact_rejects_change(self):
        (self.root/E.FROZEN[0]).write_text('changed')
        with self.assertRaises(ValueError):E.register(self.root,NOW)
    def test_singles_scope_keeps_unknown_identities_and_missing_stats(self):
        def g(a,b,round='4',result='6-4 6-4'):
            return dict(winner_id=a,loser_id=b,tour_id='77',round_id=round,result=result)
        games=[g('1','2'),g('3','4'),g('5','2'),g('1','2','3'),g('1','2','5','W/O')]
        known,excluded=E.required_singles(games,{'1':'One','2':'Two','3':'A/B','4':'C/D'},['77'],lambda s:None if s=='W/O' else (2,0))
        self.assertEqual(known['77'],{('1','2','77','4'),('5','2','77','4')})
        self.assertEqual(excluded,{'77':1})
    def test_source_revision_is_explicit_and_preserves_original_evidence(self):
        original=(self.p/'registration.json').read_bytes();old=T.sha(self.root/E.SELF)
        (self.root/E.SELF).write_text('# repaired singles scope');new=T.sha(self.root/E.SELF)
        with self.assertRaises(ValueError):E.register(self.root,NOW)
        revision=E.register_source_revision(self.root,NOW,old,new)
        self.assertEqual(E.register(self.root,NOW)['source_revision'],revision)
        self.assertEqual((self.p/'registration.json').read_bytes(),original)
        self.assertEqual(len(T.ledger(self.p/'evidence.jsonl')),1)
        E.capture_pairs(self.root,[record()],NOW)
        self.assertEqual(T.ledger(self.p/'pairs.jsonl')[0]['reason'],'price_precedes_source_revision')
        # A later rebuild must never revise this rejected old quote.
        r=record();r['row']['capture_ts']=(NOW+timedelta(minutes=1)).isoformat()
        E.capture_pairs(self.root,[r],NOW+timedelta(minutes=2))
        self.assertEqual(len(T.ledger(self.p/'pairs.jsonl')),1)
        self.assertEqual(T.ledger(self.p/'pairs.jsonl')[0]['state'],'UNAVAILABLE')
    def test_revision_does_not_authorise_model_changes_or_later_code_edits(self):
        old=T.sha(self.root/E.SELF);(self.root/E.SELF).write_text('# repair')
        new=T.sha(self.root/E.SELF);E.register_source_revision(self.root,NOW,old,new)
        (self.root/E.FROZEN[0]).write_text('# changed model')
        with self.assertRaises(ValueError):E.register(self.root,NOW)
        with self.assertRaises(ValueError):E.register_source_revision(self.root,NOW,old,new)
        (self.root/E.FROZEN[0]).write_text('# frozen')
        (self.root/E.SELF).write_text('# arbitrary later code')
        with self.assertRaises(ValueError):E.register(self.root,NOW)
    def test_neutral_changes_input_not_final_mean(self):
        r=record();r['board'].update(current_env_ace_factor='.95',ace_rate_adj='.07')
        f=[]
        def score(rows):f.extend(rows);return [7.]*len(rows)
        mu,proof=E.neutral_mean(r,score,{})
        self.assertEqual(mu,7.);self.assertGreater(min(x['incumbent_aces'] for x in f),5.2)
        self.assertEqual(r['features']['incumbent_aces'],5.)
    def test_neutral_rounding_crossing_tree_split_is_unavailable(self):
        r=record();r['board'].update(current_env_ace_factor='.95',ace_rate_adj='.07')
        with self.assertRaises(ValueError):E.neutral_mean(r,lambda rows:[x['incumbent_aces'] for x in rows],{})
    def test_neutral_clipped_rates_unavailable(self):
        for rate in ('.002','.28',''):
            r=record();r['board'].update(current_env_ace_factor='.95',ace_rate_adj=rate)
            with self.assertRaises(ValueError):E.neutral_mean(r,lambda rows:[7.]*len(rows),{})
    def test_both_versions_settle_from_same_result_and_reporting(self):
        r=record();E.capture_pairs(self.root,[r],NOW)
        result={r['id']:dict(status='settled',completed=True,actual=9,actual_points=70)}
        reg=dict(registered_at=NOW.isoformat())
        report=T.summarize([r],result,reg,{},NOW,{})
        report['event_comparison']=E.comparison_report(self.root,[r],result,reg,NOW)
        v=report['event_comparison']['versions']
        self.assertEqual(v['original']['quotes'],v['event_adjusted']['quotes'])
        self.assertEqual(v['original']['completed_contracts'],1)
        self.assertEqual(v['event_adjusted']['bias'][0]['actual_mean'],9)
        self.assertIn('Event-adjusted 50/50',weekly_text(report));self.assertFalse(report['config']['alerts'])
    def test_empty_roi_not_zero_and_old_base_unpaired(self):
        c=E.comparison_report(self.root,[record()],{},dict(registered_at=NOW.isoformat()),NOW)
        self.assertEqual(c['unpaired_base_records'],1)
        self.assertIsNone(c['versions']['event_adjusted']['arms']['blend50']['roi_pct'])

if __name__=='__main__':unittest.main()
