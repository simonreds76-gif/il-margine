#!/usr/bin/env python3
"""
Build and optionally upload a hosted snapshot of the team-shots monitor files.

This mirrors the goalscorer snapshot pattern so deployed pages can read a stable
hosted payload instead of depending on whichever machine last generated the
files locally.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "data" / "team-shots" / "team-shots-live-snapshot.json"
DEFAULT_SNAPSHOT_KEY = "team_shots_state"
SNAPSHOT_TABLE = "goalscorer_live_snapshot"
SNAPSHOT_FILES = [
    "data/team-shots/team-shots-calibration.txt",
    "data/team-shots/team-shots-calibration-params.json",
    "data/team-shots/team-shots-calibration-diagnostics.txt",
    "data/team-shots/team-shots-backtest-results.csv",
    "data/team-shots/team-shots-backtest-report.txt",
    "data/team-shots/team-shots-predictions.csv",
    "data/team-shots/team-shots-comparison.csv",
    "data/team-shots/team-shots-comparison.txt",
    "data/team-shots/team-shots-odds-history.csv",
    "data/team-shots/team-shots-upcoming.csv",
    "data/team-shots/team-shots-scanner.csv",
    "data/team-shots/team-shots-scrape-last-run.json",
    "data/football-form/research-lane-state.json",
    "data/football-form/research-lane-state.md",
    "data/football-form/team-shots-active-allowed-leagues.json",
    "data/football-form/team-shots-last90-diagnostic.json",
    "data/football-form/team-shots-last90-diagnostic.md",
    "data/football-form/team-shots-v3-ema20-allowed-leagues.json",
    "data/football-form/team-shots-v3-ema20-promotion-check.json",
    "data/football-form/team-shots-v3-ema20-promotion-check.md",
    "data/football-form/team-shots-v3-ema20-published-picks.csv",
    "data/football-form/team-shots-v3-ema20-clv-monitor.csv",
    "data/football-form/team-shots-v3-ema20-clv-monitor.md",
    "data/team-shots/team-shots-v4-params.json",
    "data/team-shots/team-shots-v4-lock.json",
    "data/team-shots/team-shots-v4-fold-results.csv",
    "data/team-shots/team-shots-v4-fold-report.md",
    "data/team-shots/team-shots-v4a-served-fold-results.csv",
    "data/team-shots/team-shots-v4a-served-fold-report.md",
    "data/football-form/team-shots-v4-shadow-config.json",
    "data/football-form/team-shots-v4-shadow-signals.csv",
    "data/football-form/team-shots-v4-shadow-clv.csv",
    "data/football-form/team-shots-v4-shadow-clv.md",
    "data/football-form/team-shots-v4-settlement-audit.json",
    "data/football-form/football-counts-vnext-candidates.csv",
    "data/football-form/football-counts-vnext-gate.json",
    "data/football-form/football-counts-vnext-gate.md",
    "data/football-form/football-count-market-coverage.json",
    "data/football-form/football-count-market-coverage.md",
    "data/football-form/football-foul-market-probe.json",
    "data/football-form/football-foul-market-probe.md",
    "data/football-form/fouls-empirical-baseline.json",
    "data/football-form/fouls-empirical-baseline.md",
    "data/football-form/team-fouls-v1-fold-report.json",
    "data/football-form/team-fouls-v1-fold-report.md",
    "data/football-form/team-fouls-f2-fold-report.json",
    "data/football-form/team-fouls-f2-fold-report.md",
    "data/football-form/team-fouls-definition-agreement.json",
    "data/football-form/team-fouls-definition-agreement.md",
    "data/football-form/team-fouls-fotmob-agreement.json",
    "data/football-form/team-fouls-fotmob-agreement.md",
    "data/football-form/weekly-research-report.json",
    "data/football-form/weekly-research-report.md",
    "data/team-shots/shadow/team-shots-shadow-signals.csv",
    "data/team-shots/shadow/team-shots-shadow-performance.txt",
    "data/team-shots/shadow/settlement-audit.json",
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
        raise SystemExit("Set NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY to upload the team-shots snapshot.")

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
    parser = argparse.ArgumentParser(description="Snapshot team-shots monitor files for hosted page reads")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Local snapshot JSON path")
    parser.add_argument("--snapshot-key", default=DEFAULT_SNAPSHOT_KEY, help="Supabase snapshot_key value")
    parser.add_argument("--supabase", action="store_true", help="Upload snapshot payload to Supabase")
    args = parser.parse_args()

    print("\n" + "=" * 64)
    print("  IL MARGINE - Team Shots Live Snapshot")
    print("=" * 64)

    output_path = Path(args.output)
    previous_payload = read_existing_snapshot(output_path)
    payload = build_snapshot(args.snapshot_key)
    write_snapshot(output_path, payload)

    print(f"  Generated at: {payload['generated_at']}")
    print(f"  Files stored: {payload['file_count']}")
    print(f"  Missing files: {len(payload['missing_files'])}")
    print(f"  Saved: {output_path}")
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
