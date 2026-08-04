from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "tennis-evidence-snapshot.py"
SPEC = importlib.util.spec_from_file_location("tennis_evidence_snapshot", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class TennisEvidenceSnapshotTests(unittest.TestCase):
    def test_snapshot_contains_all_hosted_tennis_sections(self) -> None:
        payload = MODULE.build_snapshot()
        self.assertEqual(payload["schema_version"], 1)
        self.assertIn("tennis_model_evidence", payload["sections"])
        self.assertNotIn("lanes", payload["sections"]["tennis_model_evidence"])
        self.assertIn("tennis_props_market_benchmark", payload["sections"])
        self.assertIn("tennis_props_shadow_decision", payload["sections"])

    def test_payload_hash_ignores_generation_time(self) -> None:
        first = MODULE.build_snapshot()
        second = MODULE.build_snapshot()
        self.assertEqual(first["payload_hash"], second["payload_hash"])

    def test_missing_supabase_credentials_fail_closed_without_network(self) -> None:
        with patch.dict(MODULE.os.environ, {}, clear=True), patch.object(
            MODULE.urllib.request, "urlopen"
        ) as urlopen:
            self.assertFalse(MODULE.upload_snapshot("test", {"generated_at": "2026-08-04T00:00:00Z"}))
        urlopen.assert_not_called()

    def test_written_snapshot_is_valid_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "snapshot.json"
            payload = MODULE.build_snapshot()
            MODULE.write_json(output, payload)
            self.assertEqual(MODULE.read_json(output)["payload_hash"], payload["payload_hash"])


if __name__ == "__main__":
    unittest.main()
