import copy
import json
from pathlib import Path
import runpy
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import tennis_most_aces_settlement as bridge
from tennis_most_aces_current import record
SHADOW = runpy.run_path(str(SCRIPTS/'tennis-most-aces-shadow.py'))
import test_tennis_most_aces_shadow as fixtures


class PricedSettlementTests(unittest.TestCase):
    def setUp(self):
        sample = fixtures.MostAcesShadowTests()
        self.row = SHADOW['registration_row'](sample.board(), sample.capture())
        self.row.update(bookmaker='Grosvenor', tournament='Basel')
        self.match = sample.result()
        self.counts = {'parse_year': lambda s: int(s[:4]), 'pair_key': SHADOW['pair_key']}
        self.key = ('ATP', 2026, SHADOW['pair_key']('Player One', 'Player Two'))

    def test_shared_lookup_includes_priced_only_fixture_and_is_idempotent(self):
        rows = [self.row]; before = copy.deepcopy(self.row)
        self.assertEqual(bridge.pending_signals(rows)[0]['player'], 'Player One')
        index = {self.key: [self.match]}
        self.assertEqual(bridge.settle_priced(rows, index, self.counts, SHADOW), 1)
        self.assertEqual(self.row['result'], 'loss')
        for k in ('selected_odds','p_player1','p_draw','p_player2','observation_id','bet_eligible'):
            self.assertEqual(self.row[k], before[k])
        settled = copy.deepcopy(rows)
        self.assertEqual(bridge.settle_priced(rows, index, self.counts, SHADOW), 0)
        self.assertEqual(rows, settled)

    def test_quarantine_and_duplicate_pending_are_not_reopened(self):
        for fields in ({'quarantine_reason':'bad identity'}, {'duplicate_of_signal_id':'original'}, {'settlement_note':'duplicate_contract_of:x'}):
            r = dict(self.row, **fields); before = copy.deepcopy(r)
            self.assertEqual(bridge.pending_signals([r]), [])
            self.assertEqual(bridge.settle_priced([r], {self.key:[self.match]}, self.counts, SHADOW), 0)
            self.assertEqual(r, before)

    def test_first_set_retirement_void_and_later_retirement_held(self):
        for score, changed, status in [('5-2 RET.',1,'void'),('6-4 2-1 RET',0,'pending'),('',0,'pending'),('8-1 RET',0,'pending')]:
            r = dict(self.row)
            self.assertEqual(bridge.settle_priced([r], {self.key:[dict(self.match,score=score)]}, self.counts, SHADOW), changed)
            self.assertEqual(r['settlement_status'], status)
            if changed:self.assertEqual(r['pnl'],'0.000')

    def test_record_refresh_does_not_refresh_price_timestamp(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'current.json';original={'generated_at':'2026-01-01T08:00:00Z','matches':[{'prices':[{'captured_at':'old'}]}]}
            p.write_text(json.dumps(original))
            bridge.refresh_current_records(p, [dict(self.row,settlement_status='settled',result='loss',pnl='-1')],record)
            current=json.loads(p.read_text())
            self.assertEqual(current['generated_at'], original['generated_at'])
            self.assertEqual(current['matches'],original['matches'])
            self.assertEqual(current['records'][0]['profit'],-1)

    def test_morning_runner_requests_results_for_priced_only_fixture(self):
        runner=runpy.run_path(str(SCRIPTS/'tennis-settle-model-evidence.py'))
        class StopAfterLookup(Exception):pass
        captured=[]
        def lookup(source, rows):
            captured.extend(rows)
            raise StopAfterLookup()
        def read(path):return [self.row] if path.name=='most-aces-1x2-observations.csv' else []
        counts={'read_csv':read,'load_oncourt_index':lookup}
        modules={'tennis-props-settle-shadow.py':counts,
                 'tennis-most-aces-forecast.py':{'read_csv':read,'signal_row':lambda r:r},
                 'tennis-most-aces-shadow.py':SHADOW,'tennis-props-rate-trend-prospective.py':{}}
        with tempfile.TemporaryDirectory() as folder, patch('runpy.run_path',side_effect=lambda p:modules[Path(p).name]):
            with self.assertRaises(StopAfterLookup):runner['run'](SCRIPTS.parent,Path(folder),Path(folder)/'oncourt')
        self.assertEqual(len(captured),1)
        self.assertEqual(captured[0]['player'],'Player One')
        self.assertEqual(captured[0]['opponent'],'Player Two')


if __name__=='__main__':unittest.main()
