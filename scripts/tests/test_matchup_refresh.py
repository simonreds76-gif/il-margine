import sys
import unittest
from copy import deepcopy
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from matchup_refresh import validate

class RefreshTests(unittest.TestCase):
    def setUp(self):
        self.data = {'players':[{'id':'a'},{'id':'b'}], 'portraits':{}, 'countries':[],
                     'matches':[{'id':'m','date':'2026-09-20','p1':0,'p2':1,'o1':2,'o2':2,
                                 'stats1':{'aces':[3,60]},'stats2':None}]}
    def test_extra_results_are_retained_and_priced_without_rewriting_outcomes(self):
        old=deepcopy(self.data)
        old['results']=[dict(id='old',date='2016-01-01',p1=0,p2=1,winner=0,o1=None,o2=None,score='6-4 6-4',event='Test',surface='clay',competition='Challenger')]
        new=deepcopy(old);new['results'][0].update(o1=2,o2=2)
        self.assertTrue(validate(old,new))
        new['results'][0]['winner']=1
        with self.assertRaises(ValueError):validate(old,new)
        new=deepcopy(old);new['results']=[]
        with self.assertRaises(ValueError):validate(old,new)

    def test_date_only_does_not_deploy(self):
        new=deepcopy(self.data);new['asOf']='2026-09-27'
        self.assertFalse(validate(self.data,new))
    def test_missing_statistics_can_be_filled(self):
        new=deepcopy(self.data);new['matches'][0]['stats2']={'aces':[4,70]}
        self.assertTrue(validate(self.data,new))
    def test_edits_or_loss_of_existing_statistics_fail(self):
        for value in [None,{'aces':[4,60]}]:
            new=deepcopy(self.data);new['matches'][0]['stats1']=value
            with self.assertRaises(ValueError):validate(self.data,new)
    def test_missing_match_or_repriced_result_fails(self):
        new=deepcopy(self.data);new['matches']=[]
        with self.assertRaises(ValueError):validate(self.data,new)
        new=deepcopy(self.data);new['matches'][0]['o1']=3
        with self.assertRaises(ValueError):validate(self.data,new)
    def test_player_reindexing_keeps_identity(self):
        new=deepcopy(self.data);new['players'].reverse();new['matches'][0].update(p1=1,p2=0)
        self.assertTrue(validate(self.data,new)) # manifest changed, outcomes did not

if __name__=='__main__':unittest.main()
