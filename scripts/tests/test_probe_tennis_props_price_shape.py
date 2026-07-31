from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]
MODULE_PATH = SCRIPTS / "probe-tennis-props-price-shape.py"
SPEC = importlib.util.spec_from_file_location("probe_tennis_props_price_shape", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Cannot load {MODULE_PATH}")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class FakeResponse:
    status_code = 200

    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def json(self) -> dict:
        return self.payload


class PriceShapeProbeTests(unittest.TestCase):
    def test_selects_first_forward_dated_prop_event(self) -> None:
        rows = [
            {"event_id": "old", "date": "2026-07-30", "market": "aces"},
            {"event_id": "future", "date": "2026-08-01", "market": "double_faults"},
            {"event_id": "today", "date": "2026-07-31", "market": "aces"},
        ]
        self.assertEqual(MODULE.select_event_id(rows, "2026-07-31"), "today")

    def test_probe_is_exactly_three_requests_and_output_is_sanitized(self) -> None:
        calls: list[dict] = []
        payload = {
            "bookmakers": {
                "Bet365": [
                    {
                        "name": "Totals (Aces)",
                        "odds": [
                            {"hdp": 10.5, "over": "1.80", "under": "1.90"},
                            {"hdp": 11.5, "over": "2.10"},
                        ],
                    }
                ]
            }
        }

        def requester(url: str, *, params: dict, timeout: int) -> FakeResponse:
            calls.append({"url": url, "params": dict(params), "timeout": timeout})
            return FakeResponse(payload)

        result = MODULE.run_probe("secret-value", "event-1", requester=requester)
        self.assertEqual(len(calls), 3)
        self.assertEqual(result["request_count"], 3)
        self.assertEqual(result["results"][0]["two_way_rungs"], 1)
        self.assertEqual(result["results"][0]["over_only_rungs"], 1)
        serialized = json.dumps(result)
        self.assertNotIn("secret-value", serialized)
        self.assertNotIn("apiKey", serialized)

    def test_summary_handles_list_payload(self) -> None:
        summary = MODULE.summarize_payload(
            [
                {
                    "bookmakers": {
                        "Bet365": [
                            {
                                "name": "Team Total (Double Faults) Home",
                                "odds": [{"hdp": 2.5, "over": "2.00"}],
                            }
                        ]
                    }
                }
            ]
        )
        self.assertEqual(summary["ace_df_markets"], 1)
        self.assertEqual(summary["over_only_rungs"], 1)


if __name__ == "__main__":
    unittest.main()
