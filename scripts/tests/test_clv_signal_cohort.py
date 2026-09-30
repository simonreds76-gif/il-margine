import importlib.util
import sys
import unittest
from datetime import date
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("audit_strict_clv_cohort", SCRIPTS / "audit-strict-clv.py")
audit = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = audit
spec.loader.exec_module(audit)


class SignalCohortTests(unittest.TestCase):
    def test_policy_boundary_excludes_legacy_overlay_and_unknown_dates(self):
        rows = [
            {"date": "2026-05-26", "policy_mode": "base"},
            {"date": "2026-05-27", "policy_mode": "base"},
            {"date": "2026-05-28", "policy_mode": "overlay"},
            {"date": "2026-05-29", "policy_mode": ""},
            {"date": "bad-date", "policy_mode": "base"},
        ]
        self.assertEqual(audit.filter_signal_cohort(rows, date(2026, 5, 27), "base"), [rows[1], rows[3]])

    def test_default_preserves_all_rows(self):
        rows = [{"date": ""}, {"date": "2026-01-01", "policy_mode": "overlay"}]
        self.assertEqual(audit.filter_signal_cohort(rows), rows)

    def test_overlay_selection_does_not_include_blank_base(self):
        rows = [{"policy_mode": ""}, {"policy_mode": "overlay"}]
        self.assertEqual(audit.filter_signal_cohort(rows, policy_mode="overlay"), [rows[1]])


if __name__ == "__main__":
    unittest.main()
