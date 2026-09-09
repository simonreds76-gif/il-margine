"""Guard player identity namespaces and the existing Super Sub settlement contract."""
import runpy
import csv
import json
import tempfile
from unittest.mock import patch
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
highlights = runpy.run_path(str(ROOT / "scripts/generate-fair-odds-lab-highlights.py"))
settler = runpy.run_path(str(ROOT / "scripts/goalscorer-settle.py"))


class LabPortraitAndSettlementTests(unittest.TestCase):
    def test_legacy_understat_id_is_not_used_for_portraits(self):
        self.assertIsNone(highlights['portrait_url']({'player': 'Unknown', 'player_id': '1234'}, 'epl'))
        self.assertTrue(highlights['portrait_url']({'player': 'Ante Budimir', 'player_id': '1235'}, 'la-liga').endswith('/251269.png'))

    def test_daily_identity_supplies_future_portraits(self):
        row={'signal_type':'fair_odds_daily_board','player_id':'251269'}
        self.assertTrue(highlights['portrait_url'](row,'la-liga').endswith('/251269.png'))
        row['player_id']='not-an-id'
        self.assertIsNone(highlights['portrait_url'](row,'la-liga'))

    def settle_replacement(self, row, ambiguous=False, own_goal=False):
        original={'name':'Starter','subbed_off':True,'sub_out_minute':60}
        substitute={'name':'Replacement','subbed_on':True,'sub_in_minute':60,'goals':1,'own_goals':int(own_goal)}
        players=[original,substitute]
        if ambiguous: players.append(dict(substitute,name='Other replacement'))
        return settler['_settle_super_sub_replacement'](row,team_players=players,player_entry=original)

    def test_legacy_bet365_replacement_win_still_counts(self):
        result=self.settle_replacement({'best_bookmaker':'Bet365'})
        self.assertEqual(result,('won','super_sub_replacement_scored:Replacement',1))

    def test_daily_bet365_automatically_credits_replacement(self):
        row={'best_bookmaker':'Bet365','signal_type':'fair_odds_daily_board','super_sub_contract_verified':'0'}
        self.assertEqual(self.settle_replacement(row)[0],'won')

    def test_ambiguous_replacement_and_own_goal_are_not_credited(self):
        self.assertEqual(self.settle_replacement({'best_bookmaker':'Bet365'},ambiguous=True)[0],'pending')
        self.assertIsNone(self.settle_replacement({'best_bookmaker':'Bet365'},own_goal=True))

    def test_other_bookmaker_is_not_credited(self):
        self.assertIsNone(self.settle_replacement({'best_bookmaker':'Other'}))

    def test_substitute_of_substitute_can_win(self):
        original={'name':'Starter','subbed_off':True,'sub_out_minute':60}
        first={'name':'First sub','subbed_on':True,'sub_in_minute':60,'subbed_off':True,'sub_out_minute':80,'goals':0}
        second={'name':'Second sub','subbed_on':True,'sub_in_minute':80,'goals':1}
        row={'best_bookmaker':'Bet365'}
        result=settler['_settle_super_sub_replacement'](row,team_players=[original,first,second],player_entry=original)
        self.assertEqual(result,('won','super_sub_replacement_scored:Second sub',1))
        self.assertEqual(row['super_sub_replacement_chain'],'["First sub", "Second sub"]')

    def test_prior_daily_losses_are_rechecked_once(self):
        row={'best_bookmaker':'Bet365','signal_type':'fair_odds_daily_board','bet_outcome':'lost'}
        self.assertTrue(settler['_needs_super_sub_recheck'](row))
        row['super_sub_settlement_policy']=settler['SUPER_SUB_POLICY']
        self.assertFalse(settler['_needs_super_sub_recheck'](row))

    def test_highlight_does_not_assign_replacement_goals_to_original_player(self):
        row={'bet_outcome':'won','best_bookmaker_odds':'4','model_fair_odds':'3','model_p_atgs':'.333',
             'settlement_note':'super_sub_replacement_scored:Replacement','goals_scored':'1','super_sub_replacement':'Replacement','super_sub_replacement_goals':'1'}
        hit=highlights['highlight_from_row'](row,'epl')
        self.assertTrue(hit['super_sub_win']); self.assertEqual(hit['goals_scored'],0)

    def test_settler_rechecks_old_daily_loss_and_keeps_named_outcome(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); (root/'epl').mkdir()
            row={'date':'2026-09-01','kickoff':'2026-09-01T12:00:00Z','home_team':'Arsenal','away_team':'Chelsea',
                 'team':'Arsenal','player':'Starter','match':'Arsenal vs Chelsea','best_bookmaker':'Bet365','best_bookmaker_odds':'4',
                 'signal_type':'fair_odds_daily_board','super_sub_contract_verified':'0','settled':'1','bet_outcome':'lost',
                 'goals_scored':'0','pnl_units':'-1','evaluation_stake_units':'1','model_p_atgs':'.3'}
            signals=root/'daily.csv'
            with signals.open('w',newline='') as f:
                w=csv.DictWriter(f,fieldnames=row);w.writeheader();w.writerow(row)
            result={'match_date':row['date'],'home_team':'Arsenal','away_team':'Chelsea','status_finished':True,'players':[
                {'name':'Starter','team':'Arsenal','minutes_played':60,'subbed_off':True,'sub_out_minute':60,'goals':0},
                {'name':'Replacement','team':'Arsenal','minutes_played':30,'subbed_on':True,'sub_in_minute':60,'goals':1}]}
            (root/'epl/fotmob-test.json').write_text(json.dumps(result))
            args=['settler','--league','epl','--signals',str(signals),'--summary',str(root/'summary.txt'),'--match-results-dir',str(root)]
            with patch('sys.argv',args): settler['main']()
            with signals.open() as f: saved=list(csv.DictReader(f))[0]
            self.assertEqual(saved['bet_outcome'],'won');self.assertEqual(float(saved['pnl_units']),3)
            self.assertEqual(saved['goals_scored'],'0');self.assertEqual(saved['named_player_outcome'],'lost')
            self.assertEqual(saved['super_sub_replacement'],'Replacement')
            with patch('sys.argv',args): self.assertEqual(settler['main'](),0)

if __name__ == '__main__': unittest.main()
