#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "goalscorer"
STATUS_FILE = DATA_DIR / "goalscorer-live-status.json"
SCHEDULE_STATE_FILE = DATA_DIR / "goalscorer-live-schedule-state.json"

LEAGUES = ["serie-a", "epl", "la-liga", "bundesliga", "ligue-1"]
REQUIRED_PLAYER_LOGS = {
    "serie-a": DATA_DIR / "serie-a-player-match-logs-2025-2026.csv",
    "epl": DATA_DIR / "epl-player-match-logs-2025-2026.csv",
    "la-liga": DATA_DIR / "la-liga-player-match-logs-2025-2026.csv",
    "bundesliga": DATA_DIR / "bundesliga-player-match-logs-2025-2026.csv",
    "ligue-1": DATA_DIR / "ligue-1-player-match-logs-2025-2026.csv",
}

FAILURE_COOLDOWN_MINUTES = 60
FAILURE_THRESHOLD = 3
DETAIL_CADENCE_HOT_MINUTES = 60


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def iso_age_minutes(value: str | None) -> float | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None
    return (datetime.now(timezone.utc) - parsed).total_seconds() / 60.0


def run_cmd(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )


def build_default_state(previous: dict[str, Any] | None) -> dict[str, Any]:
    previous_leagues = previous.get("leagues", {}) if isinstance(previous, dict) else {}
    leagues: dict[str, Any] = {}
    for league in LEAGUES:
        existing = previous_leagues.get(league, {}) if isinstance(previous_leagues, dict) else {}
        leagues[league] = {
            "last_successful_run_at": str(existing.get("last_successful_run_at") or ""),
            "last_detail_run_at": str(existing.get("last_detail_run_at") or ""),
            "last_failure_at": str(existing.get("last_failure_at") or ""),
            "consecutive_failures": int(existing.get("consecutive_failures") or 0),
            "last_tier": str(existing.get("last_tier") or ""),
            "last_decision": str(existing.get("last_decision") or ""),
            "last_message": str(existing.get("last_message") or ""),
            "next_kickoff_utc": str(existing.get("next_kickoff_utc") or ""),
        }
    return leagues


def write_status(
    *,
    state: str,
    run_started_at: str,
    last_successful_finished_at: str | None,
    current_league: str,
    warnings: list[str],
    message: str,
    exit_code: int = 0,
) -> None:
    payload = {
        "state": state,
        "updated_at": now_utc_iso(),
        "last_started_at": run_started_at,
        "last_finished_at": None if state == "running" else now_utc_iso(),
        "last_successful_finished_at": last_successful_finished_at,
        "current_league": current_league,
        "bookmaker": "Bet365",
        "leagues": LEAGUES,
        "warnings": warnings,
        "message": message,
        "last_exit_code": exit_code,
    }
    write_json(STATUS_FILE, payload)


