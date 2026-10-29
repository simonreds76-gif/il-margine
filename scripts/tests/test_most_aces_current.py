import copy
import unittest
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
import tennis_most_aces_current as current

class CurrentTests(unittest.TestCase):
    def setUp(self):
        self.s=current.load_shadow();self.now=datetime.now(timezone.utc)
        stamp=self.now.isoformat();day=self.now.date().isoformat()
        self.board=dict(generated_at_utc=stamp,date=day,tour='ATP',tournament='Basel',surface='Hard',
            player1='Player One',player2='Player Two',p_player1='0.65',p_draw='0.10',p_player2='0.25',
            fair_player1='1.538',fair_draw='10',fair_player2='4',player1_confidence='MED',player2_confidence='MED',
            quote_status='READY',model=current.COUNT_MODEL)
        self.capture=dict(event_id='source:1',date=day,tournament='Basel',bookmaker='Grosvenor',
            player1='Player One',player2='Player Two',player1_odds='1.8',draw_odds='8',player2_odds='4.5',
            capture_ts=stamp,match_start_utc=(self.now+timedelta(hours=1)).isoformat())
    def report(self,boards=None,captures=None):
        return current.compare(boards or [self.board],captures or [self.capture],[],self.now,self.s)
    def test_player_order_is_preserved_across_books(self):
        cap=dict(self.capture,player1='Player Two',player2='Player One',player1_odds='4.5',player2_odds='1.8')
        p=self.report(captures=[cap])['matches'][0]['prices'][0]
        self.assertEqual(p['player1_odds'],'1.8');self.assertEqual(p['candidate']['recommended_side'],'P1')
    def test_started_stale_and_wrong_event_not_matched(self):
        for cap in [dict(self.capture,capture_ts=(self.now-timedelta(hours=2)).isoformat()),
                    dict(self.capture,match_start_utc=self.now.isoformat()),dict(self.capture,tournament='Vienna')]:
            self.assertEqual(self.report(captures=[cap])['matches'][0]['prices'],[])
    def test_partial_or_unverified_contract_no_candidate(self):
        for changes in [dict(draw_odds=''),dict(bookmaker='Sisal IT')]:
            p=self.report(captures=[dict(self.capture,**changes)])['matches'][0]['prices'][0]
            self.assertIsNone(p['candidate'])
    def test_direct_is_never_alerted_and_one_best_price_is_selected(self):
        direct=dict(self.board,model='most_aces_direct_1x2_v1',evidence_tier='RECENT',live_parity_status='EXACT_REGISTERED_FEATURES')
        second=dict(self.capture,bookmaker='Bet365',event_id='other:1',player1_odds='1.9',evidence_sha256='test',source_url='https://www.bet365.com/')
        r=self.report(boards=[self.board,direct],captures=[self.capture,second])
        rows=current.alert_rows(r,self.now)
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['bookmaker'],'Bet365')
        self.assertEqual(rows[0]['model'],current.COUNT_MODEL)
    def test_old_report_does_not_alert(self):
        r=self.report();r['generated_at']=(self.now-timedelta(hours=1)).isoformat()
        self.assertEqual(current.alert_rows(r,self.now),[])
    def test_repeat_registration_does_not_reprice_saved_selection(self):
        ledger=[];self.assertEqual(self.s.register([self.board],[self.capture],ledger),1)
        before=copy.deepcopy(ledger)
        self.assertEqual(self.s.register([self.board],[dict(self.capture,player1_odds='1.9')],ledger),0)
        self.assertEqual(ledger,before)
    def test_record_is_version_specific(self):
        rows=[dict(model=current.COUNT_MODEL,bet_eligible='yes',settlement_status='settled',result='loss',pnl='-1'),
              dict(model='direct',bet_eligible='yes',settlement_status='settled',result='win',pnl='5')]
        self.assertEqual(current.record(rows,current.COUNT_MODEL)['roi'],-100)

    def test_history_requires_exact_fixture_and_unique_player_row(self):
        row=dict(date=self.board['date'],tour='ATP',tournament='Basel',surface='Hard',
                 player='Player One',opponent='Player Two',tournament_round_log='[]',same_tournament_matches='0')
        players=current.tournament_players(self.board,[row],self.s)
        self.assertEqual(len(players),1)
        self.assertEqual(len(current.tournament_players(dict(self.board,player1_id='sackmann:other'),[row],self.s)),1)
        self.assertEqual(current.tournament_players(dict(self.board,player1_oncourt_id='different'),[row],self.s),[])
        self.assertEqual(current.tournament_players(self.board,[dict(row,tournament='Vienna')],self.s),[])
        self.assertEqual(current.tournament_players(self.board,[row,row],self.s),[])

if __name__=='__main__':unittest.main()
