"""Guard player identity namespaces and the existing Super Sub settlement contract."""
import runpy
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

    def test_daily_requires_verified_promotion(self):
        row={'best_bookmaker':'Bet365','signal_type':'fair_odds_daily_board','super_sub_contract_verified':'0'}
        self.assertIsNone(self.settle_replacement(row))
        row['super_sub_contract_verified']='1'
        self.assertEqual(self.settle_replacement(row)[0],'won')

    def test_ambiguous_replacement_and_own_goal_are_not_credited(self):
        self.assertIsNone(self.settle_replacement({'best_bookmaker':'Bet365'},ambiguous=True))
        self.assertIsNone(self.settle_replacement({'best_bookmaker':'Bet365'},own_goal=True))

    def test_other_bookmaker_is_not_credited(self):
        self.assertIsNone(self.settle_replacement({'best_bookmaker':'Other'}))

if __name__ == '__main__': unittest.main()
