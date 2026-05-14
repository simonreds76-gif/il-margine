"""Scaffold for future per-lane tennis calibration fitting.

Phase 0 does not fit or overwrite any calibration artefacts. Later phases will
fill in lane-specific implementations behind this CLI.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lane_registry import PROJECT_ROOT, lane_calibration_path, lane_config, lane_ids, load_lane_config


def _stub_payload(lane_id: str, lane: dict[str, Any]) -> dict[str, Any]:
    return {
        "lane_id": lane_id,
        "method": (lane.get("calibration") or {}).get("method", "none"),
        "phase": "phase0-scaffold",
        "fit_timestamp": datetime.now(timezone.utc).isoformat(),
        "valid": False,
        "reason": "Phase 0 scaffold only; no calibration fitted.",
        "diagnostics": {},
        "fallback_lane": (lane.get("calibration") or {}).get("fallback_lane"),
        "version": "phase0-scaffold",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Fit a tennis research-lane calibration artefact.")
    parser.add_argument("--lane-id", required=True, help="Lane id from data/backtest/lane-config.json")
    parser.add_argument(
        "--write-stub",
        action="store_true",
        help="Write a non-valid scaffold JSON for the selected lane. Phase 0 default is no writes.",
    )
    args = parser.parse_args()

    config = load_lane_config()
    if args.lane_id not in lane_ids(config):
        print(f"unknown lane: {args.lane_id}", file=sys.stderr)
        return 2

    lane = lane_config(args.lane_id, config)
    if lane.get("state") == "disabled":
        print(f"lane disabled: {lane.get('disabled_reason', 'disabled')}", file=sys.stderr)
        return 2

    calibration_path = lane_calibration_path(args.lane_id, config)
    if not calibration_path:
        print(f"lane has no calibration target: {args.lane_id}", file=sys.stderr)
        return 2

    if not args.write_stub:
        print(f"lane {args.lane_id}: Phase 0 scaffold (no calibration fitted)")
        return 0

    target = PROJECT_ROOT / calibration_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(_stub_payload(args.lane_id, lane), indent=2) + "\n", encoding="utf-8")
    print(f"wrote scaffold calibration stub: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
