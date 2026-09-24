import copy
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('update', Path(__file__).parents[1] / 'football_atlas_update.py')
u = importlib.util.module_from_spec(spec)
spec.loader.exec_module(u)
NOW = datetime(2026, 9, 24, 12, tzinfo=timezone.utc)


class AtlasUpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = u.database(Path(self.temp.name))
        self.fixture = dict(id='100', league='premier-league', season='2026-2027', home='A', away='B',
                            kickoff=NOW.isoformat(), status=-1, score=[1, 1])
        self.old = dict(teams=['A','B'], leagues=['premier-league'], seasons=['2026-2027'], crests={}, fixtures=[])
        self.config = {'startedAt': (NOW-timedelta(days=1)).isoformat()}

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def quote(self, minutes, kickoff=NOW):
        with self.db:
            self.db.execute('INSERT INTO quotes VALUES (?,?,?,?,?,?,?,?)',
               ('pin1','premier-league','A','B',kickoff.isoformat(),(NOW-timedelta(minutes=minutes)).isoformat(),'v1','[2.5,3.2,3.1]'))

    def test_rejects_at_start_inplay_old_and_rescheduled_prices(self):
        self.quote(0); self.quote(-1); self.quote(31); self.quote(10,NOW+timedelta(days=1))
        self.assertIsNone(u.select_quote(self.db,self.fixture))
        self.quote(30)
        self.assertEqual(u.select_quote(self.db,self.fixture),[2.5,3.2,3.1])

    def test_latest_eligible_price_wins(self):
        self.quote(29);self.quote(2)
        self.db.execute("UPDATE quotes SET odds='[2.6,3.2,3.0]' WHERE captured=?",((NOW-timedelta(minutes=2)).isoformat(),))
        self.assertEqual(u.select_quote(self.db,self.fixture),[2.6,3.2,3.0])

    def test_requires_stable_completed_result_and_keeps_original(self):
        self.quote(5)
        u.observe_results(self.db,[self.fixture],NOW+timedelta(hours=4))
        with self.assertRaisesRegex(ValueError,'stable'):
            u.candidate(self.old,[self.fixture],self.db,self.config,NOW+timedelta(hours=4))
        u.observe_results(self.db,[self.fixture],NOW+timedelta(hours=6))
        out,n=u.candidate(self.old,[self.fixture],self.db,self.config,NOW+timedelta(hours=6))
        self.assertEqual(n,1);self.assertEqual(out['fixtures'][0][6:8],[1,1]);self.assertEqual(out['fixtures'][0][-1],2)
        self.assertEqual(self.old['fixtures'],[])
        again,n=u.candidate(out,[self.fixture],self.db,self.config,NOW+timedelta(hours=7))
        self.assertEqual(n,0);self.assertEqual(out,again)

    def test_missing_price_blocks_publication_and_no_backfill_before_start(self):
        u.observe_results(self.db,[self.fixture],NOW+timedelta(hours=4))
        u.observe_results(self.db,[self.fixture],NOW+timedelta(hours=6))
        with self.assertRaisesRegex(ValueError,'near-close'):
            u.candidate(self.old,[self.fixture],self.db,self.config,NOW+timedelta(hours=6))
        out,n=u.candidate(self.old,[self.fixture],self.db,{'startedAt':(NOW+timedelta(days=1)).isoformat()},NOW+timedelta(days=2))
        self.assertEqual(n,0)

    def test_correction_never_silently_rewrites_existing_result(self):
        self.quote(5);u.observe_results(self.db,[self.fixture],NOW+timedelta(hours=4))
        u.observe_results(self.db,[self.fixture],NOW+timedelta(hours=6))
        out,_=u.candidate(self.old,[self.fixture],self.db,self.config,NOW+timedelta(hours=6))
        corrected={**self.fixture,'score':[2,1]}
        u.observe_results(self.db,[corrected],NOW+timedelta(hours=7))
        u.observe_results(self.db,[corrected],NOW+timedelta(hours=9))
        with self.assertRaisesRegex(ValueError,'correction'):
            u.candidate(out,[corrected],self.db,self.config,NOW+timedelta(hours=9))

    def test_market_selection_fulltime_only_and_home_draw_away_order(self):
        match={'id':1,'type':'matchup','status':'pending','startTime':NOW.isoformat(),
               'participants':[{'alignment':'home','name':'A'},{'alignment':'away','name':'B'}]}
        market={'matchupId':1,'period':0,'type':'moneyline','status':'open','version':123,
                'prices':[{'designation':'away','price':220},{'designation':'home','price':-150},{'designation':'draw','price':350}]}
        args=([match],[market],'premier-league',{'a':'A','b':'B'},NOW-timedelta(minutes=5))
        quotes=u.extract_quotes(*args)
        self.assertEqual(len(quotes),1)
        self.assertEqual(u.json.loads(quotes[0][-1]),[1+100/150,4.5,3.2])
        for patch in [{'period':1},{'status':'suspended'},{'type':'total'},{'isAlternate':True},
                      {'prices':market['prices'][:2]}]:
            self.assertEqual(u.extract_quotes([match],[{**market,**patch}],*args[2:]),[])
        self.assertEqual(u.extract_quotes([{**match,'isLive':True}],[market],*args[2:]),[])
        self.assertEqual(u.extract_quotes([match],[market],*args[2:4],NOW),[])


if __name__ == '__main__':
    unittest.main()
