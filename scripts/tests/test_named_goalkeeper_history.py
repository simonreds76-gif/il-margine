from pathlib import Path
import sys,tempfile,unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from named_goalkeeper_history import target_record,retain
from football_identity import read

class KeeperHistoryTests(unittest.TestCase):
    def test_preserves_conflicts_and_unknowns_without_imputation(self):
        page={'general':{'matchTimeUTCDate':'2026-10-11T13:00:00Z','homeTeam':{'id':1},'awayTeam':{'id':2}}}
        rows=[{'is_goalkeeper':True,'started':True,'minutes':90,'saves':3,'event_saves':2,'target_conflict':True},
              {'is_goalkeeper':True,'started':True,'minutes':90,'saves':None,'event_saves':None,'target_conflict':False}]
        with patch('named_goalkeeper_history.validate') as validate, patch('named_goalkeeper_history.extract',return_value=rows):
            result=target_record(page,{'id':'10','league_id':'47'},b'original','now')
            validate.assert_called_once()
        self.assertFalse(result['full_match_agreement'])
        self.assertEqual(result['keepers'][0]['saves'],3)
        self.assertIsNone(result['keepers'][1]['saves'])

    def test_repeated_payload_is_not_duplicated_and_revisions_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'history.json.gz'
            first={'match_id':'10','source_sha256':'first','keepers':[{'saves':2}]}
            second={'match_id':'10','source_sha256':'second','keepers':[{'saves':3}]}
            self.assertTrue(retain(path,first));self.assertFalse(retain(path,first));self.assertTrue(retain(path,second))
            self.assertEqual(read(path)['fixtures']['10'],[first,second])

if __name__=='__main__':unittest.main()
