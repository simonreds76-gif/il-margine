import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tennis_props_current_history import activity_names

class ActivityAliases(unittest.TestCase):
    def test_explicit_alias_keeps_native_activity_in_the_archive_player_bucket(self):
        baseline=[dict(tour='WTA',player_id='214839',player_name='Jodie Burrage')]
        aliases=[dict(tour='WTA',alias='Jodie Anna Burrage',player_name='Jodie Burrage')]
        names=activity_names(baseline,aliases,str.lower)
        self.assertEqual(names[('wta','jodie anna burrage')],{('214839','Jodie Burrage')})
        self.assertEqual(names[('wta','jodie burrage')],names[('wta','jodie anna burrage')])
        self.assertFalse(names[('atp','jodie anna burrage')])

    def test_no_fuzzy_merge_and_ambiguous_canonical_names_remain_ambiguous(self):
        baseline=[dict(tour='ATP',player_id=p,player_name='Same Name') for p in ('1','2')]
        names=activity_names(baseline,[dict(tour='ATP',alias='Other Name',player_name='Same Name')],str.lower)
        self.assertEqual(len(names[('atp','other name')]),2)
        self.assertFalse(names[('atp','same middle name')])

if __name__=='__main__':unittest.main()
