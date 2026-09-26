import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location('manager_builder',Path(__file__).parents[1]/'build-manager-atlas.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
class JoinTests(unittest.TestCase):
    def setUp(self):
        self.atlas={'teams':['A','B'],'leagues':['premier-league'],'seasons':['2024-2025'],'fixtures':[['m','2025-01-01',0,0,0,1,2,1,2,3,4,1]]}
        self.row={'game_id':'g','competition_id':'GB1','date':'2025-01-01','home_club_name':'A','away_club_name':'B','home_club_goals':'2','away_club_goals':'1','home_club_manager_name':'Coach A','away_club_manager_name':'Coach B'}
    def test_exact_join_keeps_actual_managers(self):
        data,audit=mod.join(self.atlas,[self.row],{})
        self.assertEqual(data['fixtures'][0]['homeManager'],'coacha')
        self.assertEqual(audit['counts']['joined'],1)
    def test_conflicting_score_and_duplicate_are_not_guessed(self):
        wrong={**self.row,'home_club_goals':'3'}
        data,audit=mod.join(self.atlas,[wrong],{})
        self.assertFalse(data['fixtures']);self.assertEqual(audit['counts']['score_conflict'],1)
        data,audit=mod.join(self.atlas,[self.row,self.row],{})
        self.assertFalse(data['fixtures'])
    def test_ambiguous_short_manager_name_is_excluded(self):
        data,audit=mod.join(self.atlas,[{**self.row,'home_club_manager_name':'Míchel'}],{})
        self.assertFalse(data['fixtures']);self.assertEqual(audit['counts']['ambiguous_manager_identity'],1)
if __name__=='__main__':unittest.main()
