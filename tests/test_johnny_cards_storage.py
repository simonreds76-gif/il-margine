"""Recovery when the private store loses the response to a Johnny checkpoint write."""
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

from requests.exceptions import ReadTimeout

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from johnny_cards import JohnnyStore
from statshub_daily_io import RemoteError, Store


class CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.store = object.__new__(JohnnyStore)
        self.path = "johnny/editions/2026-11-25/research.json"
        self.report = {"stage": "ranked", "slate": ["fixture-1"]}
        self.store.get = Mock(side_effect=lambda key, missing: missing)
        self.sleep = self.enterContext(patch("johnny_cards.time.sleep"))

    def test_timeout_after_commit_preserves_the_written_report(self):
        self.store.get.side_effect = None
        self.store.get.return_value = self.report
        with patch.object(Store, "put", side_effect=ReadTimeout) as upload:
            self.assertTrue(self.store.put(self.path, self.report))
            self.assertEqual(upload.call_count, 1)

    def test_missing_after_timeout_retries_identical_checkpoint(self):
        with patch.object(Store, "put", side_effect=[ReadTimeout(), RemoteError(503), True]) as upload:
            self.assertTrue(self.store.put(self.path, self.report))
            self.assertEqual(len(upload.mock_calls), 3)
            self.assertTrue(all(c.args == (self.path, self.report, True) for c in upload.mock_calls))

    def test_first_saved_edition_wins_after_uncertain_create(self):
        self.store.get.side_effect = None
        self.store.get.return_value = {"another": "edition"}
        with patch.object(Store, "put", side_effect=ReadTimeout) as upload:
            self.assertFalse(self.store.put(self.path, self.report, replace=False))
            self.assertEqual(upload.call_count, 1)

    def test_persistent_failure_is_bounded_and_visible(self):
        with patch.object(Store, "put", side_effect=ReadTimeout) as upload:
            with self.assertRaises(ReadTimeout):
                self.store.put(self.path, self.report)
            self.assertEqual(upload.call_count, 3)

    def test_auth_errors_and_delivery_claims_are_not_replayed(self):
        for error, key in [(RemoteError(403), self.path), (ReadTimeout(), "receipts/johnny-2026-11-25-0.json")]:
            with self.subTest(key=key), patch.object(Store, "put", side_effect=error) as upload:
                with self.assertRaises(type(error)):
                    self.store.put(key, self.report, replace=False)
                self.assertEqual(upload.call_count, 1)
        self.store.get.assert_not_called()
