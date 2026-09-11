import csv
import runpy
import tempfile
import unittest
from pathlib import Path

class ShadowSchemaTests(unittest.TestCase):
    def test_append_preserves_super_sub_settlement_evidence(self):
        mod=runpy.run_path(str(Path(__file__).resolve().parents[1]/'goalscorer-shadow-tracker.py'))
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'signals.csv'
            settled=dict(date='2026-09-10',match='Home vs Away',player='Original',settled='1',
                         bet_outcome='won',pnl_units='3',named_player_goals='0',named_player_outcome='lost',
                         super_sub_settlement_policy='bet365_automatic_20260909',super_sub_replacement_chain='Replacement')
            with path.open('w',newline='') as handle:
                writer=csv.DictWriter(handle,fieldnames=settled);writer.writeheader();writer.writerow(settled)
            fresh=dict(date='2026-09-11',match='Home vs Away',player='Next')
            self.assertEqual(mod['append_rows_dedup'](path,[fresh]),1)
            self.assertEqual(mod['append_rows_dedup'](path,[fresh]),0)
            with path.open(newline='') as handle: rows=list(csv.DictReader(handle))
            self.assertEqual(len(rows),2)
            for key,value in settled.items(): self.assertEqual(rows[0][key],value)

if __name__=='__main__': unittest.main()
