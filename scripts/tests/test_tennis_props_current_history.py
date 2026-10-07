import copy
import csv
from datetime import date, datetime, timezone
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import tennis_props_current_history as H
import tennis_props_full_refresh as A


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def audit():
    return {tour: dict(overlap_matches=150, latest_appended='2026-10-06',
        parity={field: dict(n=150, exact=150) for field in ('w_ace', 'l_ace', 'w_df', 'l_df')})
        for tour in ('atp', 'wta')}


class CurrentHistoryTests(unittest.TestCase):
    def prepared(self, root):
        source = root / 'source.csv';source.write_text('source', encoding='utf-8')
        prepared = root / 'prepared';prepared.mkdir()
        H.write(prepared / 'player-props-baseline.csv', [dict(player='A', matches=10)])
        H.write(prepared / 'player-props-activity.csv', [dict(player='A', matches=12)])
        status = dict(state='CURRENT', version=H.VERSION, as_of='2026-10-07', sources=audit(),
            source_hashes={'source.csv':H.sha(source)},
            output_hashes={p.name:H.sha(p) for p in prepared.iterdir()})
        (prepared / 'player-history-status.json').write_text(json.dumps(status), encoding='utf-8')
        props = root / 'data/tennis-props';props.mkdir(parents=True)
        (props / 'player-props-baseline.csv').write_text('old baseline', encoding='utf-8')
        return prepared, props

    def test_result_dates_determine_freshness_not_output_timestamp(self):
        with tempfile.TemporaryDirectory() as temp:
            prepared, _ = self.prepared(Path(temp))
            p = prepared / 'player-history-status.json'
            status = json.loads(p.read_text());status['sources']['atp']['latest_appended']='2026-06-07'
            status['generated_at']=datetime.now(timezone.utc).isoformat()
            p.write_text(json.dumps(status))
            self.assertEqual(H.history_health(prepared, '2026-10-07')['state'], 'PLAYER_HISTORY_BLOCKED')

    def test_no_same_day_or_future_result_or_poor_parity_accepted(self):
        for day in ('2026-10-07', '2026-10-08'):
            evidence=audit();evidence['wta']['latest_appended']=day
            with self.assertRaises(ValueError):H.validate_source_audit(evidence, date(2026,10,7))
        evidence=audit();evidence['atp']['parity']['w_df']['exact']=140
        with self.assertRaisesRegex(ValueError,'parity'):H.validate_source_audit(evidence,date(2026,10,7))

    def test_publish_preserves_original_and_rejects_source_change_before_any_write(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);prepared, props=self.prepared(root)
            (root / 'source.csv').write_text('new export')
            with self.assertRaisesRegex(ValueError,'Source changed'):H.publish(root,prepared)
            self.assertEqual((props/'player-props-baseline.csv').read_text(),'old baseline')
            (root/'source.csv').write_text('source');H.publish(root,prepared)
            self.assertEqual((props/'history-reference/player-props-baseline.csv').read_text(),'old baseline')
            self.assertEqual(H.history_health(props,'2026-10-07')['state'],'CURRENT')
            self.assertEqual(H.history_health(props,'2026-10-08')['state'],'PLAYER_HISTORY_BLOCKED')
            (prepared/'player-props-activity.csv').write_text('corrupt')
            with self.assertRaisesRegex(ValueError,'validation'):H.publish(root,prepared)

    def test_activity_includes_qualifying_and_challenger_excludes_future_and_conflicts(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'data/oncourt';source.mkdir(parents=True)
            players=[dict(id='1',name='Player One'),dict(id='2',name='Player Two')]
            tours=[dict(id='10',name='Shanghai',rank='4'),dict(id='11',name='Challenger',rank='1')]
            def game(tournament, rnd, day='2026-10-06', result='6-4 6-4'):
                return dict(winner_id='1',loser_id='2',tour_id=tournament,round_id=rnd,date=day,result=result)
            games=[game('10','4'),game('10','2'),game('11','4'),game('10','5','2026-10-07'),
                   game('10','6',result='6-4 6-4'),game('10','6',result='6-2 6-2')]
            for tour in ('atp','wta'):
                H.write(source/f'players_{tour}.csv',players);H.write(source/f'tours_{tour}.csv',tours)
                H.write(source/f'games_{tour}.csv',games)
                H.write(source/f'stat_{tour}.csv',[dict(games[0],w_svpt='60',l_svpt='60')])
            with patch.dict(A.BOARD, {'is_supported_main_tour':lambda t:t.get('id')=='10'}):
                rows, excluded, dates=H.activity(root,date(2026,10,7),[],A)
            player=next(r for r in rows if r['tour']=='ATP' and r['player_id']=='oc:1')
            self.assertEqual((player['main_matches'],player['qual_chall_matches']),(1,2))
            self.assertEqual(excluded['conflicting_results'],2)
            self.assertEqual(dates['atp_qual_chall'],'2026-10-06')

    def test_history_update_does_not_duplicate_physical_signal(self):
        tracker=load('tennis-props-shadow-tracker.py')
        row=dict(date='2026-10-08',tour='ATP',tournament='Shanghai',player='A',opponent='B',market='aces',line='4.5')
        previous=tracker.signal_id(row,'OVER')
        row.update(history_version=H.VERSION,history_as_of='2026-10-07')
        self.assertEqual(tracker.signal_id(row,'OVER'),previous)

    def test_settlement_only_preserves_ledger_and_original_registration(self):
        module=load('tennis-props-full-refresh-shadow.py')
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);config=folder/'config.json';config.write_text('{"capture_enabled":false}')
            reg=folder/'registration.json';reg.write_text('{"config":{"id":"original"}}')
            ledger=folder/'observations.jsonl';ledger.write_text('original immutable ledger')
            def settle(records,source,outcomes,now):outcomes['prior']=dict(status='settled',actual=5)
            with patch.object(sys,'argv',['shadow','--comparison','unused','--out',str(folder),'--config',str(config),'--settle-only']), \
                 patch.object(module,'prepare',side_effect=AssertionError('Must not capture')), \
                 patch.object(module,'summarize',return_value={'markets':{}}) as summary, \
                 patch.dict(module.P, {'ledger':lambda p:[], 'settle':settle}):
                self.assertEqual(module.main(),0)
            self.assertEqual(summary.call_args.args[3],{'id':'original'})
            self.assertEqual(ledger.read_text(),'original immutable ledger')
            self.assertEqual(json.loads(reg.read_text())['config']['id'],'original')
            self.assertEqual(json.loads((folder/'outcomes.json').read_text())['prior']['actual'],5)

    def test_history_cohorts_keep_old_and_fresh_results_separate(self):
        module=load('tennis-props-rate-trend-prospective.py')
        row=dict(market='aces',tournament='Shanghai',line='4.5',over_odds='2.0')
        def record(key, version):
            return dict(id=key,fixture_key=key,registered_at='2026-10-01T10:00:00Z',row=dict(row,history_version=version),
                control={'OVER':{'p_conditional':.6}}, candidate={'OVER':{'p_conditional':.7}},control_side='OVER',candidate_side='OVER')
        result=module.report([record('old','legacy-unversioned'),record('new',H.VERSION)],
            {'old':dict(status='settled',actual=3),'new':dict(status='settled',actual=6)}, {},
            dict(markets=['aces'],id='test'),datetime.now(timezone.utc))
        self.assertEqual(result['history_versions']['legacy-unversioned']['aces']['control']['roi_pct'],-100)
        self.assertEqual(result['history_versions'][H.VERSION]['aces']['control']['roi_pct'],100)


if __name__=='__main__':unittest.main()
