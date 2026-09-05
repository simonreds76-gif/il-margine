import copy
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest.mock import patch

M = runpy.run_path(str(Path(__file__).resolve().parents[1]/'tennis-props-rate-trend-prospective.py'))


class ProspectiveIntegrity(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026,9,5,12,tzinfo=timezone.utc)
        self.row = dict(date='2026-09-05',tour='ATP',tournament='US Open',player='A Player',opponent='B Player',
                        surface='Hard',market='aces',bookmaker='BetsBK',line='8.5',projection_mean='9',
                        distribution='negative_binomial',over_odds='1.9',under_odds='1.9',
                        fair_p_over='.55',fair_p_under='.45',fair_p_push='0',matched_board='yes',
                        capture_ts='2026-09-05T11:30:00Z',match_start_utc='2026-09-05T16:00:00Z')

    def test_after_start_future_capture_and_missing_clock_rejected(self):
        self.assertIsNone(M['eligibility'](self.row,self.now))
        for change in ({'match_start_utc':self.now.isoformat()}, {'capture_ts':'2026-09-05T13:00:00Z'}, {'capture_ts':''}):
            self.assertIsNotNone(M['eligibility'](dict(self.row,**change),self.now))

    def test_invalid_probabilities_and_incomplete_odds_fail(self):
        for change in ({'fair_p_over':'NaN'}, {'fair_p_over':'.8'}, {'under_odds':''}, {'projection_mean':'-1'}):
            self.assertIsNotNone(M['eligibility'](dict(self.row,**change),self.now))

    def test_provider_ids_and_postponements_do_not_duplicate(self):
        self.assertEqual(M['contract_key'](self.row), M['contract_key'](dict(self.row,event_id='new',date='2026-09-06')))
        self.assertNotEqual(M['contract_key'](self.row), M['contract_key'](dict(self.row,line='9.5')))

    def test_hash_chain_detects_rewriting(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'ledger.jsonl'; records=[]
            M['append'](path,records,{'id':'a','row':self.row})
            M['append'](path,records,{'id':'b','row':self.row})
            self.assertEqual(len(M['ledger'](path)),2)
            path.write_text(path.read_text().replace('8.5','9.5'))
            with self.assertRaises(ValueError): M['ledger'](path)

    def test_only_profitable_side_chosen_without_betting_both_sides(self):
        self.assertIsNone(M['policy']({'OVER':{'ev':.01},'UNDER':{'ev':-.1}},.03))
        self.assertEqual(M['policy']({'OVER':{'ev':.05},'UNDER':{'ev':.04}},.03),'OVER')

    def test_missing_source_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest,reason=M['source_manifest'](Path(tmp),['ATP'],self.now,48)
            self.assertIsNone(manifest)
            self.assertEqual(reason,'source_file_missing')

    def test_second_writer_cannot_enter(self):
        with tempfile.TemporaryDirectory() as tmp:
            with M['lock'](Path(tmp)):
                with self.assertRaises(FileExistsError):
                    with M['lock'](Path(tmp)): pass

    def test_settlement_rejects_wrong_event_and_does_not_rewrite_forecasts(self):
        record={'id':'one','row':dict(self.row,match_start_utc='2026-09-05T10:00:00Z')}
        before=copy.deepcopy(record)
        candidate={'tourney_date':'20260905','tourney_name':'Other Event','score':'6-4 6-4'}
        key=('ATP',2026,M['SETTLE']['pair_key']('A Player','B Player'))
        outcomes={}
        with patch.dict(M['SETTLE'], load_oncourt_index=lambda *_:{key:[candidate]},market_count=lambda *_:(10,'ok')):
            M['settle']([record],Path('unused'),outcomes,self.now)
            self.assertEqual(outcomes,{})
            candidate['tourney_name']='US Open'
            M['settle']([record],Path('unused'),outcomes,self.now)
            self.assertEqual(outcomes['one']['actual'],10)
            self.assertEqual(record,before)

    def test_many_lines_never_count_as_many_independent_fixtures(self):
        predictions={side:{'p_conditional':.5,'ev':.05} for side in ('OVER','UNDER')}
        records=[dict(id=str(i),fixture_key='same',row=self.row,registered_at=self.now.isoformat(),
                      control=predictions,candidate=predictions,control_side='OVER',candidate_side='OVER') for i in range(250)]
        outcomes={str(i):{'status':'settled','actual':10} for i in range(250)}
        result=M['report'](records,outcomes,{}, {'markets':['aces'],'id':'test'},self.now+timedelta(days=60))
        self.assertEqual(result['markets']['aces']['independent_fixtures'],1)
        self.assertFalse(result['markets']['aces']['review_floor_met'])


if __name__ == '__main__': unittest.main()
