import copy
import importlib.util
from pathlib import Path
import unittest
from copy import deepcopy
import json
import tempfile
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("penalty_news", Path(__file__).parents[1] / "build-penalty-news.py")
news = importlib.util.module_from_spec(spec)
spec.loader.exec_module(news)
from penalty_news_context import incident_context, narrative_context, clock
publisher_spec = importlib.util.spec_from_file_location('penalty_publisher', Path(__file__).parents[1] / 'publish-penalty-news.py')
publisher = importlib.util.module_from_spec(publisher_spec)
publisher_spec.loader.exec_module(publisher)


class PenaltyNewsTests(unittest.TestCase):
    def setUp(self):
        self.shot = {"id": 100, "situation": "Penalty", "period": "SecondHalf", "eventType": "Goal",
                     "teamId": 1, "playerId": 9, "fullName": "Test Taker", "min": 90, "minAdded": 4}
        self.payload = {"props": {"pageProps": {
            "general": {"leagueId": 47, "finished": True, "matchId": 123, "matchTimeUTCDate": "2026-10-18T12:00:00Z"},
            "header": {"status": {"finished": True}, "teams": [{"id": 1, "name": "Home", "score": 2}, {"id": 2, "name": "Away", "score": 1}]},
            "content": {"shotmap": {"shots": [self.shot]}}}}}
        self.clubs = {"1": {"name": "Home", "logo": "/home.png"}}

    def run_normalize(self):
        return news.normalize(self.payload, "https://www.fotmob.com/matches/example#123", "2026-10-21T12:00:00Z", self.clubs)

    def test_completed_fact_report_without_reviews(self):
        mid, articles, exclusions = self.run_normalize()
        self.assertEqual(mid, "123")
        self.assertEqual(exclusions, [])
        a = articles[0]
        self.assertEqual(a["minute"], "90+4")
        self.assertEqual(a["clubUrl"], "/penalty-takers/epl/home")
        self.assertIsNone(a["cause"])
        self.assertIn("Home 2–1 Away", a["sentences"][1])

    def test_saved_penalty_and_rebound_goal_are_not_a_conversion(self):
        self.shot["eventType"] = "AttemptSaved"
        rebound = dict(self.shot, id=101, situation="RegularPlay", eventType="Goal")
        self.payload["props"]["pageProps"]["content"]["shotmap"]["shots"].append(rebound)
        articles = self.run_normalize()[1]
        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0]["outcome"], "saved")

    def test_shootouts_and_regular_goals_excluded(self):
        self.shot["period"] = "PenaltyShootout"
        self.assertEqual(self.run_normalize()[1], [])
        self.shot["period"] = "SecondHalf"
        self.shot["situation"] = "RegularPlay"
        self.assertEqual(self.run_normalize()[1], [])

    def test_no_guessing_unknown_outcomes(self):
        self.shot["eventType"] = "Blocked"
        _, articles, exclusions = self.run_normalize()
        self.assertEqual(articles, [])
        self.assertEqual(len(exclusions), 1)

    def test_unfinished_matches_are_held(self):
        self.payload["props"]["pageProps"]["header"]["status"]["finished"] = False
        with self.assertRaises(ValueError):
            self.run_normalize()

    def test_retakes_held_and_identical_events_deduplicated(self):
        shots = self.payload["props"]["pageProps"]["content"]["shotmap"]["shots"]
        shots.append(copy.deepcopy(self.shot))
        self.assertEqual(len(self.run_normalize()[1]), 1)
        shots[1]["id"] = 101
        self.assertEqual(self.run_normalize()[1], [])
        self.assertEqual(len(self.run_normalize()[2]), 2)

    def test_idempotent_merge_and_source_corrections(self):
        first = self.run_normalize()[1]
        second = copy.deepcopy(first)
        second[0]["publishedAt"] = second[0]["updatedAt"] = "2026-10-22T12:00:00Z"
        result = news.merge(first, second, {"123"})
        self.assertEqual(result, first)
        second[0]["sourceHash"] = "corrected"
        result = news.merge(first, second, {"123"})
        self.assertEqual(result[0]["publishedAt"], first[0]["publishedAt"])
        self.assertNotEqual(result[0]["updatedAt"], first[0]["updatedAt"])
        self.assertEqual(news.merge(first, [], set()), first)
        self.assertEqual(news.merge(first, [], {"123"}), [])

    def commentary(self):
        return {'Events': [
            {'MessageId': 'kick', 'Elapsed': 90, 'ElapsedPlus': 4, 'IncidentCode': 'PSG', 'Players': [{'Id': 9, 'TeamId': 1}]},
            {'MessageId': 'conceded', 'Elapsed': 90, 'ElapsedPlus': 2, 'IncidentCode': 'penalty lost', 'Description': 'Penalty conceded by Defender (Away) after a foul in the penalty area.', 'Players': [{'Id': 8, 'TeamId': 2}]},
            {'MessageId': 'won', 'Elapsed': 90, 'ElapsedPlus': 2, 'IncidentCode': 'penalty won', 'Description': 'Penalty Home. Winger draws a foul in the penalty area.', 'Players': [{'Id': 7, 'TeamId': 1}]},
        ]}

    def test_award_identifies_fouled_player_not_taker(self):
        result = incident_context(self.shot, self.commentary(), {})
        self.assertEqual(result['wonBy'], 'Winger')
        self.assertEqual(result['concededBy'], 'Defender')
        self.assertLess(clock(45, 9), clock(46))

    def test_handball_does_not_invent_foul_winner(self):
        c = self.commentary()
        c['Events'].pop()
        c['Events'][1]['Description'] = 'Penalty conceded by Defender (Away) with a handball in the penalty area.'
        result = incident_context(self.shot, c, {})
        self.assertEqual(result['type'], 'handball')
        self.assertIsNone(result['wonBy'])

    def test_wrong_player_and_intervening_attempt_are_rejected(self):
        c = self.commentary()
        c['Events'][0]['Players'][0]['Id'] = 99
        self.assertIsNone(incident_context(self.shot, c, {}))
        c = self.commentary()
        c['Events'].insert(1, {'IncidentCode': 'PSG', 'Elapsed': 90, 'ElapsedPlus': 3})
        self.assertIsNone(incident_context(self.shot, c, {}))

    def test_ambiguous_awards_and_wrong_team_rejected(self):
        c = self.commentary()
        c['Events'].append(deepcopy(c['Events'][-1]))
        self.assertIsNone(incident_context(self.shot, c, {}))
        c = self.commentary()
        c['Events'][-1]['Players'][0]['TeamId'] = 2
        self.assertIsNone(incident_context(self.shot, c, {}))

    def test_reviewed_note_expires_when_source_changes(self):
        c = self.commentary()
        c['Events'] = [c['Events'][0], {'MessageId': 'note', 'Elapsed': 90, 'ElapsedPlus': 2, 'Description': 'Verified incident', 'IncidentCode': 'highlight'}]
        notes = {'100': {'type': 'foul', 'wonBy': 'Winger', 'sentence': 'Verified summary', 'evidence': {'note': 'Verified incident'}}}
        self.assertEqual(incident_context(self.shot, c, notes)['method'], 'reviewed_commentary')
        c['Events'][1]['Description'] = 'Corrected incident'
        self.assertIsNone(incident_context(self.shot, c, notes))

    def test_commentary_must_match_the_fixture(self):
        with self.assertRaisesRegex(ValueError, 'different teams'):
            news.normalize(self.payload, 'https://example.com', '2026-10-21', self.clubs,
                           {'HometeamId': 99, 'AwayteamId': 2, 'Events': []})

    def narrative(self):
        content = {'playerStats': {'7': {'id': 7, 'name': 'Rasmus Højlund', 'teamId': 1,
                    'stats': [{'stats': {'Penalty won': {'key': 'penalties_won', 'stat': {'value': 1}}}}]},
                    '8': {'id': 8, 'name': 'Relja Obrić', 'teamId': 2, 'stats': []}}}
        window = [{'IncidentCode': 'highlight', 'Elapsed': 89, 'MessageId': 'award',
                   'Description': 'PENALTY TO HOME! Hojlund is bundled over inside the area.'}]
        return content, window

    def test_narrative_foul_crosschecks_player_and_unique_team_penalty(self):
        content, window = self.narrative()
        result = narrative_context(self.shot, window, content, [self.shot])
        self.assertEqual(result['wonBy'], 'Rasmus Højlund')
        self.assertIsNone(result['concededBy'])
        self.assertIsNone(narrative_context(self.shot, window, content, [self.shot, dict(self.shot, id=101)]))
        content['playerStats']['7']['stats'] = []
        self.assertIsNone(narrative_context(self.shot, window, content, [self.shot]))

    def test_narrative_handball_requires_single_opponent_and_rejects_negation(self):
        content, window = self.narrative()
        content['playerStats']['7']['stats'] = []
        window[0]['Description'] = 'PENALTY TO HOME! A raised Obric hand blocked the shot.'
        self.assertEqual(narrative_context(self.shot, window, content, [self.shot])['concededBy'], 'Relja Obrić')
        window[0]['Description'] += ' VAR decides it was not handball. The penalty is overturned.'
        self.assertIsNone(narrative_context(self.shot, window, content, [self.shot]))

    def test_unrelated_earlier_incident_is_not_used(self):
        content, window = self.narrative()
        content['playerStats']['7']['stats'] = []
        content['playerStats']['6'] = {'id': 6, 'name': 'Other Defender', 'teamId': 2, 'stats': []}
        window[0]['Description'] = 'PENALTY TO HOME! A raised Obric hand blocked the shot.'
        window.append({'IncidentCode': 'highlight', 'Elapsed': 85, 'MessageId': 'old',
                       'Description': 'Other Defender sees his handball appeal rejected at the other end.'})
        self.assertEqual(narrative_context(self.shot, window, content, [self.shot])['concededBy'], 'Relja Obrić')

    def test_commentary_outage_keeps_enriched_article_only_for_unchanged_facts(self):
        old = self.run_normalize()[1]
        old[0]['incident'] = {'sentence': 'Verified detail'}
        fresh = self.run_normalize()[1]
        self.assertEqual(news.merge(old, fresh, {'123'}), old)
        fresh[0]['eventHash'] = 'corrected-score'
        self.assertIsNone(news.merge(old, fresh, {'123'})[0]['incident'])

    def test_partial_capture_preserves_unresolved_fixture_and_adds_new_one(self):
        old = self.run_normalize()[1]
        fresh = deepcopy(old)
        fresh[0].update(id='fotmob:456:101', matchId='456')
        merged = news.merge(old, fresh, {'456'})
        self.assertEqual({a['matchId'] for a in merged}, {'123', '456'})


