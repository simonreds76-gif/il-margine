#!/usr/bin/env python3
"""Persist one compact snapshot of local tennis evidence for hosted reports.

The Windows tennis pipelines own the prospective ledgers. GitHub's weekly
runner cannot see ignored local CSVs, so treating missing files as zero creates
false reports. This script summarizes those ledgers once and upserts one row;
it never uploads raw match histories and skips unchanged payloads.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT_SCRIPT = ROOT / "scripts" / "weekly-research-report.py"
DEFAULT_OUTPUT = ROOT / "data" / "tennis-props" / "tennis-evidence-snapshot.json"
DEFAULT_SNAPSHOT_KEY = "tennis_evidence_v1"
SNAPSHOT_TABLE = "goalscorer_live_snapshot"
SCHEMA_VERSION = 2
VOLATILE_HASH_KEYS = {"age_days", "checked_at", "created_at", "generated_at", "updated_at"}


def load_env_files() -> None:
    for name in (".env.local", "env.local"):
        path = ROOT / name
        if not path.exists():
            continue
        for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_report_module() -> Any:
    spec = importlib.util.spec_from_file_location("weekly_research_report_snapshot", REPORT_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {REPORT_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def source_metadata(module: Any) -> dict[str, dict[str, Any]]:
    paths = {
        "gap_report": module.TENNIS_GAP_REPORT,
        "props_v3": module.TENNIS_PROPS_V3_LOCAL_JSON,
        "props_v4": module.TENNIS_PROPS_V4_JSON,
        "market_observations": module.TENNIS_PROPS_OBSERVATIONS,
        "shadow_signals": module.TENNIS_PROPS_SHADOW_SIGNALS,
        "pipeline_health": module.TENNIS_PROPS_PIPELINE_HEALTH,
        "venue_factors": module.TENNIS_VENUE_ACE_FACTORS,
        "venue_observations": module.TENNIS_VENUE_ACE_V1_OBSERVATIONS,
        "most_aces_forecast": module.TENNIS_MOST_ACES_FORECAST_JSON,
        "most_aces_observations": module.TENNIS_MOST_ACES_OBSERVATIONS,
    }
    paths.update(
        {f"lane_{name}": path for name, path in module.TENNIS_LANE_FILES.items()}
    )
    paths.update(
        {f"lane_clv_{name}": path for name, path in module.TENNIS_CLV_FILES.items()}
    )
    output: dict[str, dict[str, Any]] = {}
    for name, path in paths.items():
        exists = path.exists()
        output[name] = {
            "path": module.display_path(path),
            "exists": exists,
            "size_bytes": path.stat().st_size if exists else 0,
            "modified_at": (
                datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
                .replace(microsecond=0)
                .isoformat()
                .replace("+00:00", "Z")
                if exists
                else ""
            ),
        }
    return output


def stable_hash_value(value: Any) -> Any:
    """Remove wall-clock fields while retaining every evidence value and source mtime."""
    if isinstance(value, dict):
        return {
            key: stable_hash_value(item)
            for key, item in value.items()
            if key not in VOLATILE_HASH_KEYS
        }
    if isinstance(value, list):
        return [stable_hash_value(item) for item in value]
    return value


def build_snapshot() -> dict[str, Any]:
    module = load_report_module()
    tennis_model_evidence = module.tennis_model_evidence_summary()
    sections = {
        "tennis_ml_gap_guard": module.ml_gap_guard_summary(),
        # The Windows pipeline owns the current lane ledgers. Hosted copies can
        # lag for months, so transport their compact summaries with the other
        # local evidence instead of reconstructing them on GitHub.
        "tennis_model_evidence": tennis_model_evidence,
        "tennis_props_v3": module.tennis_props_v3_snapshot(),
        "tennis_rate_trend": module.rate_trend_summary(),
        "tennis_props_v4": module.load_json(module.TENNIS_PROPS_V4_JSON),
        "tennis_venue_ace_factor_v1": module.venue_ace_factor_v1_summary(),
        "tennis_most_aces_forecast": module.load_json(module.TENNIS_MOST_ACES_FORECAST_JSON),
        "tennis_most_aces_prices": module.most_aces_price_summary(),
        "tennis_props_market_benchmark": module.tennis_props_market_benchmark(),
        "tennis_props_shadow_decision": module.tennis_props_shadow_decision(),
    }
    stable = {
        "schema_version": SCHEMA_VERSION,
        "source": "windows_local_tennis_pipeline",
        "source_files": source_metadata(module),
        "sections": sections,
    }
    payload_hash = hashlib.sha256(
        json.dumps(stable_hash_value(stable), ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return {
        **stable,
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "payload_hash": payload_hash,
    }


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def upload_snapshot(snapshot_key: str, payload: dict[str, Any]) -> bool:
    load_env_files()
    base = (os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or os.environ.get("SUPABASE_URL") or "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY") or ""
    if not base or not key:
        print("WARNING: tennis evidence snapshot upload skipped; Supabase credentials are missing.")
        return False

    body = json.dumps(
        [
            {
                "snapshot_key": snapshot_key,
                "updated_at": payload["generated_at"],
                "payload": payload,
            }
        ]
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{base}/rest/v1/{SNAPSHOT_TABLE}?on_conflict=snapshot_key",
        data=body,
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=minimal",
        },
        method="POST",
    )
    error = ""
    for attempt in range(1, 4):
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                response.read()
            return True
        except urllib.error.HTTPError as exc:
            error = f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')[:300]}"
            if 400 <= exc.code < 500 and exc.code != 429:
                break
        except (urllib.error.URLError, TimeoutError) as exc:
            error = str(exc)
        if attempt < 3:
            time.sleep(2**attempt)
    print(f"WARNING: tennis evidence snapshot upload failed after retries: {error}")
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--snapshot-key", default=DEFAULT_SNAPSHOT_KEY)
    parser.add_argument("--supabase", action="store_true")
    args = parser.parse_args()

    output = Path(args.output)
    previous = read_json(output)
    payload = build_snapshot()
    write_json(output, payload)
    unchanged = previous.get("payload_hash") == payload.get("payload_hash")
    print(
        f"Tennis evidence snapshot: {len(payload['sections'])} sections, "
        f"hash={payload['payload_hash'][:12]}, unchanged={str(unchanged).lower()}"
    )
    if args.supabase:
        if unchanged:
            print("Supabase upload skipped: evidence payload is unchanged.")
        elif upload_snapshot(args.snapshot_key, payload):
            print(f"Uploaded tennis evidence snapshot '{args.snapshot_key}'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
