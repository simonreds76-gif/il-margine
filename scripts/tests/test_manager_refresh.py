import importlib.util
from pathlib import Path
import unittest
import json
import sys
sys.path.insert(0,str(Path(__file__).parents[1]))
spec=importlib.util.spec_from_file_location('refresh',Path(__file__).parents[1]/'refresh-manager-atlas.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)

class RefreshTests(unittest.TestCase):
    def test_only_exact_unknown_identity_holds_can_accompany_verified_results(self):
        candidates=[['verified'],['held']]
        added=[{'id':'verified'}]
        pending=[{'id':'held','reason':'Manager needs identity review: New Coach','coaches':[{'id':'a'},{'id':'b'}]}]
        self.assertTrue(mod.identity_quarantine_complete(candidates,added,pending))
        for reason in ['Match date/teams/score conflict','No unique exact fixture match','Provider coach name changed','Unfinished']:
            self.assertFalse(mod.identity_quarantine_complete(candidates,added,[{**pending[0],'reason':reason}]))
        self.assertFalse(mod.identity_quarantine_complete(candidates+[['unprocessed']],added,pending))
        self.assertFalse(mod.identity_quarantine_complete(candidates,added,pending*2))
        self.assertFalse(mod.identity_quarantine_complete(candidates,added+[{'id':'held'}],pending))

    def test_verified_luis_garcia_provider_id_survives_context_review_date(self):
        root=Path(__file__).parents[2]
        registry=json.loads((root/'scripts/config/manager-atlas-identities.json').read_text(encoding='utf-8'))
        crosswalk=json.loads((root/'scripts/config/manager-fotmob-identities.json').read_text(encoding='utf-8'))
        coach={'id':'242474','name':'Luis García'}
        self.assertEqual(mod.resolve_coach(coach,'Sevilla','2026-10-12',registry,crosswalk),'mgr-0366')
        # A verified person ID does not expire with a historical name-only window.
        self.assertEqual(mod.resolve_coach(coach,'Sevilla','2026-10-20',registry,crosswalk),'mgr-0366')
        with self.assertRaises(ValueError):
            mod.resolve_coach({'id':'unknown','name':'Luis García'},'Sevilla','2026-10-20',registry,crosswalk)
        with self.assertRaises(ValueError):
            mod.resolve_coach({'id':'242474','name':'Luis García Fernández'},'Sevilla','2026-10-12',registry,crosswalk)
        self.assertEqual(mod.resolve_coach({'id':'other','name':'Luis García'},'Espanyol','2023-05-01',registry,crosswalk),'mgr-0674')

    def page(self):
        return {'general':{'matchId':'42','leagueId':47},'header':{'status':{'finished':True,'utcTime':'2026-09-20T13:00:00Z'},'teams':[{'id':1,'name':'A','score':1},{'id':2,'name':'B','score':0}]},'content':{'lineup':{'homeTeam':{'id':1,'coach':{'id':8,'name':'Coach A','isCoach':True}},'awayTeam':{'id':2,'coach':{'id':9,'name':'Coach B','isCoach':True}}}}}
    def test_coaches_are_fixture_specific_and_oriented(self):
        x=mod.extract_coaches(self.page(),42)
        self.assertEqual([c['id'] for c in x['coaches']],['8','9'])
        self.assertEqual((x['date'],x['hg'],x['ag']),('2026-09-20',1,0))
    def test_other_fixture_or_unfinished_or_swapped_lineup_rejected(self):
        with self.assertRaises(ValueError):mod.extract_coaches(self.page(),43)
        p=self.page();p['header']['status']['finished']=False
        with self.assertRaises(ValueError):mod.extract_coaches(p,42)
        p=self.page();p['content']['lineup']['homeTeam']['id']=2
        with self.assertRaises(ValueError):mod.extract_coaches(p,42)
    def test_unregistered_and_ambiguous_names_are_not_guessed(self):
        r={'managers':[{'id':'one','name':'Coach A','aliases':[]}]}
        self.assertEqual(mod.resolve_coach({'id':'8','name':'Coach A'},'A','2026-09-20',r,{}),'one')
        with self.assertRaises(ValueError):mod.resolve_coach({'id':'9','name':'A'},'A','2026-09-20',r,{})
        r['managers'].append({'id':'two','name':'Coach A','aliases':[]})
        with self.assertRaises(ValueError):mod.resolve_coach({'id':'8','name':'Coach A'},'A','2026-09-20',r,{})
    def test_provider_crosswalk_requires_matching_name(self):
        r={'managers':[{'id':'one','name':'Full Name','aliases':[]}]};x={'8':{'managerId':'one','names':['Short Name']}}
        self.assertEqual(mod.resolve_coach({'id':'8','name':'Short Name'},'A','2026-09-20',r,x),'one')
        with self.assertRaises(ValueError):mod.resolve_coach({'id':'8','name':'Someone Else'},'A','2026-09-20',r,x)
    def test_review_is_bound_to_one_fixture_and_provider_id(self):
        row={'providerMatchId':'42','evidence':['https://club.example/report'],'reviewedAt':'2026-09-27'}
        self.assertIs(mod.reviewed_fixture({'fixture-a':row},'fixture-a',42),row)
        self.assertIsNone(mod.reviewed_fixture({'fixture-a':row},'fixture-b',42))
        with self.assertRaises(ValueError):mod.reviewed_fixture({'fixture-a':row},'fixture-a',43)
        with self.assertRaises(ValueError):mod.reviewed_fixture({'fixture-a':{'providerMatchId':'42'}},'fixture-a',42)
    def test_reviewed_club_aliases_do_not_merge_other_clubs(self):
        self.assertEqual(mod.club_key('Ipswich Town'),mod.club_key('Ipswich'))
        self.assertEqual(mod.club_key('Deportivo A Coruña'),mod.club_key('Deportivo La Coruña'))
        self.assertNotEqual(mod.club_key('Deportivo La Coruña'),mod.club_key('Deportivo Alaves'))

if __name__=='__main__':unittest.main()
