import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone, timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fair_odds_board import build_board, fingerprint, has_new_confirmed

class DailyBoardTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.base=self.root/'data/goalscorer';self.base.mkdir(parents=True)
        self.now=datetime(2026,9,8,18,tzinfo=timezone.utc)
        self.fixture=dict(match_date='2026-09-08',kickoff_utc='2026-09-08T19:00:00Z',home_team='Home',away_team='Away',
             lineup_type='standard',changed_at='2026-09-08T17:50:00Z',observed_at='2026-09-08T17:59:00Z')
        for side in ('home','away'):
            self.fixture[side+'_players']=[side+str(i) for i in range(11)]
            self.fixture[side+'_starters']=[dict(name=side+str(i),role_group='GK' if i==0 else 'FW',line_index=-1 if i==0 else 0) for i in range(11)]
            self.fixture[side+'_formation']='4-3-3';self.fixture[side+'_subs']=['usual'] if side=='home' else []
        self.model=dict(match_date='2026-09-08',home_team='Home',away_team='Away',player_team='Home',player_name='home1',probability=.3,
          method='model',allocation_status='confirmed_roster',lineup_fingerprint=fingerprint(self.fixture),generated_at='2026-09-08T17:56:00Z')
        self.quote=dict(match_date='2026-09-08',home_team='Home',away_team='Away',player_team='Home',player_name='home1',bookmaker='Bet365',
          odds_decimal=4,captured_at='2026-09-08T17:55:00Z')
    def board(self):
        for name,payload in [('confirmed-lineups.json',{'fixtures':[self.fixture]}),('fair-odds-player-forecasts.json',{'players':[self.model]}),
                             ('serie-a-penalty-takers.json',{'Home':{'primary':'usual','secondary':'home1'}})]:
            (self.base/name).write_text(json.dumps(payload))
        with (self.base/'goalscorer-live-comparison.csv').open('w',newline='') as handle:
            writer=csv.DictWriter(handle,fieldnames=self.quote);writer.writeheader();writer.writerow(self.quote)
        return build_board(self.root,self.now)['fixtures'][0]
    def test_full_xi_missing_odds_and_penalty_handover(self):
        f=self.board();self.assertEqual(sum(len(t['players']) for t in f['teams']),22)
        p=f['teams'][0]['players'][1]
        self.assertEqual(p['gapPp'],5);self.assertEqual(p['modelEvPct'],20)
        self.assertTrue(p['penaltyActive']);self.assertEqual(p['penaltyInheritedFrom'],'usual')
        self.assertIsNone(f['teams'][1]['players'][1]['bookmakerOdds'])
        self.assertIsNone(f['teams'][0]['players'][0]['fairOdds'])
    def test_stale_quote_has_no_gap(self):
        self.quote['captured_at']='2026-09-08T16:00:00Z'
        self.assertIsNone(self.board()['teams'][0]['players'][1]['gapPp'])
    def test_pre_lineup_quote_has_no_gap(self):
        self.quote['captured_at']='2026-09-08T17:49:00Z'
        self.assertIsNone(self.board()['teams'][0]['players'][1]['gapPp'])
    def test_forecast_from_old_lineup_is_not_reused(self):
        self.fixture['home_players'][2]='new starter'
        self.assertIsNone(self.board()['teams'][0]['players'][1]['fairOdds'])
    def test_quarantined_fixture_cannot_publish_model_prices(self):
        self.model['trust_tier']='T3'
        self.assertIsNone(self.board()['teams'][0]['players'][1]['fairOdds'])
    def test_kickoff_locks_gap_and_post_kickoff_forecast(self):
        self.now+=timedelta(hours=1)
        self.assertIsNone(self.board()['teams'][0]['players'][1]['gapPp'])
        self.model['generated_at']='2026-09-08T19:01:00Z'
        self.assertIsNone(self.board()['teams'][0]['players'][1]['fairOdds'])
    def test_missing_probability_is_not_zero_or_infinity(self):
        for invalid in (None,'NaN',False,0,1):
            self.model['probability']=invalid
            self.assertIsNone(self.board()['teams'][0]['players'][1]['fairOdds'])
    def test_limited_history_estimate_is_visible_but_not_recorded_as_an_edge(self):
        self.model.update(method='fallback',limited_data=True)
        player=self.board()['teams'][0]['players'][1]
        self.assertAlmostEqual(player['fairOdds'],3.33,places=2)
        self.assertEqual(player['pricingStatus'],'limited_data')
        self.assertIsNone(player['gapPp'])
        self.assertIsNotNone(player['pricingReason'])
    def test_raw_quote_survives_missing_model_identity(self):
        raw=dict(self.quote,player_name='away1',player_team='Away',odds_decimal=7)
        with (self.base/'goalscorer-odds-history.csv').open('w',newline='') as handle:
            writer=csv.DictWriter(handle,fieldnames=raw);writer.writeheader();writer.writerow(raw)
        player=self.board()['teams'][1]['players'][1]
        self.assertEqual(player['bookmakerOdds'],7)
        self.assertIsNone(player['modelProbability'])
        self.assertIsNotNone(player['pricingReason'])
    def test_missing_quote_explains_feed_gap_without_inventing_a_price(self):
        player=self.board()['teams'][1]['players'][2]
        self.assertEqual(player['bookmakerStatus'],'not_in_feed')
        self.assertIsNotNone(player['bookmakerReason'])
        self.assertIsNone(player['bookmakerOdds'])
    def test_bookmaker_club_aliases_match_the_lineup_fixture(self):
        self.fixture.update(home_team='Venezia',away_team='Fiorentina')
        self.model.update(home_team='Venezia',away_team='Fiorentina',player_team='Venezia',lineup_fingerprint=fingerprint(self.fixture))
        self.quote.update(home_team='Venezia FC',away_team='ACF Fiorentina',player_team='Venezia FC')
        player=self.board()['teams'][0]['players'][1]
        self.assertEqual(player['bookmakerOdds'],4)
        self.assertIsNotNone(player['modelProbability'])
    def test_first_official_comparison_is_immutable_and_includes_negative_edges(self):
        from fair_odds_board import record_daily_board
        f=self.board(); f['teams'][0]['players'][1]['gapPp']=-2
        f['teams'][0]['players'][1]['modelEvPct']=-8
        payload={'generatedAt':self.now.isoformat(),'fixtures':[f]}
        record_daily_board(payload,self.root)
        f['teams'][0]['players'][1]['modelEvPct']=30
        record_daily_board(payload,self.root)
        with (self.base/'fair-odds-daily-serie-a.csv').open() as handle: rows=list(csv.DictReader(handle))
        self.assertEqual(len(rows),1);self.assertEqual(float(rows[0]['ev']),-.08)
        self.assertEqual(rows[0]['recommended_stake_units'],'0')
    def test_observed_bookmaker_fixture_aliases_keep_prices_on_both_sides(self):
        cases=[('Genoa','Frosinone','Genoa CFC','Frosinone Calcio'),
               ('Sunderland','Arsenal','Sunderland AFC','Arsenal FC'),
               ('Borussia Dortmund','Paderborn','Borussia Dortmund','SC Paderborn 07'),
               ('Mainz 05','Eintracht Frankfurt','FSV Mainz','Eintracht Frankfurt'),
               ('Le Havre','Angers','Le Havre AC','Angers SCO'),
               ('Paris FC','Lyon','Paris FC','Olympique Lyon'),
               ('Rennes','Marseille','Stade Rennais FC','Olympique Marseille'),
               ('Sevilla','Valencia','Sevilla FC','Valencia CF')]
        for home,away,book_home,book_away in cases:
            with self.subTest(home=home,away=away):
                self.fixture.update(home_team=home,away_team=away)
                self.quote.update(home_team=book_home,away_team=book_away,player_team=book_home)
                self.assertEqual(self.board()['teams'][0]['players'][1]['bookmakerOdds'],4)
    def test_raw_prices_survive_clean_checkout_and_unrelated_league_refresh(self):
        from fair_odds_board import latest_bookmaker_quotes
        persisted=dict(self.quote,player_team='Away',player_name='away1',odds_decimal=7)
        path=self.base/'bet365-latest-quotes.json'
        path.write_text(json.dumps({'quotes':[persisted]}))
        self.assertEqual(self.board()['teams'][1]['players'][1]['bookmakerOdds'],7)
        newer=dict(persisted,odds_decimal=8,captured_at='2026-09-08T17:59:00Z')
        unrelated=dict(self.quote,home_team='Other',away_team='Fixture')
        with (self.base/'goalscorer-odds-history.csv').open('w',newline='') as h:
            w=csv.DictWriter(h,fieldnames=newer);w.writeheader();w.writerows([newer,unrelated])
        kept=latest_bookmaker_quotes(self.root,self.now)
        self.assertEqual(len(kept),2)
        path.write_text(json.dumps({'quotes':kept}))
        (self.base/'goalscorer-odds-history.csv').unlink()
        self.assertEqual(self.board()['teams'][1]['players'][1]['bookmakerOdds'],8)
        self.now+=timedelta(hours=2)
        p=self.board()['teams'][1]['players'][1]
        self.assertEqual(p['bookmakerOdds'],8)
        self.assertFalse(p['priceFresh'])
    def test_persisted_quotes_reject_invalid_future_and_expired_rows(self):
        from fair_odds_board import latest_bookmaker_quotes
        rows=[dict(self.quote,bookmaker='Other'),dict(self.quote,odds_decimal='NaN'),
              dict(self.quote,captured_at='2026-09-09T17:55:00Z'),dict(self.quote,match_date='2026-09-01')]
        (self.base/'bet365-latest-quotes.json').write_text(json.dumps({'quotes':rows}))
        self.assertEqual(latest_bookmaker_quotes(self.root,self.now),[])
    def test_api_quote_without_team_matches_player_without_model_history(self):
        from fair_odds_board import latest_bookmaker_quotes
        raw=dict(self.quote,player_team='',player_name='away1',odds_decimal=9)
        (self.base/'bet365-latest-quotes.json').write_text(json.dumps({'quotes':[raw]}))
        self.assertEqual(len(latest_bookmaker_quotes(self.root,self.now)),1)
        player=self.board()['teams'][1]['players'][1]
        self.assertEqual(player['bookmakerOdds'],9)
        self.assertIsNone(player['modelProbability'])
    def test_teamless_quote_never_crosses_fixture_or_ambiguous_roster(self):
        raw=dict(self.quote,player_team='',player_name='away1',home_team='Different',odds_decimal=9)
        path=self.base/'bet365-latest-quotes.json'
        path.write_text(json.dumps({'quotes':[raw]}))
        self.assertIsNone(self.board()['teams'][1]['players'][1]['bookmakerOdds'])
        raw['home_team']='Home'
        self.fixture['home_players'][2]='away1'
        path.write_text(json.dumps({'quotes':[raw]}))
        board=self.board()
        self.assertIsNone(board['teams'][0]['players'][2]['bookmakerOdds'])
        self.assertIsNone(board['teams'][1]['players'][1]['bookmakerOdds'])
    def test_only_new_prematch_confirmed_lineups_trigger_capture(self):
        self.board()
        from unittest.mock import patch
        with patch('fair_odds_board.datetime',wraps=datetime) as dt:
            dt.now.return_value=self.now
            self.assertTrue(has_new_confirmed({},self.base/'confirmed-lineups.json'))
            from fair_odds_board import confirmed_signatures
            self.assertFalse(has_new_confirmed(confirmed_signatures(self.base/'confirmed-lineups.json'),self.base/'confirmed-lineups.json'))

if __name__=='__main__':unittest.main()
