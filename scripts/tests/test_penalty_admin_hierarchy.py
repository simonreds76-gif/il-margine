import importlib.util
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from datetime import date
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
live = load('goalscorer-live-penalty-review')
daily = load('goalscorer-penalty-review')
alerts = load('club-penalty-review-alert')
import penalty_alert_reviews as reviews

class AdminHierarchyTests(unittest.TestCase):
    def setUp(self):
        self.context = dict(primary='Riccardo Orsolini', secondary='Artem Dovbyk',
                            tertiary='Federico Bernardeschi', primary_lineup_status='confirmed_bench',
                            secondary_lineup_status='confirmed_bench', tertiary_lineup_status='confirmed_starter',
                            active_taker_pre_match='Federico Bernardeschi', active_slot_pre_match='tertiary',
                            _generated_at='2026-10-31T15:43:36Z', _source_path='stale-context.json')
        self.order = dict(primary='Riccardo Orsolini', secondary='Federico Bernardeschi', tertiary='Artem Dovbyk')
        self.approved = dict(self.order, _generated_at='2026-10-25T14:53:23.684Z')

    def test_bologna_nonempty_context_is_corrected_and_statuses_follow_players(self):
        fixed = live._apply_hierarchy_fallback(self.context, {'_approved_override': self.approved}, '2026-10-31T17:00:00Z')
        self.assertEqual({s:fixed[s] for s in self.order}, self.order)
        self.assertEqual(fixed['secondary_lineup_status'], 'confirmed_starter')
        self.assertEqual(fixed['tertiary_lineup_status'], 'confirmed_bench')
        self.assertEqual(fixed['active_slot_pre_match'], 'secondary')
        self.assertEqual(fixed['_source_path'], 'admin_penalty_state:editorial')
        self.assertEqual(self.context['secondary'], 'Artem Dovbyk')
        self.assertEqual(live._apply_hierarchy_fallback(fixed, {'_approved_override': self.approved}, '2026-10-31T17:00:00Z'), fixed)

    def test_later_undated_naive_and_invalid_edits_do_not_rewrite_history(self):
        for stamp in ('2026-11-01T12:00:00Z', '', '2026-10-24', '2026-10-24T12:00:00', 'invalid'):
            self.assertEqual(reviews.apply_editorial_hierarchy(self.context, dict(self.approved, _generated_at=stamp), '2026-10-31T17:00:00Z'), self.context)
        self.assertEqual(reviews.apply_editorial_hierarchy(self.context, self.approved, '2026-10-24T17:00:00Z'), self.context)

    def test_only_matching_season_admin_order_is_authoritative_even_if_static_file_newer(self):
        state = {'clubs': {'serie-a|bologna': dict(order=self.order, season='2026/27', at=self.approved['_generated_at'])}}
        payload = {'_meta': {'season': {'label':'2026/27'}}, 'Bologna': dict(self.context, last_verified={'date':'2026-10-30'})}
        with patch.object(live, '_editorial_state', return_value=state), patch.object(live, '_load_json', return_value=payload):
            entry = live._load_hierarchy_map(Path('serie-a-penalty-takers.json'), str.lower)['bologna']
        self.assertEqual(entry['_approved_override']['secondary'], 'Federico Bernardeschi')
        self.assertIsNone(reviews.editorial_hierarchy(state, 'serie-a', 'Bologna', '2025/26'))
        self.assertIsNone(reviews.editorial_hierarchy(state, 'serie-a', 'Bologna', ''))

    def test_admin_empty_slot_clears_old_player_without_reusing_their_lineup(self):
        fixed = reviews.apply_editorial_hierarchy(self.context, dict(self.approved, tertiary=''), '2026-10-31T17:00:00Z')
        self.assertEqual(fixed['tertiary'], '')
        self.assertEqual(fixed['tertiary_lineup_status'], '')

    def test_non_admin_fallback_does_not_replace_captured_order(self):
        fixed = live._apply_hierarchy_fallback(self.context, dict(self.order, _generated_at='2026-10-24'), '2026-10-31T17:00:00Z')
        self.assertEqual(fixed, self.context)

    def test_daily_settled_path_uses_saved_admin_order(self):
        import os
        context = dict(self.context, league='serie-a', team='Bologna', team_key='bologna', opponent_key='monza', match_date='2026-10-31')
        event = SimpleNamespace(penalties_attempted=1, penalties_scored=1, match_date=date(2026,10,31),
            match_date_str='2026-10-31', team_key='bologna', opponent_key='monza', team='Bologna', opponent='Monza', player_name='Federico Bernardeschi')
        state = {'clubs': {'serie-a|bologna': dict(order=self.order, season='2026/27', at=self.approved['_generated_at'])}}
        def functions(path, **kwargs):
            if str(path).endswith('goalscorer-model.py'):
                return {'load_match_logs': lambda paths:[event]}
            return {'penalty_role_for_player':lambda hierarchy, player: next(k for k,v in hierarchy.items() if v==player)}
        with patch.dict(os.environ, {'SUPABASE_SERVICE_ROLE_KEY':'test'}), patch.object(reviews,'load_reviews',return_value=state), \
                patch.object(daily.runpy,'run_path',side_effect=functions), patch.object(Path,'exists',return_value=True), \
                patch.object(daily,'_load_json',return_value={'_meta':{'season':{'label':'2026/27'}}}):
            rows = daily.build_review_rows([context], [], 36500)
        self.assertEqual(rows[0]['actual_role_pre_match'], 'secondary')
        self.assertEqual(rows[0]['secondary_lineup_status'], 'confirmed_starter')

    def test_confirmed_backup_held_is_low_but_unknown_and_split_stay_actionable(self):
        context = dict(self.order, _penalty_pitch_status={'primary':'No - bench', 'secondary':'Yes - started', 'tertiary':'No - bench'})
        kind = daily._classify_review_type(context=context, actual_role='secondary', distinct_takers_in_match=1)
        self.assertEqual(kind, 'expected_backup_held')
        self.assertEqual(daily._review_priority(kind), 'low')
        for status in ('Unknown - missing timeline', 'Yes - started'):
            context['_penalty_pitch_status']['primary'] = status
            kind = daily._classify_review_type(context=context, actual_role='secondary', distinct_takers_in_match=1)
            self.assertNotEqual(daily._review_priority(kind), 'low')
        context['_penalty_pitch_status']['primary'] = 'No - bench'
        self.assertEqual(daily._classify_review_type(context=context, actual_role='secondary', distinct_takers_in_match=2), 'multiple_penalties_split')
        # A tertiary taking it while the secondary is on the pitch still needs review.
        self.assertNotEqual(daily._review_priority(daily._classify_review_type(context=context, actual_role='tertiary', distinct_takers_in_match=1)), 'low')

    def test_closed_and_sent_identity_unchanged_by_bologna_correction(self):
        row = {'date':'2026-10-31', 'league':'serie-a', 'team':'Bologna', 'opponent':'Monza', 'actual_taker':'Federico Bernardeschi', 'review_priority':'medium'}
        for slot in ('primary', 'secondary', 'tertiary', 'actual_taker'):
            row[slot+'_on_pitch_at_penalty'] = 'Yes - started' if slot in ('tertiary','actual_taker') else 'No - bench'
        fixed = dict(row, secondary_pre_match='Federico Bernardeschi', tertiary_pre_match='Artem Dovbyk', actual_role_pre_match='secondary')
        self.assertEqual(reviews.ticket_id(row), reviews.ticket_id(fixed))
        self.assertEqual(alerts.row_identity(row), alerts.row_identity(fixed))
        self.assertEqual(alerts.new_actionable_rows([fixed], [], reviews={'tickets':{reviews.ticket_id(row):{'status':'done'}}}), [])
        self.assertEqual(alerts.new_actionable_rows([fixed], [], alerted_identities={alerts.row_identity(row)}), [])
        self.assertEqual(alerts.new_actionable_rows([dict(fixed,review_priority='low')], []), [])
        self.assertEqual(len(alerts.new_actionable_rows([dict(fixed,review_priority='low')], [], priority_teams={alerts.team_identity(fixed):'conditional'})), 1)

if __name__ == '__main__': unittest.main()
