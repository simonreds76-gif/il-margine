import copy,json,sys,tempfile,unittest
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from football_fixture_resolutions import apply_reviewed_voids

class ResolutionTests(unittest.TestCase):
    def test_exact_fixture_only_preserves_forecast_and_no_fake_result(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'config').mkdir()
            resolution={'date':'2026-09-16','league':'la-liga','home':'Levante UD','away':'Athletic Bilbao','outcome':'void','reviewed_at':'2026-10-03T10:00:00Z','reason':'Postponed before play','source_url':'https://example.org/official','scope':'paper_research_only_not_a_claim_about_customer_bet_settlement'}
            (root/'config/football-fixture-resolutions.json').write_text(json.dumps([resolution]))
            row={'match_date':'2026-09-16','league':'la-liga','home_team':'Levante UD','away_team':'Athletic Bilbao','result':'pending','status':'pending','model_probability':.6,'odds_decimal':2,'stake_units':.5}
            rows=[copy.deepcopy(row),{**row,'match_date':'2026-10-21'},{**row,'result':'won','status':'won'}]
            now=datetime(2026,10,3,12,tzinfo=timezone.utc)
            self.assertEqual(apply_reviewed_voids(rows,root,goalkeeper=True,now=now),1)
            self.assertEqual(apply_reviewed_voids(rows,root,goalkeeper=True,now=now),0)
            self.assertEqual((rows[0]['actual_saves'],rows[0]['pnl_units']),('', '0'))
            self.assertEqual((rows[0]['model_probability'],rows[0]['odds_decimal'],rows[0]['stake_units']),(.6,2,.5))
            self.assertEqual(rows[1]['status'],'pending');self.assertEqual(rows[2]['status'],'won')

if __name__=='__main__':unittest.main()
