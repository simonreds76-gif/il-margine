import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
from odds_api_allocation import selected_bookmakers
from goalkeeper_saves_live import team_goalkeeper_name
from goalkeeper_price_selection import contract_key

spec = importlib.util.spec_from_file_location('continuity_shadow', SCRIPTS/'goalkeeper-saves-shadow.py')
shadow = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shadow)


class FreeContinuity(unittest.TestCase):
    def test_legacy_workflow_never_requests_removed_book(self):
        for requested in ('Bet365', 'Bet365,Kambi', 'bet365', ''):
            self.assertEqual(selected_bookmakers(requested), 'Paddy Power,Kambi')

    def test_selected_subset_and_unapproved_book(self):
        self.assertEqual(selected_bookmakers('Kambi'), 'Kambi')
        with self.assertRaises(ValueError):
            selected_bookmakers('William Hill')

    def test_missing_or_empty_allocation_does_not_auto_select(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'allocation.json'
            with self.assertRaises(FileNotFoundError): selected_bookmakers('Bet365',p)
            p.write_text(json.dumps({'selected_bookmakers':[]}))
            with self.assertRaises(ValueError): selected_bookmakers('Bet365',p)

    def test_team_keeper_needs_exact_unique_side(self):
        f={'home_starters':[{'name':'Home Keeper','role_group':'GK'}], 'away_starters':[{'name':'Away Keeper','role_group':'GK'}]}
        self.assertEqual(team_goalkeeper_name(f,'away'),'Away Keeper')
        self.assertEqual(team_goalkeeper_name(None,'away'),'')
        self.assertEqual(team_goalkeeper_name(f,'combined'),'')
        f['away_starters'].append({'name':'Other Keeper','role_group':'GK'})
        self.assertEqual(team_goalkeeper_name(f,'away'),'')

    def test_kambi_candidate_identity_without_any_bet365_quote(self):
        f={'lineup_type':'predicted','away_starters':[{'name':'Away Keeper','role_group':'GK'}]}
        price=dict(event_id='123',match_date='2026-10-27',home_team='Arsenal',away_team='Chelsea',
                   player='Away goalkeeper',bookmaker='Kambi',line='3.5',side='over',odds_decimal='2.2',
                   source='odds_api_io:team_goalkeeper_away:Kambi',kickoff_at='2026-10-27T20:00:00Z')
        index={('2026-10-27','arsenal','chelsea'):f}
        with patch.object(shadow,'build_features',return_value=(None,['history_lt_6'])):
            rows=shadow.build_candidates([price],{}, {},index,'2026-10-26T14:00:00Z')
        self.assertEqual(rows[0]['goalkeeper'],'Away Keeper')
        self.assertEqual(rows[0]['lineup_status'],'predicted_starter')
        self.assertEqual(rows[0]['identity_basis'],'same_fixture_lineup_side')
        self.assertNotIn('goalkeeper_team_unresolved',rows[0]['blockers'])
        self.assertIn('history_lt_6',rows[0]['blockers'])
        self.assertIsNotNone(contract_key(rows[0]))

    def test_identity_does_not_accept_unresolved_contract(self):
        r=dict(event_id='1',goalkeeper='Keeper',line=3.5,side='over',contract_scope='team_goalkeeper_home')
        for basis in ('unresolved_team_keeper','',None):
            self.assertIsNone(contract_key(dict(r,identity_basis=basis)))
        for basis in ('same_fixture_lineup_side','same_event_bet365_and_lineup_side'):
            self.assertIsNotNone(contract_key(dict(r,identity_basis=basis)))

if __name__=='__main__': unittest.main()
