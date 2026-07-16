from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PAGE = (ROOT / "src" / "app" / "model-monitor" / "assist-value" / "page.tsx").read_text(encoding="utf-8")
MONITOR = (ROOT / "src" / "app" / "model-monitor" / "page.tsx").read_text(encoding="utf-8")
SYNC = (ROOT / "scripts" / "sync-hosted-monitor-data.ps1").read_text(encoding="utf-8")
DEV_SYNC = (ROOT / "scripts" / "dev-with-hosted-sync.mjs").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github" / "workflows" / "assist-value-shadow.yml").read_text(encoding="utf-8")


class AssistLaneFrozenTests(unittest.TestCase):
    def test_monitor_is_an_archive_not_a_signal_board(self) -> None:
        self.assertIn("Assist Value Research Archive", PAGE)
        self.assertIn("Frozen lane, not a betting product", PAGE)
        self.assertIn("No current candidates, P/L chart or ROI panel", PAGE)
        self.assertNotIn('title="Assist Value Signals"', PAGE)
        self.assertNotIn('title="League P/L"', PAGE)

    def test_default_hosted_sync_skips_assist(self) -> None:
        self.assertIn("$includeAssistValue = $AssistValue", SYNC)
        self.assertNotIn("$includeAssistValue = $syncAll -or $AssistValue", SYNC)
        self.assertNotIn('"-AssistValue"', DEV_SYNC)

    def test_workflow_is_manual_and_fail_closed(self) -> None:
        self.assertIn("workflow_dispatch:", WORKFLOW)
        self.assertNotIn("schedule:", WORKFLOW)
        self.assertIn("vars.ASSIST_VALUE_SHADOW_ENABLED == '1'", WORKFLOW)

    def test_monitor_index_labels_lane_paused(self) -> None:
        self.assertIn("Assist Research Archive", MONITOR)
        self.assertIn(">Paused</span>", MONITOR)


if __name__ == "__main__":
    unittest.main()
