import csv
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tennis_break_point_history import histories, enrich_files, valid_counts
from admin_monitor_bundle import build_admin_bundle


def write(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


class BreakPointHistoryTests(unittest.TestCase):
    def fixture(self, root):
        folder = root/'data/oncourt'
        game = dict(winner_id='1', loser_id='2', tour_id='10', round_id='4', date='2026-10-29', result='7-5 6-4')
        stat = dict(winner_id='1', loser_id='2', tour_id='10', round_id='4',
                    w_bpof='6', w_bpw='1', w_bpfaced='4', w_bpsaved='2',
                    l_bpof='4', l_bpw='2', l_bpfaced='6', l_bpsaved='5')
        write(folder/'games_atp.csv',[game]); write(folder/'stat_atp.csv',[stat])
        write(folder/'players_atp.csv',[dict(id='1',name='One'),dict(id='2',name='Two')])
        return folder, game, stat

    def test_reciprocal_counts_chances_not_converted_breaks(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.fixture(root)
            h=histories(root,[('ATP','10','1','2026-10-30'),('ATP','10','2','2026-10-30')])
            a=h[('ATP','10','1','2026-10-30')]['logs'][0]
            b=h[('ATP','10','2','2026-10-30')]['logs'][0]
            self.assertEqual((a['created'],a['converted'],a['faced'],a['match_chances']),(6,1,4,10))
            self.assertEqual((b['created'],b['converted'],b['faced'],b['match_chances']),(4,2,6,10))

    def test_zero_is_valid_missing_impossible_and_conflicting_are_not(self):
        self.assertIsNotNone(valid_counts({f'{p}_{f}':'0' for p in ('w','l') for f in ('bpof','bpw','bpfaced','bpsaved')}))
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);folder,game,stat=self.fixture(root)
            for changed in [dict(stat,w_bpof=''),dict(stat,w_bpof='7'),dict(stat,w_bpw='9')]:
                write(folder/'stat_atp.csv',[changed])
                row=histories(root,[('ATP','10','1','2026-10-30')])[('ATP','10','1','2026-10-30')]['logs'][0]
                self.assertIsNone(row['created']);self.assertEqual(row['stats_status'],'unavailable')
            write(folder/'stat_atp.csv',[stat,dict(stat,w_bpof='9')])
            row=histories(root,[('ATP','10','1','2026-10-30')])[('ATP','10','1','2026-10-30')]['logs'][0]
            self.assertEqual(row['issue'],'conflicting_stats')

    def test_exact_edition_cutoff_missing_stats_and_partial_match(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);folder,g,s=self.fixture(root)
            write(folder/'games_atp.csv',[g,g,dict(g,tour_id='11'),dict(g,round_id='5',date='2026-10-30'),
                dict(g,round_id='3',date='2026-10-28'),dict(g,round_id='9',result='6-2 1-0 RET')])
            logs=histories(root,[('ATP','10','1','2026-10-30')])[('ATP','10','1','2026-10-30')]['logs']
            self.assertEqual(len(logs),3)
            self.assertEqual(logs[0]['round_id'],'3');self.assertIsNone(logs[0]['created'])
            self.assertEqual(logs[-1]['status'],'retired')

    def test_transport_preserves_predictions_and_original_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.fixture(root)
            board=root/'data/board.csv'
            row=dict(tour='ATP',tour_id='10',player_id='1',date='2026-10-30',projected_aces='9.123456',fair='2.45',tournament_round_log='[]')
            write(board,[row]);original=board.read_bytes()
            report={'matches':[{'tour':'ATP','p_player1':.43,'tournament_players':[dict(row)]}],'records':[{'roi':-5}]}
            original_report=json.dumps(report)
            result=enrich_files(root,{'props-board':original.decode(),'most-aces-current':original_report})
            new=list(csv.DictReader(io.StringIO(result['props-board'])))[0]
            self.assertEqual({k:new[k] for k in row},row)
            self.assertEqual(board.read_bytes(),original)
            other=json.loads(result['most-aces-current']);self.assertEqual(other['records'],report['records']);self.assertEqual(other['matches'][0]['p_player1'],.43)
            self.assertEqual(json.loads(new['break_point_history'])['logs'][0]['created'],6)
            (root/'config').mkdir();(root/'config/admin-monitor-catalog.json').write_text(json.dumps([{'id':'props-board','file':'data/board.csv'}]))
            bundle=build_admin_bundle(root)
            self.assertEqual(bundle['admin_break_point_history_status'],'included')
            self.assertIn('source_sha256',bundle['admin_manifest'][0])

    def test_unavailable_native_source_keeps_original_transport(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'config').mkdir()
            write(root/'board.csv',[dict(tour='ATP',tour_id='10',player_id='1',date='2026-10-30')])
            (root/'config/admin-monitor-catalog.json').write_text('[{"id":"props-board","file":"board.csv"}]')
            bundle=build_admin_bundle(root)
            self.assertEqual(bundle['admin_files']['props-board'],(root/'board.csv').read_bytes().decode())
            self.assertIn('unavailable:',bundle['admin_break_point_history_status'])


if __name__ == '__main__': unittest.main()
