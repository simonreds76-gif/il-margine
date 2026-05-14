#!/usr/bin/env python3
"""
Build and optionally upload a hosted snapshot of the live goalscorer files.

This keeps the deployed pages close to the local machine output without
rewriting the existing parsers. We snapshot the current CSV/TXT/JSON files into
one JSON blob and upsert that blob to Supabase.

Examples:
  python scripts/goalscorer-live-snapshot.py
  python scripts/goalscorer-live-snapshot.py --supabase
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
DEFAULT_OUTPUT = ROOT / "data" / "goalscorer" / "goalscorer-live-snapshot.json"
DEFAULT_SNAPSHOT_KEY = "live_state"
SNAPSHOT_FILES = [
    "data/goalscorer/goalscorer-shadow-signals.csv",
    "data/goalscorer/goalscorer-public-signals.csv",
    "data/goalscorer/goalscorer-live-status.json",
    "data/goalscorer/goalscorer-live-schedule-state.json",
    "data/goalscorer/goalscorer-live.log",
    "data/goalscorer/epl-shadow-signals.csv",
    "data/goalscorer/epl-public-signals.csv",
    "data/goalscorer/la-liga-shadow-signals.csv",
    "data/goalscorer/la-liga-public-signals.csv",
    "data/goalscorer/bundesliga-shadow-signals.csv",
    "data/goalscorer/bundesliga-public-signals.csv",
    "data/goalscorer/ligue-1-shadow-signals.csv",
    "data/goalscorer/ligue-1-public-signals.csv",
    "data/goalscorer/penalty-duty-review.json",
    "data/goalscorer/penalty-duty-live-review.json",
    "data/goalscorer/epl-penalty-duty-review.json",
    "data/goalscorer/epl-penalty-duty-live-review.json",
    "data/goalscorer/la-liga-penalty-duty-review.json",
    "data/goalscorer/la-liga-penalty-duty-live-review.json",
    "data/goalscorer/bundesliga-penalty-duty-review.json",
    "data/goalscorer/bundesliga-penalty-duty-live-review.json",
    "data/goalscorer/ligue-1-penalty-duty-review.json",
    "data/goalscorer/ligue-1-penalty-duty-live-review.json",
    "data/goalscorer/live-board.json",
    "data/goalscorer/goalscorer-live-comparison.csv",
    "data/goalscorer/goalscorer-live-comparison.txt",
    "data/goalscorer/confirmed-lineups.json",
    "data/goalscorer/epl/live-board.json",
    "data/goalscorer/epl/goalscorer-live-comparison.csv",
    "data/goalscorer/epl/goalscorer-live-comparison.txt",
    "data/goalscorer/epl-confirmed-lineups.json",
    "data/goalscorer/la-liga/live-board.json",
    "data/goalscorer/la-liga/goalscorer-live-comparison.csv",
    "data/goalscorer/la-liga/goalscorer-live-comparison.txt",
    "data/goalscorer/la-liga-confirmed-lineups.json",
    "data/goalscorer/bundesliga/live-board.json",
    "data/goalscorer/bundesliga/goalscorer-live-comparison.csv",
    "data/goalscorer/bundesliga/goalscorer-live-comparison.txt",
    "data/goalscorer/bundesliga-confirmed-lineups.json",
    "data/goalscorer/ligue-1/live-board.json",
    "data/goalscorer/ligue-1/goalscorer-live-comparison.csv",
    "data/goalscorer/ligue-1/goalscorer-live-comparison.txt",
    "data/goalscorer/ligue-1-confirmed-lineups.json",
]

META_ONLY_FILES = {
    "data/goalscorer/goalscorer-live.log",
}


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


def build_snapshot() -> Dict[str, object]:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    files: Dict[str, Dict[str, object]] = {}
    missing: list[str] = []

    for rel_path in SNAPSHOT_FILES:
        abs_path = ROOT / rel_path
        if not abs_path.exists():
            missing.append(rel_path)
            continue
        stat = abs_path.stat()
        entry = {
            "mtime": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "size_bytes": stat.st_size,
        }
        if rel_path not in META_ONLY_FILES:
            entry["content"] = abs_path.read_text(encoding="utf-8", errors="replace")
        files[rel_path] = entry

    hashed_payload = {
        "file_count": len(files),
        "missing_files": missing,
        "files": files,
    }
    payload_hash = hashlib.sha256(
        json.dumps(hashed_payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()

    return {
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
        raise SystemExit("Set NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY to upload the live snapshot.")

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
    url = f"{base}/rest/v1/goalscorer_live_snapshot?on_conflict=snapshot_key"
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
    parser = argparse.ArgumentParser(description="Snapshot live goalscorer files for hosted page reads")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Local snapshot JSON path")
    parser.add_argument("--snapshot-key", default=DEFAULT_SNAPSHOT_KEY, help="Supabase snapshot_key value")
    parser.add_argument("--supabase", action="store_true", help="Upload snapshot payload to Supabase")
    args = parser.parse_args()

    print("\n" + "=" * 64)
    print("  IL MARGINE - Goalscorer Live Snapshot")
    print("=" * 64)

    output_path = Path(args.output)
    previous_payload = read_existing_snapshot(output_path)
    payload = build_snapshot()
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
            print(f"  Uploaded snapshot '{args.snapshot_key}' to goalscorer_live_snapshot")

    print("\n  Done.\n")


if __name__ == "__main__":
    main()