def main() -> int:
    run_started_at = now_utc_iso()
    warnings: list[str] = []
    current_league = ""
    previous_status = read_json(STATUS_FILE) or {}
    last_successful_finished_at = str(previous_status.get("last_successful_finished_at") or "") or None
    state = build_default_state(read_json(SCHEDULE_STATE_FILE))

    write_status(
        state="running",
        run_started_at=run_started_at,
        last_successful_finished_at=last_successful_finished_at,
        current_league=current_league,
        warnings=warnings,
        message="Goalscorer live poll started",
    )

    plan_proc = run_cmd([sys.executable, str(ROOT / "scripts" / "goalscorer-live-schedule.py"), "--leagues", ",".join(LEAGUES), "--json"])
    if plan_proc.returncode != 0:
        warnings.append(f"goalscorer-live-schedule failed ({plan_proc.returncode})")
        write_status(
            state="failed",
            run_started_at=run_started_at,
            last_successful_finished_at=last_successful_finished_at,
            current_league="schedule",
            warnings=warnings,
            message=plan_proc.stderr.strip() or plan_proc.stdout.strip() or "schedule plan failed",
            exit_code=plan_proc.returncode,
        )
        return plan_proc.returncode or 1

    plan = json.loads(plan_proc.stdout or "{}")
    plan_lookup = {str(item.get("league")): item for item in plan.get("leagues", [])}
    ran_count = 0
    failed_count = 0

    for league in LEAGUES:
        current_league = league
        entry = state[league]
        plan_entry = plan_lookup.get(league, {})
        tier = str(plan_entry.get("tier") or "off")
        cadence_minutes = int(plan_entry.get("cadence_minutes") or 0)
        active_fixture_count = int(plan_entry.get("active_fixture_count") or 0)
        next_kickoff_utc = str(plan_entry.get("next_kickoff_utc") or "")

        last_success_age = iso_age_minutes(entry.get("last_successful_run_at"))
        last_detail_age = iso_age_minutes(entry.get("last_detail_run_at"))
        last_failure_age = iso_age_minutes(entry.get("last_failure_at"))
        consecutive_failures = int(entry.get("consecutive_failures") or 0)

        if tier == "off" or cadence_minutes <= 0 or active_fixture_count <= 0:
            entry.update({
                "last_tier": tier,
                "last_decision": "off",
                "last_message": f"Skip {league}: no upcoming fixtures inside schedule window.",
                "next_kickoff_utc": next_kickoff_utc,
            })
            continue

        if consecutive_failures >= FAILURE_THRESHOLD and last_failure_age is not None and last_failure_age < FAILURE_COOLDOWN_MINUTES:
            entry.update({
                "last_tier": tier,
                "last_decision": "cooldown",
                "last_message": f"Skip {league}: cooldown active after failures.",
                "next_kickoff_utc": next_kickoff_utc,
            })
            continue

        if last_success_age is not None and last_success_age < cadence_minutes:
            entry.update({
                "last_tier": tier,
                "last_decision": "waiting",
                "last_message": f"Skip {league}: cadence {cadence_minutes}m not due yet.",
                "next_kickoff_utc": next_kickoff_utc,
            })
            continue

        required_log = REQUIRED_PLAYER_LOGS[league]
        if not required_log.exists():
            entry.update({
                "last_tier": tier,
                "last_decision": "missing-data",
                "last_message": f"Skip {league}: player log missing.",
                "next_kickoff_utc": next_kickoff_utc,
            })
            continue

        write_status(
            state="running",
            run_started_at=run_started_at,
            last_successful_finished_at=last_successful_finished_at,
            current_league=league,
            warnings=warnings,
            message=f"Running {league} ({tier} tier)",
        )

        live_args = [
            sys.executable,
            str(ROOT / "scripts" / "run-goalscorer-pipeline.py"),
            "--league", league,
            "--live-only",
            "--fetch-lineups",
            "--lineup-days-ahead", "3",
            "--fetch-odds-api",
            "--odds-api-bookmakers", "Bet365",
            "--bookmaker", "Bet365",
            "--track-shadow",
        ]
        if (
            (os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or os.environ.get("SUPABASE_URL"))
            and (os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY"))
        ):
            live_args.append("--supabase")
        else:
            warnings.append("Goalscorer odds capture is local-only: Supabase credentials are missing.")
        live_proc = run_cmd(live_args)
        if live_proc.returncode != 0:
            failed_count += 1
            entry.update({
                "last_tier": tier,
                "last_decision": "failed",
                "last_message": f"goalscorer live poll failed for {league} (exit {live_proc.returncode})",
                "next_kickoff_utc": next_kickoff_utc,
                "consecutive_failures": consecutive_failures + 1,
                "last_failure_at": now_utc_iso(),
            })
            warnings.append(entry["last_message"])
            continue

        ran_count += 1
        successful_run_at = now_utc_iso()
        detail_run_at = ""
        run_detail_tasks = False
        if tier not in {"lineup", "grace"}:
            run_detail_tasks = not (last_detail_age is not None and last_detail_age < DETAIL_CADENCE_HOT_MINUTES)

        if run_detail_tasks:
            review_proc = run_cmd([sys.executable, str(ROOT / "scripts" / "goalscorer-live-penalty-review.py"), "--league", league, "--days-back", "6"])
            if review_proc.returncode != 0:
                warnings.append(f"same-night penalty review failed for {league} ({review_proc.returncode})")
            baseline_proc = run_cmd([sys.executable, str(ROOT / "scripts" / "build-penalty-baseline-evidence.py"), "--league", league])
            if baseline_proc.returncode != 0:
                warnings.append(f"penalty baseline evidence failed for {league} ({baseline_proc.returncode})")
            if review_proc.returncode == 0 and baseline_proc.returncode == 0:
                detail_run_at = successful_run_at

        entry.update({
            "last_tier": tier,
            "last_decision": "ran",
            "last_message": f"Ran {league} in {tier} tier (cadence {cadence_minutes}m, fixtures {active_fixture_count}).",
            "next_kickoff_utc": next_kickoff_utc,
            "consecutive_failures": 0,
            "last_failure_at": "",
            "last_successful_run_at": successful_run_at,
            "last_detail_run_at": detail_run_at or entry.get("last_detail_run_at", ""),
        })

    schedule_payload = {
        "updated_at": now_utc_iso(),
        "reason": "cycle",
        "leagues": state,
    }
    write_json(SCHEDULE_STATE_FILE, schedule_payload)

    if ran_count > 0:
        clv_args = [sys.executable, str(ROOT / "scripts" / "goalscorer-clv-monitor.py")]
        if (
            (os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or os.environ.get("SUPABASE_URL"))
            and (os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY"))
        ):
            clv_args.append("--supabase")
        clv_proc = run_cmd(clv_args)
        if clv_proc.returncode != 0:
            warnings.append(f"goalscorer CLV monitor failed ({clv_proc.returncode})")

        snapshot_args = [sys.executable, str(ROOT / "scripts" / "goalscorer-live-snapshot.py")]
        supabase_upload_enabled = os.environ.get("ENABLE_SUPABASE_SNAPSHOT_UPLOADS", "0").strip() == "1"
        if (
            supabase_upload_enabled
            and os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
            and os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
        ):
            snapshot_args.append("--supabase")
        snapshot_proc = run_cmd(snapshot_args)
        if snapshot_proc.returncode != 0:
            warnings.append(f"goalscorer live snapshot upload failed ({snapshot_proc.returncode})")
        last_successful_finished_at = now_utc_iso()
        final_state = "warning" if warnings else "idle"
        final_message = (
            f"Goalscorer live poll finished with warnings ({ran_count} ran, {failed_count} failed)."
            if warnings else
            f"Goalscorer live poll finished ({ran_count} league(s) ran)."
        )
        write_status(
            state=final_state,
            run_started_at=run_started_at,
            last_successful_finished_at=last_successful_finished_at,
            current_league="",
            warnings=warnings,
            message=final_message,
        )
        return 0

    if failed_count > 0:
        write_status(
            state="failed",
            run_started_at=run_started_at,
            last_successful_finished_at=last_successful_finished_at,
            current_league="",
            warnings=warnings,
            message=f"Goalscorer live poll failed ({failed_count} league(s) failed, none completed).",
            exit_code=1,
        )
        return 1

    last_successful_finished_at = now_utc_iso()
    write_status(
        state="skipped",
        run_started_at=run_started_at,
        last_successful_finished_at=last_successful_finished_at,
        current_league="",
        warnings=warnings,
        message="Goalscorer live poll skipped: no leagues due in current cadence window.",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
