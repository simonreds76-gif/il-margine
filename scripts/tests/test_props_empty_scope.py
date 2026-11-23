"""An empty price file is not sufficient evidence of an empty fixture window."""
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tennis_props_empty_scope import verified_empty


class EmptyScopeTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.now = datetime(2026, 11, 23, 10, 37, tzinfo=timezone.utc)
        self.day = '2026-11-23'
        self.ts = (self.now - timedelta(minutes=1)).isoformat()
        self.inbox = self.root/'data/tennis-props/inbox'
        self.inbox.mkdir(parents=True)
        (self.root/'config').mkdir()
        (self.root/'config/odds-api-bookmaker-allocation.json').write_text(json.dumps(
            dict(market_bookmakers=dict(tennis_props=['A','B']), direct_tennis_grosvenor=False)))
        self.receipt = dict(generated_at=self.ts, all_sources_checked=True,
            sources={book: dict(status='NO_VERIFIED_MARKETS', quotes=0, error_types=[],
                               checked_at=self.ts) for book in ('A','B')}, artifacts={})
        for key, prefix, fields in [('props','bet365-lines','line,market,over_odds,under_odds'),
                ('most_aces','betmgm-most-aces-1x2','player1_odds,draw_odds,player2_odds'),
                ('most_df','most-df-1x2','player1_odds,draw_odds,player2_odds')]:
            file = self.inbox/f'{prefix}-{self.day}.csv'
            file.write_text('event_id,bookmaker,'+fields+'\n')
            self.receipt['artifacts'][key] = dict(name=file.name,sha256=hashlib.sha256(file.read_bytes()).hexdigest())
        self.epoch = {'today_atp.csv': {'sha256':'abc'}}
        self.extract = self.root/'data/oncourt/extraction-status.json'
        self.extract.parent.mkdir()
        self.extract.write_text(json.dumps(dict(state='VERIFIED', completed_at=self.ts, exports=self.epoch)))
        self.board = dict(state='CURRENT',coverage='COMPLETE',expected_fixtures=0, actual_sides=0,
                          board_sha256='xyz', player_history_current=True, native_epoch=self.epoch)
        for name,value in [('native_epoch', self.epoch), ('board_state', self.board), ('expected_props', [])]:
            p = patch('tennis_props_empty_scope.'+name,return_value=value)
            self.addCleanup(p.stop)
            setattr(self,name,p.start())

    def proof(self, **opts):
        (self.inbox/f'bookmaker-check-{self.day}.json').write_text(json.dumps(self.receipt))
        return verified_empty(self.root, self.day, now=self.now, **opts)

    def test_same_evidence_in_capture_and_board(self):
        proof = self.proof(not_before=self.now-timedelta(minutes=2))
        self.assertEqual(proof['sources_checked'],2)
        self.assertEqual(proof,self.proof(require_board=True))

    def test_source_failure_partial_or_absent(self):
        for status in ('PARTIAL_FAILURE','SOURCE_FAILED','MISSING_KEY','DISABLED','NOT_CHECKED','QUOTES_CAPTURED'):
            self.receipt['sources']['A']['status']=status
            self.assertIsNone(self.proof())
        del self.receipt['sources']['A']
        self.assertIsNone(self.proof())

    def test_old_or_wrong_run_or_provider_error(self):
        self.assertIsNone(self.proof(not_before=self.now))
        self.receipt['sources']['A']['error_types']=['timeout']
        self.assertIsNone(self.proof())
        self.receipt['sources']['A']['error_types']=[]
        self.receipt['sources']['A']['checked_at']=(self.now-timedelta(minutes=31)).isoformat()
        self.assertIsNone(self.proof())

    def test_changed_file_and_same_hash_nonempty(self):
        entry = self.receipt['artifacts']['props']
        path = self.inbox/entry['name']
        with path.open('a') as file:
            file.write('1,A,1.5,aces,2,2\n')
        self.assertIsNone(self.proof())
        entry['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertIsNone(self.proof())

    def test_missing_or_invalid_header(self):
        entry=self.receipt['artifacts']['props']
        path=self.inbox/entry['name']
        path.write_text('')
        entry['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertIsNone(self.proof())
        path.unlink()
        self.assertIsNone(self.proof())

    def test_fallback_rows_exclude_empty(self):
        (self.inbox/f'betsbk-lines-{self.day}.csv').write_text('event_id,bookmaker,line,market,over_odds,under_odds\n1,B,2,aces,2,2\n')
        self.assertIsNone(self.proof())

    def test_eligible_or_quarantined_fixture(self):
        self.expected_props.return_value=[{'tour_id':'7'}]
        self.assertIsNone(self.proof())
        def held(root, day, days, quarantined):
            quarantined.append({'reason':'missing_id'})
            return []
        self.expected_props.side_effect=held
        self.assertIsNone(self.proof())

    def test_incomplete_board(self):
        for field,bad in [('state','BLOCKED'),('coverage','PARTIAL_QUARANTINE'),('expected_fixtures',1),
                          ('actual_sides',1),('player_history_current',False),('board_sha256',None)]:
            with self.subTest(field=field), patch.dict(self.board,{field:bad}):
                self.assertIsNone(self.proof(require_board=True))

    def test_old_changed_missing_extraction(self):
        data=json.loads(self.extract.read_text())
        for field,value in [('state','EXTRACTING'),('completed_at','2026-11-22T10:00:00Z'),('exports',{})]:
            self.extract.write_text(json.dumps(dict(data,**{field:value})))
            self.assertIsNone(self.proof())
        self.extract.unlink()
        self.assertIsNone(self.proof())


if __name__ == '__main__':
    unittest.main()
