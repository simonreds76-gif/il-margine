import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from statshub_daily_scout import odds_comparison, sample, scouting


class PlayerOddsReview(unittest.TestCase):
    def setUp(self):
        self.row = dict(playerId="player.2", statType="shots", oddsType="over", line=1.5)
        self.fixture = dict(id="fixture.1", home="Alpha", away="Beta")
        self.offer = dict(playerId="other-slug.2", marketKey="shots", marketType="over",
                          line=1.5, homeTeam="Alpha", awayTeam="Beta",
                          bookmakers=[dict(bookmaker="A", odd=2.15), dict(bookmaker="B", odd=1.85)])
        self.filters = dict(matchId="match.1", prices="prices older than 6 hours are left out")

    def compare(self, offer, **filters):
        return odds_comparison(self.row, self.fixture, dict(
            data=[offer], filtersApplied={**self.filters, **filters}))

    def test_same_line_all_books_and_measured_age(self):
        result = self.compare(self.offer)
        self.assertEqual(result["best"], 2.15)
        self.assertEqual(result["median"], 2)
        self.assertEqual(result["freshness"], self.filters["prices"])
        self.assertIsNone(self.compare(self.offer, prices="all prices included"))
        self.assertIsNone(self.compare(self.offer, matchId="other.4"))
        for override in (dict(line=2.5), dict(marketType="under"), dict(playerId="person.7"),
                         dict(homeTeam="Beta"), dict(marketKey="tackles")):
            with self.subTest(override=override):
                self.assertIsNone(self.compare({**self.offer, **override}))

    def test_conflicting_bookmaker_odds_are_ambiguous(self):
        self.assertIsNone(self.compare(dict(self.offer, bookmakers=[
            dict(bookmaker="A", odd=2), dict(bookmaker="A", odd=3)])))

    def test_under_counts_use_the_complement_and_exclude_small_samples(self):
        data = dict(samples=[dict(label="role", hits=6, starts=20), dict(label="league", hits=3, starts=5)])
        self.assertEqual(sample(data, "role", "under"), (14, 20))
        self.assertIsNone(sample(data, "league", "over"))
        self.assertIsNone(sample(data, "absent", "over"))

    def test_player_already_issued_is_skipped_without_spending_a_read(self):
        class NoReads:
            limit = 22
        cases = [(None, self.row, self.fixture, dict(odds=2))]
        issued = [dict(matchId="match.1", player="person.2")]
        self.assertEqual(scouting(NoReads(), cases, issued, lambda: ""), dict(checked=0, candidates=0, leads=[]))
