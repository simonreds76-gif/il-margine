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
    def test_registry_ids_and_source_evidence_survive_display_alias(self):
        registry={'managers':[{'id':'m1','name':'Coach Alpha','aliases':['Coach A']},{'id':'m2','name':'Coach B','aliases':[]}]}
        data,audit=mod.join(self.atlas,[self.row],{},registry)
        self.assertEqual(data['fixtures'][0]['homeManager'],'m1')
        self.assertEqual(audit['provenance'][0]['home_source_label'],'Coach A')
        self.assertEqual(audit['provenance'][0]['source_game_id'],'g')
    def test_disputed_fixture_excluded_and_new_manager_requires_review(self):
        data,audit=mod.join(self.atlas,[self.row],{},excluded_games={'g':'disputed'})
        self.assertFalse(data['fixtures']);self.assertEqual(audit['counts']['disputed_manager_assignment'],1)
        with self.assertRaisesRegex(ValueError,'registry review'):
            mod.join(self.atlas,[self.row],{},registry={'managers':[]})
if __name__=='__main__':unittest.main()
