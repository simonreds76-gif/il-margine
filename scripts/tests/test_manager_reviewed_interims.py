"""Real held-fixture identities stay exact, append-only, and retry-safe."""
import copy
from pathlib import Path
import tempfile
import unittest
from test_manager_monthly_preservation import ROOT, MonthlyPreservationTests, read, write

IDS=['papi-id1000002371945354','papi-id1000002371945374',
     'papi-id1000002371945398','papi-id1000003472036278','papi-id1000003472036280']

class ReviewedInterimTests(unittest.TestCase):
    def tree(self,root):
        helper=MonthlyPreservationTests();before=helper.fixture_tree(root)
        reviews=read(root/'scripts/config/manager-fixture-reviews.json')
        rows=[reviews[fid] for fid in IDS]
        teams=list(dict.fromkeys(t for r in rows for t in (r['home'],r['away'])))
        leagues=['serie-a','ligue-1']
        fixtures=[];days={}
        for fid,r in zip(IDS,rows):
            fixtures.append([fid,r['date'],leagues.index(r['league']),0,
                teams.index(r['home']),teams.index(r['away']),r['hg'],r['ag'],None,None,None,None])
            days.setdefault(r['date'],[]).append({'league':r['league'],'matches':[{
                'id':int(r['providerMatchId']),'home':{'name':r['home']},
                'away':{'name':r['away']},'status':{'finished':True}}]})
            write(root/'state/managers/matches'/f"{r['providerMatchId']}.json",
                  {**r,'coaches':r['observedCoaches']})
        write(root/'public/football-test.json',{'teams':teams,'leagues':leagues,
              'seasons':['2026-2027'],'fixtures':fixtures})
        for date,groups in days.items():
            write(root/f'state/managers/dates-v2/{date}.json',
                  {'schemaVersion':2,'date':date,'leagues':groups})
        return helper,before,reviews

    def test_one_conflicting_review_is_held_then_resolves_once(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);helper,before,reviews=self.tree(root)
            broken=copy.deepcopy(reviews);broken[IDS[2]]['ag']=3
            write(root/'scripts/config/manager-fixture-reviews.json',broken)
            first=helper.run_offline(root)
            self.assertEqual(first['added'],4)
            self.assertEqual([r['id'] for r in first['pending']],[IDS[2]])
            self.assertEqual(first['pending'][0]['code'],'fixture_conflict')
            write(root/'scripts/config/manager-fixture-reviews.json',reviews)
            second=helper.run_offline(root)
            self.assertEqual(second['added'],1);self.assertEqual(second['pending'],[])
            payload=read(root/'public'/second['manifest']['indexUrl'].lstrip('/'))
            current={r[0]:r for r in payload['rows']}
            self.assertTrue(all(current[r[0]]==r for r in before['rows']))
            self.assertEqual(current[IDS[0]][11],'mgr-0407')
            self.assertEqual(current[IDS[1]][11],'mgr-0407')
            self.assertEqual(current[IDS[2]][10],'mgr-0023')
            self.assertEqual(current[IDS[3]][11],'mgr-0698')
            self.assertEqual(current[IDS[4]][10],'mgr-0699')
            third=helper.run_offline(root)
            self.assertEqual(third['added'],0);self.assertFalse(third['changed'])
            cross=read(root/'scripts/config/manager-fotmob-identities.json')
            self.assertNotIn('1327559',cross);self.assertNotIn('41961',cross)

if __name__=='__main__':unittest.main()
