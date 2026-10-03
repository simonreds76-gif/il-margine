import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

SCRIPT=Path(__file__).resolve().parents[1]/'goalkeeper-saves-settle.py'
spec=importlib.util.spec_from_file_location('gk_identity_settler',SCRIPT)
settle=importlib.util.module_from_spec(spec);spec.loader.exec_module(settle)

class ExactMatchTests(unittest.TestCase):
    def page(self):
        return {'general':{'matchId':'123','matchTimeUTCDate':'2026-05-16T13:00:00Z','finished':True,'homeTeam':{'id':10},'awayTeam':{'id':20}}}
    def fixture(self): return {'id':123,'home':{'id':10},'away':{'id':20}}
    def test_requests_exact_match_and_preserves_wrapper(self):
        with patch.object(settle,'request_fotmob_json',return_value=self.page()) as request:
            p=settle.request_fotmob_match_payload(123)
            request.assert_called_once_with(settle.FOTMOB_MATCH_URL,{'matchId':123})
            settle.validate_fotmob_fixture(p,self.fixture(),'2026-05-16')
    def test_rejects_different_meeting(self):
        p=self.page();p['general']['matchId']='456'
        with patch.object(settle,'request_fotmob_json',return_value=p):
            with self.assertRaisesRegex(ValueError,'identity mismatch'):settle.request_fotmob_match_payload(123)
    def test_rejects_wrong_date_unfinished_and_reversed_teams(self):
        for field,value in [('matchTimeUTCDate','2026-09-16T13:00:00Z'),('finished',False),('homeTeam',{'id':20})]:
            with self.subTest(field=field):
                p=self.page();p['general'][field]=value
                with self.assertRaises(ValueError):settle.validate_fotmob_fixture({'props':{'pageProps':p}},self.fixture(),'2026-05-16')
    def test_exact_club_aliases_do_not_allow_reversed_fixture(self):
        f={'home':{'name':'Lille'},'away':{'name':'Troyes'}}
        self.assertTrue(settle.fotmob_fixture_match(f,'Lille OSC','ESTAC Troyes'))
        self.assertFalse(settle.fotmob_fixture_match(f,'ESTAC Troyes','Lille OSC'))
    def keeper_payload(self,explicit):
        return {'props':{'pageProps':{'content':{
            'lineup':{'homeTeam':{'starters':[{'id':7,'name':'Test Keeper','positionId':11}]}},
            'shotmap':{'shots':[{'id':1,'eventType':'AttemptSaved','keeperId':7,'isBlocked':False}]},
            'playerStats':{'7':{'id':7,'stats':[{'stats':{'saves':{'key':'saves','stat':{'value':explicit}}}}]}}
        }}}}
    def test_conflicting_published_total_is_not_settled(self):
        actual,detail=settle.fotmob_player_saves(self.keeper_payload(2),'Test Keeper')
        self.assertIsNone(actual);self.assertEqual(detail['error'],'fotmob_save_totals_disagree')
    def test_agreeing_published_total_still_settles(self):
        actual,_=settle.fotmob_player_saves(self.keeper_payload(1),'Test Keeper')
        self.assertEqual(actual,1)

if __name__=='__main__':unittest.main()