class PublicationGuards(unittest.TestCase):
    def test_readback_resolves_full_url_for_project_scoped_ci_token(self):
        with patch.object(publisher, 'run', return_value='verified page') as command:
            self.assertEqual(publisher.deployment_page('vercel', 'https://candidate.vercel.app', '/penalty-news/article'), 'verified page')
            command.assert_called_once_with('vercel', 'curl', 'https://candidate.vercel.app/penalty-news/article', '--', '--fail', '--silent')

    def run_guard(self, enabled, outputs):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent, prefix='penalty-test-') as tmp:
            root = Path(tmp)
            (root / 'config').mkdir()
            (root / 'config/penalty-news-publication.json').write_text(json.dumps({'enabled': enabled, 'lookbackDays': 8}))
            with patch.object(publisher, 'ROOT', root), patch('sys.argv', ['publish', '--state', str(root / 'evidence')]), patch.object(publisher, 'run', side_effect=outputs) as command:
                publisher.main()
                return command.call_count

    def test_preview_does_not_invoke_capture_git_or_deployment(self):
        self.assertEqual(self.run_guard(False, []), 0)

    def test_dirty_checkout_blocks_publication(self):
        with self.assertRaisesRegex(RuntimeError, 'unrelated tracked changes'):
            self.run_guard(True, [' M src/app/page.tsx'])

    def test_feature_branch_cannot_publish(self):
        with self.assertRaisesRegex(RuntimeError, 'production branch'):
            self.run_guard(True, ['', 'codex/penalty-news-preview-20261021'])


if __name__ == "__main__":
    unittest.main()
