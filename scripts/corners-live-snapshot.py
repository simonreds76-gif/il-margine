#!/usr/bin/env python3
"""
Build and optionally upload a hosted snapshot of the corners monitor files.

This keeps corners shortlist/CLV data readable by deployed pages without
depending on the local machine's file state.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "data" / "corners-ou" / "corners-live-snapshot.json"
SUMMARY_OUTPUT = ROOT / "data" / "corners-ou" / "corners-monitor-summary.json"
DEFAULT_SNAPSHOT_KEY = "corners_state"
SNAPSHOT_TABLE = "goalscorer_live_snapshot"
PREDICTIONS_FILE = ROOT / "data" / "corners-ou" / "corners-ou-predictions.csv"
RECENT_PREDICTION_LIMIT = 80
SNAPSHOT_FILES = [
    "data/corners-ou/corners-ou-calibration.txt",
    "data/corners-ou/corners-calibration-params.json",
    "data/corners-ou/corners-ou-backtest-report.txt",
    "data/corners-ou/corners-ou-backtest-results.csv",
    "data/corners-ou/corners-ou-predictions.csv",
    "data/corners-ou/corners-monitor-summary.json",
    "data/corners-ou/pinnacle-corners-odds.csv",
    "data/football-form/research-lane-state.json",
    "data/football-form/research-lane-state.md",
    "data/football-form/corners-v0-allowed-leagues.json",
    "data/football-form/corners-v0-promotion-check.json",
    "data/football-form/corners-v0-promotion-check.md",
    "data/football-form/corners-v0-published-picks.csv",
    "data/football-form/corners-v0-clv-monitor.csv",
    "data/football-form/corners-v0-clv-monitor.md",
    "data/corners-ou/corners-v3-params.json",
    "data/corners-ou/corners-v3-lock.json",
    "data/corners-ou/corners-v3-fold-report.md",
    "data/corners-ou/corners-v4-g0-fold-results.csv",
    "data/corners-ou/corners-v4-g0-diagnostic.json",
    "data/corners-ou/corners-v4-g0-diagnostic.md",
    "data/football-form/corners-v3-shadow-config.json",
    "data/football-form/corners-v3-shadow-signals.csv",
    "data/football-form/corners-v3-shadow-clv.csv",
    "data/football-form/corners-v3-shadow-clv.md",
    "data/football-form/corners-v3-settlement-audit.json",
    "data/football-form/football-counts-vnext-candidates.csv",
    "data/football-form/football-counts-vnext-gate.json",
    "data/football-form/football-counts-vnext-gate.md",
    "data/football-form/corners-total-diagnostic.json",
    "data/football-form/corners-total-diagnostic.md",
    "data/football-form/weekly-research-report.json",
    "data/football-form/weekly-research-report.md",
    "data/shortlist/shortlist-latest.txt",
    "data/shortlist/shortlist-latest-v31.txt",
    "data/shortlist/value-bets-latest.csv",
    "data/shortlist/value-bets-latest-v31.csv",
    "data/shortlist/signals-latest.csv",
    "data/shortlist/signals-latest-v31.csv",
    "data/shortlist/settled-pnl.csv",
    "data/shortlist/corners-live-pnl.txt",
    "data/shortlist/settlement-audit.json",
    "data/shortlist/team-props-status.json",
]


def load_env() -> None:
    for name in (".env.local", "env.local"):
        path = ROOT / name
        if not path.exists():
            continue
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ[key.strip()] = value.strip().strip('"').strip("'")


def build_snapshot(snapshot_key: str) -> Dict[str, object]:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    files: Dict[str, Dict[str, object]] = {}
    missing: list[str] = []

    for rel_path in SNAPSHOT_FILES:
        abs_path = ROOT / rel_path
        if not abs_path.exists():
            missing.append(rel_path)
            continue
        text = abs_path.read_text(encoding="utf-8", errors="replace")
        stat = abs_path.stat()
        files[rel_path] = {
            "content": text,
            "mtime": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "size_bytes": stat.st_size,
        }

    hashed_payload = {
        "file_count": len(files),
        "missing_files": missing,
        "files": files,
    }
    payload_hash = hashlib.sha256(
        json.dumps(hashed_payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()

    return {
        "snapshot_key": snapshot_key,
        "generated_at": generated_at,
        "file_count": len(files),
        "missing_files": missing,
        "files": files,
        "payload_hash": payload_hash,
    }


def write_snapshot(path: Path, payload: Dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def build_predictions_summary() -> Dict[str, object]:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    source_file = str(PREDICTIONS_FILE.relative_to(ROOT)).replace("\\", "/")
    if not PREDICTIONS_FILE.exists():
        return {
            "generated_at": generated_at,
            "prediction_count": 0,
            "recent_predictions": [],
            "source_file": source_file,
            "source_mtime": None,
        }

    recent_rows: deque[dict[str, str]] = deque(maxlen=RECENT_PREDICTION_LIMIT)
    prediction_count = 0
    with PREDICTIONS_FILE.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            prediction_count += 1
            recent_rows.append({key: (value or "") for key, value in row.items()})

    stat = PREDICTIONS_FILE.stat()
    return {
        "generated_at": generated_at,
        "prediction_count": prediction_count,
        "recent_predictions": list(reversed(recent_rows)),
        "source_file": source_file,
        "source_mtime": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }


def read_existing_snapshot(path: Path) -> Dict[str, object] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def upload_snapshot(snapshot_key: str, payload: Dict[str, object]) -> None:
    import requests

    load_env()
    base = (os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or os.environ.get("SUPABASE_URL") or "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
    if not base or not key:
        raise SystemExit("Set NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY to upload the corners snapshot.")

    row = {
        "snapshot_key": snapshot_key,
        "updated_at": payload["generated_at"],
        "payload": payload,
    }
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=representation",
    }
    url = f"{base}/rest/v1/{SNAPSHOT_TABLE}?on_conflict=snapshot_key"
    attempts = max(1, int(os.environ.get("SUPABASE_SNAPSHOT_UPLOAD_ATTEMPTS", "3") or "3"))
    read_timeout = max(10, int(os.environ.get("SUPABASE_SNAPSHOT_UPLOAD_TIMEOUT", "45") or "45"))
    required = (os.environ.get("SUPABASE_SNAPSHOT_UPLOAD_REQUIRED", "0") or "0").strip().lower() in {
        "1",
        "true",
        "yes",
    }

    last_error = ""
    for attempt in range(1, attempts + 1):
        try:
            response = requests.post(url, headers=headers, json=[row], timeout=(10, read_timeout))
        except requests.exceptions.RequestException as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        else:
            if response.ok:
                return
            if 400 <= response.status_code < 500 and response.status_code != 429:
                raise SystemExit(f"Supabase upload failed: {response.status_code} {response.text[:400]}")
            last_error = f"{response.status_code} {response.text[:400]}"

        if attempt < attempts:
            sleep_seconds = min(2 ** attempt, 10)
            print(f"  Supabase upload attempt {attempt}/{attempts} failed: {last_error}; retrying in {sleep_seconds}s")
            time.sleep(sleep_seconds)

    message = f"Supabase upload failed after {attempts} attempt(s): {last_error}"
    if required:
        raise SystemExit(message)
    print(f"  WARNING: {message}; continuing because SUPABASE_SNAPSHOT_UPLOAD_REQUIRED is not enabled")


def main() -> None:
    parser = argparse.ArgumentParser(description="Snapshot corners monitor files for hosted page reads")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Local snapshot JSON path")
    parser.add_argument("--snapshot-key", default=DEFAULT_SNAPSHOT_KEY, help="Supabase snapshot_key value")
    parser.add_argument("--supabase", action="store_true", help="Upload snapshot payload to Supabase")
    args = parser.parse_args()

    print("\n" + "=" * 64)
    print("  IL MARGINE - Corners Live Snapshot")
    print("=" * 64)

    output_path = Path(args.output)
    previous_payload = read_existing_snapshot(output_path)
    write_snapshot(SUMMARY_OUTPUT, build_predictions_summary())
    payload = build_snapshot(args.snapshot_key)
    write_snapshot(output_path, payload)

    print(f"  Generated at: {payload['generated_at']}")
    print(f"  Files stored: {payload['file_count']}")
    print(f"  Missing files: {len(payload['missing_files'])}")
    print(f"  Saved: {output_path}")
    print(f"  Summary: {SUMMARY_OUTPUT}")
    unchanged = bool(previous_payload) and previous_payload.get("payload_hash") == payload.get("payload_hash")
    if unchanged:
        print("  Snapshot payload unchanged")

    if args.supabase:
        if unchanged:
            print(f"  Skipped Supabase upload for snapshot '{args.snapshot_key}' (unchanged payload)")
        else:
            upload_snapshot(args.snapshot_key, payload)
            print(f"  Uploaded snapshot '{args.snapshot_key}' to {SNAPSHOT_TABLE}")

    print("\n  Done.\n")


if __name__ == "__main__":
    main()
