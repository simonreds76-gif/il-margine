import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))


def load_settler():
    spec = importlib.util.spec_from_file_location("props_settle", SCRIPTS / "tennis-props-settle-shadow.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ScopedHistoryTests(unittest.TestCase):
    def test_scoped_history_matches_full_history_for_either_identity(self):
        settle = load_settler()
        base = dict(event_id="1", date="2026-11-20", tour="ATP", player="First", opponent="Second",
                    market="aces", bookmaker="Book", line="4.5")
        quotes = [base, dict(base, date="2026-11-21"), dict(base,event_id="2"),
                  dict(base, event_id=""), dict(base, line="5.5"), dict(base, bookmaker="Other")]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "observations.csv"
            settle.write_csv(path, quotes)
            full_event, full_pair = settle.load_price_history([path])
            for selected in (base, dict(base,event_id=""), dict(base,event_id="missing")):
                events, pairs = settle.load_price_history([path], [selected])
                event = settle.history_key(selected)
                pair = settle.history_key(selected, fallback=True)
                self.assertEqual(events.get(event), full_event.get(event))
                self.assertEqual(pairs.get(pair), full_pair.get(pair))
                self.assertFalse(set(events) - {event})
                self.assertEqual(set(pairs), {pair})

    def test_interrupted_write_preserves_previous_ledger(self):
        settle = load_settler()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.csv"
            path.write_bytes(b"original")
            with patch.object(settle.csv.DictWriter, "writerow", side_effect=OSError("interrupted")):
                with self.assertRaises(OSError):
                    settle.write_csv(path, [{"signal_id":"1"}])
            self.assertEqual(path.read_bytes(), b"original")
            self.assertEqual(list(path.parent.iterdir()), [path])
