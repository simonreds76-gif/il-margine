import copy, importlib.util, json, sys, unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

SCRIPTS=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(SCRIPTS))
spec=importlib.util.spec_from_file_location('test_opponent_shadow',SCRIPTS/'team-shots-opponent-shadow.py')
S=importlib.util.module_from_spec(spec);spec.loader.exec_module(S)
import team_shots_opponent as R

CONFIG=json.loads(S.CONFIG.read_text())
NOW=datetime(2026,9,13,10,tzinfo=timezone.utc)

def history():
    rows=[]
    for day in range(1,9):
        for team,opponent,venue,shots in [('arsenal','chelsea','home',15+day%3),('chelsea','arsenal','away',8+day%2)]:
            rows.append(dict(date=f'2026-08-{day:02}',league='epl',team=team,opponent=opponent,home_team='arsenal',away_team='chelsea',venue=venue,shots_for=shots,shots_against=10,corners_for=5,corners_against=4))
    return rows

def prices():
    common=dict(captured_at='2026-09-13T09:45:00Z',kickoff_at='2026-09-13T12:00:00Z',competition='epl',home_team='Arsenal',away_team='Chelsea',team='Arsenal',line='13.5',bookmaker='Bet365')
    return [dict(common,side='over',odds_decimal='2.30'),dict(common,side='under',odds_decimal='1.90')]

def candidates():
    latest=S.PUB.latest_team_shots_odds(prices(),NOW)
    return S.score_pairs(S.V.paired_rows(latest,S.PAIR_FIELDS),history(),CONFIG)[0]

class ShadowTests(unittest.TestCase):
    def test_no_backdated_registration(self):
        rows=candidates()
        self.assertTrue(rows)
        self.assertEqual(S.register([],rows,CONFIG,NOW+timedelta(days=1)),[])
        self.assertEqual(S.register([],rows,CONFIG,S.PUB.parse_dt(CONFIG['activated_at'])-timedelta(seconds=1)),[])

    def test_immutable_first_pick_and_loss(self):
        rows=candidates()
        ledger=S.register([],rows,CONFIG,NOW)
        self.assertEqual(len(ledger),1)
        ledger[0].update(result='lost',pnl_units=-1,book_price_at_publication=ledger[0]['book_odds'])
        changed=copy.deepcopy(rows)
        for row in changed:row.update(edge=.9,book_odds=9)
        again=S.register(ledger,changed,CONFIG,NOW+timedelta(minutes=1))
        self.assertEqual(again,ledger)
        self.assertEqual(again[0]['published_at_utc'],'2026-09-13T10:00:00Z')
        self.assertEqual(again[0]['price_captured_at_utc'],'2026-09-13T09:45:00Z')

    def test_freshness_and_bad_timestamps(self):
        rows=prices()
        self.assertEqual(len(S.fresh_prices(rows,CONFIG,NOW)[0]),2)
        self.assertEqual(len(S.fresh_prices(rows,CONFIG,NOW+timedelta(hours=4))[0]),0)
        rows[0]['captured_at']='2026-09-13T10:01:00Z'
        self.assertEqual(len(S.fresh_prices(rows,CONFIG,NOW)[0]),1)

    def test_pair_must_be_same_bookmaker_and_synchronized(self):
        rows=prices();rows[0]['bookmaker']='Pinnacle'
        self.assertEqual(S.V.paired_rows(S.PUB.latest_team_shots_odds(rows,NOW),S.PAIR_FIELDS),[])
        rows=prices();rows[0]['captured_at']='2026-09-13T09:00:00Z'
        self.assertEqual(S.V.paired_rows(S.PUB.latest_team_shots_odds(rows,NOW),S.PAIR_FIELDS),[])

    def test_future_counts_cannot_affect_probability(self):
        pairs=S.V.paired_rows(S.PUB.latest_team_shots_odds(prices(),NOW),S.PAIR_FIELDS)
        base=history();a=S.score_pairs(pairs,base,CONFIG)[0]
        changed=copy.deepcopy(base)
        for r in changed:r.update(date='2026-09-13',shots_for=99)
        b=S.score_pairs(pairs,base+changed,CONFIG)[0]
        self.assertEqual(a,b)

    def test_settlement_idempotent_and_preserves_terms(self):
        row=S.register([],candidates(),CONFIG,NOW)[0]
        row['book_price_at_publication']=row['book_odds']
        with patch.object(S.SETTLE,'result_for_fixture',return_value={'home_shots':20,'away_shots':10}):
            self.assertEqual(S.SETTLE.settle_team_shots([row],{}),1)
            original=copy.deepcopy(row)
            self.assertEqual(S.SETTLE.settle_team_shots([row],{}),0)
        self.assertEqual(row,original)
        self.assertEqual(row['actual_team_shots'],20)

    def test_runtime_parity_with_registered_research(self):
        try:
            import numpy
            import scipy
        except ImportError:
            self.skipTest('Optional offline research dependencies')
        spec=importlib.util.spec_from_file_location('parity_research',SCRIPTS/'football-counts-opponent-research.py')
        research=importlib.util.module_from_spec(spec);spec.loader.exec_module(research)
        a,b=R.History(),research.History()
        rows=history()
        for day in sorted({r['date'] for r in rows}):
            batch=[r for r in rows if r['date']==day]
            a.update_day(batch);b.update_day(batch)
        fixture=dict(date='2026-09-13',league='epl',home='arsenal',away='chelsea')
        for venue in ('home','away'):
            x=a.features(fixture,'shots',venue,'2026-09-13');y=b.features(fixture,'shots',venue,'2026-09-13')
            for v,w in zip(x['x'],y['x']):self.assertAlmostEqual(v,w,places=12)
            self.assertAlmostEqual(R.mean_for(CONFIG['parameters'],x),research.mean_for(CONFIG['parameters'],y),places=12)

if __name__=='__main__':unittest.main()
