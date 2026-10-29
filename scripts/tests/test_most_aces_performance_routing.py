import unittest
from types import SimpleNamespace
from tennis_alert_performance import primary_label

class MostAcesRouting(unittest.TestCase):
    def test_paper_label_is_recognised(self):
        self.assertEqual(primary_label(SimpleNamespace(labels=['MOST ACES PAPER'],section='MOST ACES 1X2 · PAPER ONLY')), 'MOST ACES PAPER')
    def test_unknown_does_not_borrow_paper_record(self):
        self.assertIsNone(primary_label(SimpleNamespace(labels=['UNKNOWN'],section='UNKNOWN')))
