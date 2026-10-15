from __future__ import annotations

import importlib.util
import csv
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"


def load_script():
    spec = importlib.util.spec_from_file_location(
        "understat_download_shots_tested", SCRIPTS / "understat-download-shots.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


MODULE = load_script()


def load_form_script():
    spec = importlib.util.spec_from_file_location(
        "build_football_form_layer_tested", SCRIPTS / "build-football-form-layer.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


FORM = load_form_script()


class UnderstatArchiveTests(unittest.TestCase):
    def test_deportivo_aliases_join_exact_completed_fixture(self):
        names=['La Coruna','Deportivo La Coruna','Deportivo La Coruña','RC Deportivo de A Coruna']
        self.assertEqual(len({MODULE._normalise_team(n) for n in names}),1)
        self.assertNotEqual(MODULE._normalise_team('Deportivo Alaves'),MODULE._normalise_team('La Coruna'))
        self.assertEqual(MODULE._normalise_team('Espanol'),MODULE._normalise_team('Espanyol'))
        self.assertEqual(MODULE._normalise_team('Santander'),MODULE._normalise_team('Racing Santander'))
        fixture={'isResult':True,'datetime':'2026-10-11 19:00:00','h':{'title':'Real Sociedad'},
                 'a':{'title':'Deportivo La Coruña'},'goals':{'h':'3','a':'2'},'xG':{'h':'1.4','a':'1.2'}}
        lookup=MODULE.parse_understat_xg({'dates':[fixture]})
        row={'date':'2026-10-11','_norm_home':MODULE._normalise_team('Sociedad'),
             '_norm_away':MODULE._normalise_team('La Coruna'),'home_goals':3,'away_goals':2}
        self.assertEqual(MODULE.merge_xg([row],lookup),(1,1))
        self.assertEqual(row['away_xg'],1.2)
        row['home_goals']=2
        self.assertEqual(MODULE.merge_xg([row],lookup),(0,1))
        self.assertEqual(row['home_xg'],'')

    def test_incomplete_invalid_or_conflicting_source_does_not_become_zero_xg(self):
        fixture={'isResult':True,'datetime':'2026-10-11 19:00:00','h':{'title':'A'},
                 'a':{'title':'B'},'goals':{'h':'1','a':'0'},'xG':{'h':'0','a':'0.3'}}
        self.assertEqual(len(MODULE.parse_understat_xg({'dates':[fixture]})),1)
        for change in ({'isResult':False},{'xG':{'h':None,'a':1}},{'xG':{'h':'nan','a':1}}):
            self.assertEqual(MODULE.parse_understat_xg({'dates':[{**fixture,**change}]}),{})
        self.assertEqual(MODULE.parse_understat_xg({'dates':[fixture,{**fixture,'xG':{'h':2,'a':1}}]}),{})

    def test_failed_refresh_retains_verified_pair_but_not_changed_result(self):
        prior={'date':'2026-10-11','league':'la-liga','home_team':'La Coruna','away_team':'B',
               'home_goals':1,'away_goals':0,'home_xg':'0','away_xg':'0.5','source':'football-data+understat-xg'}
        incoming={**prior,'home_xg':'','away_xg':'','source':'football-data'}
        kept=MODULE.merge_existing_rows([prior],[incoming])[0]
        self.assertEqual((kept['home_xg'],kept['away_xg']),('0','0.5'))
        changed=MODULE.merge_existing_rows([prior],[{**incoming,'home_goals':2}])[0]
        self.assertEqual(changed['home_xg'],'')

    def test_partial_refresh_preserves_other_seasons_and_replaces_fixture(self) -> None:
        existing = [
            {"date": "2025-08-01", "league": "epl", "home_team": "A", "away_team": "B", "home_xg": "1.0"},
            {"date": "2026-08-01", "league": "epl", "home_team": "C", "away_team": "D", "home_xg": "1.1"},
        ]
        incoming = [
            {"date": "2026-08-01", "league": "epl", "home_team": "C", "away_team": "D", "home_xg": "2.2"},
        ]
        merged = MODULE.merge_existing_rows(existing, incoming)
        self.assertEqual(len(merged), 2)
        refreshed = next(row for row in merged if row["date"] == "2026-08-01")
        self.assertEqual(refreshed["home_xg"], "2.2")

    def test_form_builder_upserts_supplemental_current_matches(self) -> None:
        fields = ["league", "season", "Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "HS", "AS", "HST", "AST", "HC", "AC", "B365H", "B365D", "B365A"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            primary = root / "primary.csv"
            supplemental = root / "supplemental.csv"
            for path, rows in (
                (primary, [["epl", "2025-2026", "01/05/2026", "A", "B", 1, 0, 10, 8, 4, 2, 5, 3, 2.0, 3.5, 4.0]]),
                (supplemental, [["epl", "2026-2027", "15/08/2026", "C", "D", 2, 1, 12, 9, 5, 3, 6, 2, 1.8, 3.6, 4.5]]),
            ):
                with path.open("w", newline="", encoding="utf-8") as handle:
                    writer = csv.writer(handle, lineterminator="\n")
                    writer.writerow(fields)
                    writer.writerows(rows)
            matches = FORM.load_match_bases(primary, [supplemental])
        self.assertEqual(len(matches), 2)


if __name__ == "__main__":
    unittest.main()
