import copy
import json
from datetime import datetime,timezone,timedelta
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import atlas_championship_weekly as p
import atlas_championship_cloud as cloud
from atlas_championship_state import read

class ChampionshipCloudTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        f=Path(__file__).parent/'fixtures/championship'
        cls.config=read(p.REGISTRY)['championship']
        cls.calendar=read(f/'calendar.json')
        cls.rows=p.calendar(cls.calendar,cls.config,datetime(2026,10,25,12,tzinfo=timezone.utc))
        cls.row=next(r for r in cls.rows if r['home']=='Charlton Athletic')
        cls.fixtures=read(f/'fixtures.json')
        cls.fixture=p.match_provider(cls.row,cls.fixtures,cls.config)
        cls.day=read(f/'day.json');cls.history=read(f/'history.json')
        cls.bootstrap=read(p.ROOT/'data/football-atlas/extensions/championship-bootstrap.json')
    def test_exact_result_and_price(self):
        self.assertEqual(p.verify_result(self.row,self.day,self.config),5836889)
        self.assertEqual(p.price(self.row,self.fixture,self.history)['odds'],[3.52,3.52,2.15])
    def test_wrong_country(self):
        day=copy.deepcopy(self.day)
        for l in day['leagues']:l['ccode']='SCO'
        with self.assertRaises(ValueError):p.verify_result(self.row,day,self.config)
    def test_wrong_score(self):
        with self.assertRaises(ValueError):p.verify_result({**self.row,'hg':4},self.day,self.config)
    def test_wrong_participant(self):
        with self.assertRaises(ValueError):p.match_provider(self.row,[{**self.fixture,'participant1Id':123456}],self.config)
    def test_rescheduled_not_priced(self):
        f={**self.fixture,'trueStartTime':(p.dt(self.fixture['startTime'])+timedelta(hours=24)).isoformat()}
        with self.assertRaisesRegex(ValueError,'reschedule'):p.price(self.row,f,self.history)
    def test_original_prices_immutable(self):
        old=copy.deepcopy(self.bootstrap['rows'][0]);new={**old,'odds':[9,8,7]}
        rows,conflicts=p.merge([old],[new]);self.assertEqual(rows,[old]);self.assertFalse(conflicts)
    def test_result_correction_held(self):
        old=copy.deepcopy(self.bootstrap['rows'][0]);new={**old,'hg':99}
        rows,conflicts=p.merge([old],[new]);self.assertEqual(rows,[old]);self.assertEqual(len(conflicts),1)
    def test_bootstrap_contains_only_independent_forward_data(self):
        self.assertEqual(len(cloud.check(self.bootstrap)['rows']),12)
        bad=copy.deepcopy(self.bootstrap);bad['rows'][0]['date']='2025-10-01'
        with self.assertRaises(ValueError):cloud.check(bad)
        bad=copy.deepcopy(self.bootstrap);bad['seedSha256']='private'
        with self.assertRaises(ValueError):cloud.check(bad)
    def test_checkpoint_failed_read_does_not_bootstrap(self):
        store=object.__new__(cloud.Store)
        with patch.object(store,'request',side_effect=ValueError('offline')):
            with self.assertRaises(ValueError):store.get()
    def test_checkpoint_concurrent_change_rejected(self):
        store=object.__new__(cloud.Store)
        with patch.object(store,'request',return_value=[]) as call:
            with self.assertRaisesRegex(ValueError,'Concurrent'):store.put(self.bootstrap,{'updated_at':'old','payload':{}})
            self.assertEqual(call.call_args.kwargs['params']['updated_at'],'eq.old')
    def test_checkpoint_verified_readback(self):
        store=object.__new__(cloud.Store)
        reordered=json.loads(json.dumps(self.bootstrap,sort_keys=True))
        with patch.object(store,'request',return_value=[{}]),patch.object(store,'get',return_value={'payload':reordered}):
            self.assertEqual(store.put(self.bootstrap,None),'verified')
    def test_checkpoint_unchanged_no_write(self):
        store=object.__new__(cloud.Store)
        with patch.object(store,'request') as call:
            self.assertEqual(store.put(self.bootstrap,{'payload':self.bootstrap}),'unchanged');call.assert_not_called()
    def test_quota_reserve(self):
        api=object.__new__(p.FreeCapture);api.config=self.config
        with patch.object(api,'get',return_value={'subscriptions':[{'is_active':True,'sport_ids':[10],'price':0,'request_limit':250,'request_count':215}]}):
            with self.assertRaisesRegex(ValueError,'reserve'):api.account()

if __name__=='__main__':unittest.main()
