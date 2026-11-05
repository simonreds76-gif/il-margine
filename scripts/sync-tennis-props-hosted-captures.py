#!/usr/bin/env python3
"""Synchronize hosted tennis-props odds captures into the local checkout.

The GitHub workflow owns Bet365/BetMGM capture. The Windows projection pipeline owns
the OnCourt-backed board and comparison. This script joins those two halves
without making another provider request or touching the active git branch.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import subprocess
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
INBOX = ROOT / "data" / "tennis-props" / "inbox"
DEFAULT_REMOTE_REF = "origin/golden-with-speed-insights"
STATUS_PATH = ROOT / "data" / "tennis-props" / "hosted-capture-sync-status.json"


def git_command(args: list[str], *, timeout: int = 60) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )


def fetch_remote() -> tuple[bool, str]:
    result = git_command(["fetch", "origin", "golden-with-speed-insights"], timeout=90)
    detail = result.stderr.decode("utf-8", errors="replace").strip()
    return result.returncode == 0, detail


def remote_blob(remote_ref: str, relative_path: str) -> bytes | None:
    result = git_command(["show", f"{remote_ref}:{relative_path}"])
    return result.stdout if result.returncode == 0 and result.stdout else None


def csv_rows(content: bytes) -> tuple[list[str], list[dict[str, str]]]:
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    return list(reader.fieldnames or []), [dict(row) for row in reader]


def latest_capture(rows: list[dict[str, str]]) -> str:
    return max(
        (
            str(row.get("capture_ts") or row.get("captured_at") or "")
            for row in rows
        ),
        default="",
    )


def should_replace(local_path: Path, remote_content: bytes) -> bool:
    if not local_path.exists():
        return True
    try:
        _, remote_rows = csv_rows(remote_content)
        _, local_rows = csv_rows(local_path.read_bytes())
    except (OSError, csv.Error, UnicodeError):
        return True
    remote_stamp = latest_capture(remote_rows)
    local_stamp = latest_capture(local_rows)
    return remote_stamp > local_stamp or (
        remote_stamp == local_stamp and len(remote_rows) > len(local_rows)
    )


def write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def merge_history(local_path: Path, remote_content: bytes) -> int:
    remote_fields, remote_rows = csv_rows(remote_content)
    if not remote_fields:
        return 0
    local_rows: list[dict[str, str]] = []
    fields = remote_fields
    if local_path.exists():
        local_fields, local_rows = csv_rows(local_path.read_bytes())
        if local_fields:
            fields = list(dict.fromkeys([*local_fields, *remote_fields]))

    def key(row: dict[str, str]) -> tuple[str, ...]:
        return tuple(str(row.get(field) or "").strip() for field in fields)

    seen = {key(row) for row in local_rows}
    added = 0
    for row in remote_rows:
        row_key = key(row)
        if row_key in seen:
            continue
        seen.add(row_key)
        local_rows.append(row)
        added += 1
    if not added and local_path.exists():
        return 0

    local_path.parent.mkdir(parents=True, exist_ok=True)
    with local_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(local_rows)
    return added


def sync_match_shape_quotes(remote_ref, target_date, lookback_days):
    """Import exact immutable cloud observations; never manufacture forecasts."""
    from tennis_match_shape_quotes import RELATIVE, digest
    prefix=str(RELATIVE/'cloud-quotes').replace('\\','/')
    result=git_command(['ls-tree','-r','--name-only',remote_ref,'--',prefix])
    if result.returncode:raise RuntimeError('match_shape_cloud_listing_failed')
    days={(target_date-timedelta(days=n)).isoformat() for n in range(min(7,max(0,lookback_days))+1)}
    paths=[p for p in result.stdout.decode().splitlines() if len(Path(p).parts)==6 and Path(p).parts[-2] in days and Path(p).suffix=='.json']
    if len(paths)>128:raise RuntimeError('match_shape_cloud_quote_budget_exceeded')
    added=0
    for relative in sorted(paths):
        raw=remote_blob(remote_ref,relative)
        if not raw or len(raw)>8*1024*1024:raise ValueError('invalid_match_shape_cloud_packet_size')
        packet=json.loads(raw)
        if digest(packet)!=Path(relative).stem or not isinstance(packet.get('events'),list):raise ValueError('invalid_match_shape_cloud_packet_hash')
        dest=ROOT/RELATIVE/'quote-evidence'/Path(relative).name
        if dest.exists():
            if json.loads(dest.read_text(encoding='utf-8'))!=packet:raise ValueError('immutable_match_shape_quote_conflict')
            continue
        dest.parent.mkdir(parents=True,exist_ok=True)
        with dest.open('xb') as stream:stream.write(raw)
        added+=1
    status=remote_blob(remote_ref,str(RELATIVE/'cloud-capture-status.json').replace('\\','/'))
    if status:
        value=json.loads(status)
        if value.get('forecasts_created')!=0 or value.get('settlements_created')!=0:raise ValueError('invalid_cloud_execution_scope')
        old=ROOT/RELATIVE/'cloud-capture-status.json'
        previous=json.loads(old.read_text()) if old.exists() else {}
        if value.get('checked_at','')>previous.get('checked_at',''):write_bytes(old,status)
    return {'imported_packets':added,'available_packets':len(paths)}


def synchronize(
    as_of: str,
    *,
    remote_ref: str = DEFAULT_REMOTE_REF,
    lookback_days: int = 7,
) -> dict[str, object]:
    target_date = date.fromisoformat(as_of)
    copied: list[str] = []
    missing: list[str] = []
    history_added = 0

    for offset in range(max(0, lookback_days) + 1):
        day = (target_date - timedelta(days=offset)).isoformat()
        for stem in (
            "bet365-lines",
            "bet365-tennis-market-audit",
            "betmgm-most-aces-1x2",
            "most-df-1x2",
            "betmgm-tennis-market-audit",
        ):
            relative = f"data/tennis-props/inbox/{stem}-{day}.csv"
            content = remote_blob(remote_ref, relative)
            if content is None:
                missing.append(relative)
                continue
            target = ROOT / relative
            if should_replace(target, content):
                write_bytes(target, content)
                copied.append(relative)

    months = {
        (target_date - timedelta(days=offset)).strftime("%Y-%m")
        for offset in range(max(0, lookback_days) + 1)
    }
    for month in sorted(months):
        for stem in ("bet365-lines-history", "betmgm-most-aces-history", "most-df-history"):
            relative = f"data/tennis-props/inbox/{stem}-{month}.csv"
            content = remote_blob(remote_ref, relative)
            if content is None:
                missing.append(relative)
                continue
            added = merge_history(ROOT / relative, content)
            history_added += added
            if added:
                copied.append(relative)

    shape_sync = sync_match_shape_quotes(remote_ref, target_date, lookback_days)
    return {
        "match_shape": shape_sync,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "as_of": as_of,
        "remote_ref": remote_ref,
        "lookback_days": lookback_days,
        "copied_files": copied,
        "missing_remote_files": missing,
        "history_rows_added": history_added,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync hosted Bet365 tennis-props captures without API calls")
    parser.add_argument("--as-of", default=date.today().isoformat())
    parser.add_argument("--remote-ref", default=DEFAULT_REMOTE_REF)
    parser.add_argument("--lookback-days", type=int, default=7)
    parser.add_argument("--no-fetch", action="store_true")
    parser.add_argument("--status", default=str(STATUS_PATH))
    args = parser.parse_args()

    fetch_ok = True
    fetch_detail = ""
    if not args.no_fetch:
        fetch_ok, fetch_detail = fetch_remote()
        if not fetch_ok:
            print(f"WARNING: hosted capture fetch failed; using existing remote ref: {fetch_detail}")

    payload = synchronize(
        args.as_of,
        remote_ref=args.remote_ref,
        lookback_days=args.lookback_days,
    )
    payload["fetch_ok"] = fetch_ok
    payload["fetch_detail"] = fetch_detail
    status_path = Path(args.status)
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print(
        "Hosted tennis-props sync: "
        f"copied={len(payload['copied_files'])}, "
        f"history_added={payload['history_rows_added']}, "
        f"missing={len(payload['missing_remote_files'])}"
    )
    return 0 if fetch_ok or payload["copied_files"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
