import copy
import importlib.util
from pathlib import Path
import unittest
from copy import deepcopy

spec = importlib.util.spec_from_file_location("penalty_news", Path(__file__).parents[1] / "build-penalty-news.py")
news = importlib.util.module_from_spec(spec)
spec.loader.exec_module(news)
from penalty_news_context import incident_context, clock


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


if __name__ == "__main__":
    unittest.main()
