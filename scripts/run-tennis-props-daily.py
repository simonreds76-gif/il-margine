#!/usr/bin/env python3
"""Refresh the tennis aces/double-fault research board.

This is intentionally local-first because the match schedule comes from the
OnCourt MDB export. If an odds-api.io key is available locally, the script also
captures Bet365 aces/DF lines and writes the comparison file.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from model_lifecycle import most_aces_suspended
from tennis_pairing_consistency import ensure_props_board, verify_derived_board


ROOT = Path(__file__).resolve().parent.parent
PROPS_DIR = ROOT / "data" / "tennis-props"
MOST_ACES_DIRECT_BOARD = PROPS_DIR / "shadow" / "most-aces-direct-1x2-board.csv"
VENUE_ACE_V1_BOARD = PROPS_DIR / "shadow" / "venue-ace-factor-v1-projection-board.csv"


def load_env() -> None:
    for name in (".env.local", "env.local"):
        path = ROOT / name
        if not path.exists():
            continue
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            raw_line = raw_line.strip()
            if raw_line and not raw_line.startswith("#") and "=" in raw_line:
                key, value = raw_line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def run(
    cmd: list[str],
    label: str,
    *,
    fatal: bool = True,
    timeout_seconds: int | None = None,
) -> int:
    print(f"\n=== {label} ===")
    try:
        result = subprocess.run(cmd, cwd=str(ROOT), timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        msg = f"{label} timed out after {timeout_seconds}s"
        if fatal:
            raise SystemExit(msg)
        print(f"WARNING: {msg}")
        return 124
    if result.returncode != 0:
        msg = f"{label} failed with exit {result.returncode}"
        if fatal:
            raise SystemExit(msg)
        print(f"WARNING: {msg}")
    return result.returncode


def has_odds_key() -> bool:
    return bool(os.environ.get("ODDS_API_KEY") or os.environ.get("ODDS_API_IO_KEY"))


def lines_file(as_of: str) -> Path:
    return PROPS_DIR / "inbox" / f"bet365-lines-{as_of}.csv"


def betsbk_lines_file(as_of: str) -> Path:
    return PROPS_DIR / "inbox" / f"betsbk-lines-{as_of}.csv"


def combined_lines_file(as_of: str) -> Path:
    return PROPS_DIR / "inbox" / f"tennis-props-lines-{as_of}.csv"


def most_aces_lines_file(as_of: str) -> Path:
    return PROPS_DIR / "inbox" / f"bet365-most-aces-1x2-{as_of}.csv"


def has_market_rows(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        return sum(1 for line in path.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip()) > 1
    except OSError:
        return False


def market_event_dates(path: Path) -> set[str]:
    if not has_market_rows(path):
        return set()
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return {
                str(row.get("date") or "").strip()
                for row in csv.DictReader(handle)
                if str(row.get("date") or "").strip()
            }
    except (OSError, csv.Error):
        return set()


def build_combined_market_file(as_of: str) -> Path | None:
    sources = [path for path in (lines_file(as_of), betsbk_lines_file(as_of)) if has_market_rows(path)]
    if not sources:
        return None
    rows: list[dict[str, str]] = []
    fields: list[str] = []
    seen: set[tuple[tuple[str, str], ...]] = set()
    for path in sources:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for field in reader.fieldnames or []:
                if field not in fields:
                    fields.append(field)
            for raw_row in reader:
                row = {str(key): str(value or "") for key, value in raw_row.items() if key is not None}
                key = tuple(sorted(row.items()))
                if key in seen:
                    continue
                seen.add(key)
                rows.append(row)
    if not rows or not fields:
        return None
    out = combined_lines_file(as_of)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(
        f"Combined tennis props prices: {len(rows)} rows from "
        f"{', '.join(path.name for path in sources)} -> {out.name}"
    )
    return out


def select_market_file(as_of: str, lookback_days: int = 3) -> Path | None:
    exact = build_combined_market_file(as_of)
    if exact is not None:
        return exact
    target = date.fromisoformat(as_of)
    for offset in range(1, max(0, lookback_days) + 1):
        candidate_date = (target - timedelta(days=offset)).isoformat()
        candidate = build_combined_market_file(candidate_date)
        if candidate is not None and any(day >= as_of for day in market_event_dates(candidate)):
            return candidate
    return None


def select_most_aces_file(as_of: str, lookback_days: int = 3) -> Path | None:
    # Automated Grosvenor uses the cloud job's existing compatibility filename.
    # Prefer today's complete capture to an older connected-browser import.
    automated = PROPS_DIR / "inbox" / f"betmgm-most-aces-1x2-{as_of}.csv"
    if has_market_rows(automated):
        return automated
    exact = most_aces_lines_file(as_of)
    if has_market_rows(exact):
        return exact
    target = date.fromisoformat(as_of)
    for offset in range(1, max(0, lookback_days) + 1):
        candidate = most_aces_lines_file((target - timedelta(days=offset)).isoformat())
        if has_market_rows(candidate) and any(day >= as_of for day in market_event_dates(candidate)):
            return candidate
    return None


def refresh_derived_ace_boards(as_of: str) -> None:
    """Full and Admin refreshes share the same current-board validation."""
    if not refresh_current_most_aces(as_of, register=False):
        raise RuntimeError('Current derived tennis projections are incomplete')


def refresh_current_most_aces(as_of: str, *, register: bool = True) -> bool:
    """Bounded current boards, without historical settlement/reporting."""
    from tennis_pairing_consistency import clear_empty_derived_scope
    empty_scope = clear_empty_derived_scope(ROOT)
    complete = True
    builders = [('tennis-props-v3-live.py', [], 'aces-v3-projection-board.csv')]
    if not most_aces_suspended():
        builders += [('build-tennis-most-aces-board.py', [], 'most-aces-1x2-board.csv'),
                     ('tennis-most-aces-direct-live.py', ['--as-of', as_of], 'most-aces-direct-1x2-board.csv')]
    for script, arguments, output in ([] if empty_scope else builders):
        started = datetime.now(timezone.utc).timestamp()
        code = run([sys.executable, str(ROOT / 'scripts' / script), *arguments], script, fatal=False, timeout_seconds=180)
        target = PROPS_DIR / 'shadow' / output
        if not code and target.exists():
            try:
                verify_derived_board(ROOT, output)
            except (ValueError, KeyError) as exc:
                print('WARNING: ' + str(exc))
                code = 1
        if code or not target.exists() or target.stat().st_mtime < started:
            if script == 'tennis-most-aces-direct-live.py':
                # Direct is an independent experiment, never the alert authority.
                # Clear its current board so stale rows cannot be registered.
                target.write_text('', encoding='utf-8')
                print('WARNING: Direct research refresh failed; Count paper comparison continues.')
                complete = False
                continue
            (PROPS_DIR / 'shadow/most-aces-current.json').write_text(json.dumps({
                'generated_at': datetime.now(timezone.utc).isoformat(), 'status': 'REFRESH_FAILED',
                'failed_step': script, 'matches': [], 'records': [],
                'note': 'Most Aces refresh failed. Earlier boards are not fresh signals.'}), encoding='utf-8')
            return False
    if not register or most_aces_suspended():
        return complete
    code = run([sys.executable, str(ROOT / 'scripts/tennis_most_aces_current.py'), '--as-of', as_of],
        'Compare current Most Aces 1X2 prices and register paper observations', fatal=False, timeout_seconds=90)
    return complete and code == 0


def refresh_current_paper_lanes(as_of: str) -> bool:
    """Refresh existing observers from the same boards/prices before Admin returns."""
    commands = [
        ('tennis_ace_compass.py', ['--comparison', str(PROPS_DIR / f'comparison-{as_of}.csv')], 240),
        ('tennis_sisal_5050.py', ['--quotes', str(PROPS_DIR / 'inbox' / f'bet365-lines-{as_of}.csv')], 180),
        ('tennis_v4_current_capture.py', ['--comparison', str(PROPS_DIR / f'comparison-v3-aces-{as_of}.csv')], 90),
    ]
    failures = []
    for script, arguments, timeout in commands:
        code = run([sys.executable, str(ROOT / 'scripts' / script), *arguments],
                   'Refresh existing paper lane: ' + script, fatal=False, timeout_seconds=timeout)
        if code:
            failures.append({'script': script, 'exit': code})
    from tennis_pairing_consistency import atomic
    atomic(ROOT / 'data/tennis-input-health/paper-refresh-status.json', {
        'checked_at': datetime.now(timezone.utc).isoformat(), 'as_of': as_of,
        'state': 'FAILED' if failures else 'CURRENT', 'failures': failures,
        'models_changed': False, 'alerts_sent': 0})
    return not failures


def run_most_aces_shadow(as_of: str, capture: Path | None = None) -> None:
    forecast_cmd = [
        sys.executable,
        str(ROOT / "scripts" / "tennis-most-aces-forecast.py"),
    ]
    if has_market_rows(MOST_ACES_DIRECT_BOARD):
        forecast_cmd.extend(["--additional-board", str(MOST_ACES_DIRECT_BOARD)])
    run(
        forecast_cmd,
        "Register and score A0 plus Direct Most Aces 1X2 forecasts",
        fatal=False,
        timeout_seconds=240,
    )
    cmd = [sys.executable, str(ROOT / "scripts" / "tennis-most-aces-shadow.py")]
    if has_market_rows(MOST_ACES_DIRECT_BOARD):
        cmd.extend(["--additional-board", str(MOST_ACES_DIRECT_BOARD)])
    selected = capture or select_most_aces_file(as_of)
    if selected and has_market_rows(selected):
        cmd.extend(["--capture", str(selected)])
    run(cmd, "Update Most Aces 1X2 paper evidence", fatal=False)
    run([sys.executable, str(ROOT / 'scripts/tennis_most_aces_current.py'), '--as-of', as_of],
        'Refresh current Most Aces comparison', fatal=False, timeout_seconds=90)


def run_comparison(
    as_of: str, market_file: Path, *, include_challengers: bool = True,
    timeout_seconds: int | None = None,
) -> bool:
    comparison = PROPS_DIR / f"comparison-{as_of}.csv"
    mark_pipeline_blocked(as_of, market_file, "canonical_comparison", running=True)
    # A failed rebuild must not leave a same-date file that looks current.
    if comparison.exists():
        comparison.unlink()
    exit_code = run(
        [
            sys.executable,
            str(ROOT / "scripts" / "tennis-props-compare-bet365.py"),
            "--date",
            as_of,
            "--lines",
            str(market_file),
        ],
        "Compare Bet365 lines with projections",
        fatal=False,
        timeout_seconds=timeout_seconds,
    )
    if exit_code != 0 or not has_market_rows(comparison):
        # Some failures occur after a partial CSV was written. It is no more
        # trustworthy than the previous comparison that was removed above.
        if comparison.exists():
            comparison.unlink()
        mark_pipeline_blocked(as_of, market_file, "canonical_comparison")
        return False
    if not include_challengers:
        return True
    v3_board = PROPS_DIR / "shadow" / "aces-v3-projection-board.csv"
    v3_comparison = PROPS_DIR / f"comparison-v3-aces-{as_of}.csv"
    if v3_comparison.exists():
        v3_comparison.unlink()
    if has_market_rows(v3_board):
        try:
            verify_derived_board(ROOT, v3_board.name)
        except (ValueError, KeyError) as exc:
            print('WARNING: ' + str(exc))
            return False
        code = run(
            [
                sys.executable,
                str(ROOT / "scripts" / "tennis-props-compare-bet365.py"),
                "--date", as_of,
                "--lines", str(market_file),
                "--board", str(v3_board),
                "--out", str(PROPS_DIR / f"comparison-v3-aces-{as_of}.csv"),
                "--unmatched-out", str(PROPS_DIR / f"comparison-v3-aces-{as_of}-unmatched.csv"),
                "--market-filter", "aces,ace,player_aces,match_aces",
            ],
            "Compare v3 ATP ace shadow projections with Bet365",
            fatal=False,
            timeout_seconds=60,
        )
        if code or not v3_comparison.exists():
            return False
    else:
        v3_comparison.write_text("date,player,opponent,market\n", encoding="utf-8")
    return True


def run_shadow_tracking(as_of: str) -> None:
    run(
        [
            sys.executable,
            str(ROOT / "scripts" / "tennis-props-build-price-history.py"),
        ],
        "Consolidate append-only Bet365 price history",
        fatal=False,
    )
    run(
        [sys.executable, str(ROOT / "scripts/tennis_ace_compass.py"),
         "--comparison", str(PROPS_DIR / f"comparison-{as_of}.csv")],
        "Capture and settle Ace Compass paper research", fatal=False, timeout_seconds=240,
    )
    run(
        [sys.executable, str(ROOT / "scripts/tennis_sisal_5050.py"),
         "--quotes", str(PROPS_DIR / "inbox" / f"bet365-lines-{as_of}.csv")],
        "Capture and settle Sisal 50/50 paper evidence (no alerts)", fatal=False, timeout_seconds=240,
    )
    # Current captures must survive slow historical report/settlement scans.
    run([sys.executable, str(ROOT / 'scripts/tennis_v4_current_capture.py'),
         '--comparison', str(PROPS_DIR / f'comparison-v3-aces-{as_of}.csv')],
        'Capture current v4 evidence before historical reports', fatal=False, timeout_seconds=90)
    run([sys.executable, str(ROOT / 'scripts/tennis_most_df.py'), '--capture-only'],
        'Refresh current Most DF report before historical settlement', fatal=False, timeout_seconds=90)
    run_most_aces_shadow(as_of)
    run([sys.executable, str(ROOT / 'scripts/tennis_most_df.py')],
        'Capture and settle Most DF paper observations (no alerts)', fatal=False, timeout_seconds=60)
    v3_comparison = PROPS_DIR / f"comparison-v3-aces-{as_of}.csv"
    venue_comparison = PROPS_DIR / f"comparison-venue-ace-v1-{as_of}.csv"
    comparison = PROPS_DIR / f"comparison-{as_of}.csv"
    run(
        [sys.executable, str(ROOT / "scripts/tennis-props-rate-trend-prospective.py"),
         "--comparison", str(comparison)],
        "Freeze and settle paired rate-trend prospective research",
        fatal=False, timeout_seconds=300,
    )
    if has_market_rows(comparison):
        run(
            [
                sys.executable,
                str(ROOT / "scripts" / "tennis-props-market-observations.py"),
                "--comparison",
                str(comparison),
            ],
            "Update all-main-line Bet365 observation benchmark",
            fatal=False,
            timeout_seconds=300,
        )
        run(
            [
                sys.executable,
                str(ROOT / "scripts" / "tennis-props-shadow-tracker.py"),
                "--date",
                as_of,
                "--comparison",
                str(comparison),
                "--allow-medium",
            ],
            "Append tennis props shadow signals",
            fatal=True,
        )
    else:
        print(f"WARNING: exact-date comparison missing; shadow append skipped: {comparison}")
    run(
        [
            sys.executable,
            str(ROOT / "scripts" / "tennis-props-settle-shadow.py"),
        ],
        "Settle tennis props shadow signals",
        fatal=True,
    )
    run(
        [
            sys.executable,
            str(ROOT / "scripts" / "tennis-props-model-report.py"),
        ],
        "Build tennis props model monitor report",
        fatal=True,
    )
    run(
        [
            sys.executable,
            str(ROOT / "scripts" / "tennis-derivatives-evidence-report.py"),
        ],
        "Refresh tennis derivative evidence gates",
        fatal=False,
    )
    # The v4 challenger can consume its full timeout. Keep it behind the core
    # append/settle/report path so optional research cannot suppress alerts.
    v4_cmd = [
        sys.executable,
        str(ROOT / "scripts" / "tennis-props-aces-over-v4.py"),
    ]
    run(
        v4_cmd,
        "Register and score ATP ace-over v4 challenger",
        fatal=False,
        timeout_seconds=180,
    )


def write_pipeline_health(as_of: str, market_file: Path | None, *, strict: bool = False) -> int:
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "tennis-props-pipeline-health.py"),
        "--date",
        as_of,
        "--lines",
        str(market_file or lines_file(as_of)),
        "--comparison",
        str(PROPS_DIR / f"comparison-{as_of}.csv"),
    ]
    if strict:
        cmd.append("--strict")
    return run(cmd, "Write tennis props pipeline health", fatal=False, timeout_seconds=15)


def mark_pipeline_blocked(as_of: str, market_file: Path | None, step: str, *, running: bool = False) -> None:
    """A failed or interrupted core refresh cannot retain a healthy artifact."""
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "as_of": as_of,
        "state": "CORE_RUN_IN_PROGRESS" if running else "CORE_RUN_FAILED",
        "structural_error": True,
        "core_failure": step,
        "lines_file": str(market_file or combined_lines_file(as_of)),
        "comparison_file": str(PROPS_DIR / f"comparison-{as_of}.csv"),
        "actionable_shadow_rows": 0,
        "actionable_public_rows": 0,
        "break_state": "PIPELINE_UNHEALTHY",
        "top_shadow_blocker": step,
    }
    PROPS_DIR.mkdir(parents=True, exist_ok=True)
    for filename, content in (
        ("pipeline-health.json", json.dumps(payload, indent=2) + "\n"),
        ("pipeline-health.txt", f"Tennis props pipeline health\nState: {payload['state']}\nStep: {step}\nCurrent recommendations blocked.\n"),
    ):
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=PROPS_DIR, prefix=".health-", delete=False) as handle:
            handle.write(content)
            temporary = Path(handle.name)
        temporary.replace(PROPS_DIR / filename)


def comparison_failure(as_of: str, market_file: Path) -> int:
    mark_pipeline_blocked(as_of, market_file, "canonical_comparison")
    return 1


def run_monitor_only(as_of: str, *, selections_only: bool = False) -> int:
    """Refresh current forecasts and existing paper lanes, without odds downloads."""
    market_file = None
    step = "select_combined_prices"
    mark_pipeline_blocked(as_of, None, step, running=True)
    try:
        step = 'current_pairing_projection_check'
        ensure_props_board(ROOT, as_of, runner=run)
        derived_ready = refresh_current_most_aces(as_of)
        market_file = select_market_file(as_of)
        if market_file is None:
            mark_pipeline_blocked(as_of, None, "market_prices_missing")
            return 1
        step = "canonical_comparison"
        if not run_comparison(as_of, market_file, include_challengers=True, timeout_seconds=25):
            return comparison_failure(as_of, market_file)
        commands = (
            ("shadow_registration", "tennis-props-shadow-tracker.py", ["--date", as_of, "--comparison", str(PROPS_DIR / f"comparison-{as_of}.csv"), "--allow-medium"], 15),
            ("shadow_settlement", "tennis-props-settle-shadow.py", [], 90),
            ("model_report", "tennis-props-model-report.py", [], 25),
        )
        if selections_only:
            commands = tuple(command for command in commands if command[0] == "shadow_registration")
        for step, script, arguments, timeout in commands:
            mark_pipeline_blocked(as_of, market_file, step, running=True)
            code = run([sys.executable, str(ROOT / "scripts" / script), *arguments], step, fatal=False, timeout_seconds=timeout)
            if code != 0:
                mark_pipeline_blocked(as_of, market_file, step)
                return code
        step = "pipeline_health"
        df_exit = run([sys.executable, str(ROOT / 'scripts/tennis_most_df.py'), '--capture-only'],
            'Record current Most DF paper comparison (no historical wait or alerts)', fatal=False, timeout_seconds=90)
        paper_ready = refresh_current_paper_lanes(as_of)
        if not derived_ready or df_exit or not paper_ready:
            mark_pipeline_blocked(as_of, market_file, 'current_model_refresh_incomplete')
            return 1
        code = write_pipeline_health(as_of, market_file, strict=True)
        if code != 0:
            try:
                health = json.loads((PROPS_DIR / "pipeline-health.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                health = {}
            # Strict health exits nonzero for a correctly diagnosed stale or
            # incomplete feed. Preserve that explanation when it was written.
            reported_failure = (
                health.get("as_of") == as_of and health.get("structural_error") is True
                and health.get("state") not in {"CORE_RUN_IN_PROGRESS", "CORE_RUN_FAILED", None}
            )
            if not reported_failure:
                mark_pipeline_blocked(as_of, market_file, step)
        return code
    except (Exception, SystemExit):
        mark_pipeline_blocked(as_of, market_file, step)
        raise


def sync_hosted_captures(as_of: str, lookback_days: int) -> None:
    run(
        [
            sys.executable,
            str(ROOT / "scripts" / "sync-tennis-props-hosted-captures.py"),
            "--as-of",
            as_of,
            "--lookback-days",
            str(lookback_days),
        ],
        "Sync hosted Bet365 tennis-props captures",
        fatal=False,
        timeout_seconds=120,
    )


def capture_market_prices(args: argparse.Namespace) -> int:
    """Capture prices before the slow projection build can hit its timeout."""
    if args.skip_odds:
        print("\nMarket capture skipped by --skip-odds.")
        return 0
    run([sys.executable, str(ROOT / "scripts/tennis_sisal_5050.py"), "--prepare-event"],
        "Freeze completed tournament evidence before Sisal quotes (paper only)",
        fatal=False, timeout_seconds=120)
    source_exits: list[int] = []
    if has_odds_key():
        source_exits.append(
            run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "tennis-props-scrape-bet365.py"),
                    "--date", args.as_of,
                    "--days-ahead", str(args.days_ahead),
                    "--max-events", str(args.max_events),
                    "--bookmakers", "Sisal IT,Kambi",
                ],
                "Capture Sisal/Kambi and Grosvenor stat bets before projections",
                fatal=False,
                timeout_seconds=180,
            )
        )
        # The shared collector already saves complete Most Aces markets from
        # selected books and Grosvenor. Do not overwrite those with a removed
        # BetMGM account request or spend another provider request budget.
    else:
        print("\nWARNING: no local odds-api key; Bet365/BetMGM capture skipped.")

    if os.name == "nt" and not args.skip_bet365_direct:
        # The public connected browser works, but unattended browser access is
        # blocked. Consume only newly provided evidence; never retry the block.
        most_evidence = PROPS_DIR / 'inbox' / f'bet365-most-props-evidence-{args.as_of}.json'
        if most_evidence.exists():
            run([sys.executable, str(ROOT / 'scripts' / 'tennis-most-props-bet365-direct.py'),
                 '--date', args.as_of, '--evidence-json', str(most_evidence)],
                'Validate connected-browser Most Aces/Double Faults prices', fatal=False, timeout_seconds=30)
        source_exits.append(
            run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "tennis-props-scrape-bet365-direct.py"),
                    "--date", args.as_of,
                    "--max-events", str(min(args.max_events, 40)),
                ],
                "Capture direct Bet365 service-break totals",
                fatal=False,
                timeout_seconds=480,
            )
        )

    if not args.skip_betsbk:
        source_exits.append(
            run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "tennis-props-scrape-betsbk.py"),
                    "--date", args.as_of,
                    "--days-ahead", str(args.days_ahead),
                    "--max-events", str(args.max_events),
                ],
                "Capture BetsBK US Open aces/DF fallback",
                fatal=False,
                timeout_seconds=900,
            )
        )
    if args.require_odds and build_combined_market_file(args.as_of) is None:
        raise SystemExit("No supported tennis props prices were captured from Bet365 or BetsBK.")
    return 0 if any(exit_code == 0 for exit_code in source_exits) else (source_exits[0] if source_exits else 0)


def run_comparison_only(
    as_of: str,
    *,
    skip_sync: bool,
    lookback_days: int,
    skip_derived_boards: bool = False,
    selections_only: bool = False,
) -> int:
    mark_pipeline_blocked(as_of, None, "comparison_refresh", running=True)
    if not skip_sync:
        sync_hosted_captures(as_of, lookback_days)
    if skip_derived_boards:
        # Manual refresh needs the bounded current board, not slow research lanes.
        return run_monitor_only(as_of, selections_only=selections_only)
    ensure_props_board(ROOT, as_of, runner=run)
    market_file = select_market_file(as_of)
    if market_file is None:
        print(f"WARNING: no hosted/local Bet365 capture contains {as_of} events.")
        return write_pipeline_health(as_of, None)
    if not skip_derived_boards:
        refresh_derived_ace_boards(as_of)
    print(f"Using hosted/local Bet365 capture: {market_file}")
    if not run_comparison(as_of, market_file):
        return comparison_failure(as_of, market_file)
    run_shadow_tracking(as_of)
    return write_pipeline_health(as_of, market_file, strict=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build tennis aces/DF projections and optional Bet365 comparison")
    parser.add_argument("--as-of", default=date.today().isoformat())
    parser.add_argument("--start-year", type=int, default=2022)
    parser.add_argument("--end-year", type=int, default=date.today().year)
    parser.add_argument("--refresh-sackmann", action="store_true", help="Download fresh ATP/WTA Sackmann CSVs first")
    parser.add_argument("--refresh-sackmann-current-season", action="store_true", help="Refresh only the end-year season; preserve earlier training snapshots")
    parser.add_argument("--skip-odds", action="store_true", help="Do not scrape Bet365 lines even if a key is configured")
    parser.add_argument("--skip-betsbk", action="store_true", help="Skip the local public BetsBK US Open props fallback")
    parser.add_argument("--skip-bet365-direct", action="store_true", help="Skip the Windows-local direct Bet365 service-break fallback")
    parser.add_argument("--require-odds", action="store_true", help="Fail if the Bet365 odds scrape cannot run")
    parser.add_argument("--selections-only", action="store_true", help="Register current selections; leave historical settlements/reports to the scheduled run")
    parser.add_argument("--comparison-only", action="store_true", help="Sync hosted prices and refresh comparison/tracking without rebuilding projections")
    parser.add_argument("--monitor-only", action="store_true", help="Current boards, comparisons and existing paper lanes; no new odds download or model fitting")
    parser.add_argument("--skip-derived-boards", action="store_true", help="Skip slow derived ace boards during a fast comparison pass")
    parser.add_argument("--capture-only", action="store_true", help="Capture bookmaker tennis count prices without rebuilding projections")
    parser.add_argument("--skip-hosted-sync", action="store_true", help="Do not sync captures from the golden data branch")
    parser.add_argument("--hosted-lookback-days", type=int, default=7)
    parser.add_argument("--days-ahead", type=int, default=3)
    parser.add_argument("--max-events", type=int, default=128)
    args = parser.parse_args()

    if args.selections_only and not (args.monitor_only or (args.comparison_only and args.skip_derived_boards)):
        parser.error("--selections-only requires --monitor-only or --comparison-only --skip-derived-boards")
    load_env()
    PROPS_DIR.mkdir(parents=True, exist_ok=True)

    if args.monitor_only:
        return run_monitor_only(args.as_of, selections_only=args.selections_only)

    if args.capture_only:
        return capture_market_prices(args)

    mark_pipeline_blocked(args.as_of, None, "full_refresh", running=True)

    if args.comparison_only:
        return run_comparison_only(
            args.as_of,
            skip_sync=args.skip_hosted_sync,
            lookback_days=args.hosted_lookback_days,
            skip_derived_boards=args.skip_derived_boards,
            selections_only=args.selections_only,
        )

    # Capture first. The projection board can take several minutes and is
    # deliberately timeout-bounded by the scheduled task; prices must not be
    # lost merely because that independent research build runs long.
    capture_market_prices(args)

    if args.refresh_sackmann or args.refresh_sackmann_current_season:
        run(
            [
                sys.executable,
                str(ROOT / "scripts" / "sackmann-refresh-data.py"),
                "--tour",
                "both",
                "--start-year",
                str(args.end_year if args.refresh_sackmann_current_season else args.start_year),
                "--end-year",
                str(args.end_year),
            ],
            "Refresh Sackmann ATP/WTA snapshots",
            fatal=False,
            timeout_seconds=240,
        )

    run(
        [
            sys.executable,
            str(ROOT / "scripts" / "sackmann-compute-slam-venue-factors.py"),
            "--start-year",
            str(args.start_year),
            "--end-year",
            str(max(args.start_year, args.end_year - 1)),
        ],
        "Compute tennis props venue factors",
        fatal=True,
    )
    run(
        [sys.executable, str(ROOT / "scripts/tennis_props_current_history.py"),
         "--as-of", args.as_of, "--publish"],
        "Refresh validated current player histories and activity",
        fatal=True, timeout_seconds=300,
    )
    run(
        [
            sys.executable,
            str(ROOT / "scripts" / "build-tennis-props-board.py"),
            "--as-of",
            args.as_of,
            "--days-ahead",
            str(args.days_ahead),
        ],
        "Build tennis props projection board",
        fatal=True,
    )
    ensure_props_board(ROOT, args.as_of, runner=run, days_ahead=args.days_ahead)
    run(
        [
            sys.executable,
            str(ROOT / "scripts" / "tennis-props-feature-audit.py"),
            "--as-of", args.as_of,
        ],
        "Audit recent OnCourt break-point and second-serve feature coverage",
        fatal=False,
        timeout_seconds=120,
    )
    refresh_derived_ace_boards(args.as_of)

    if not args.skip_hosted_sync:
        sync_hosted_captures(args.as_of, args.hosted_lookback_days)

    if args.skip_odds:
        print("\nBet365 scrape skipped by --skip-odds.")
        market_file = select_market_file(args.as_of)
        if market_file:
            print(f"Using hosted/local Bet365 capture: {market_file}")
            if not run_comparison(args.as_of, market_file):
                return comparison_failure(args.as_of, market_file)
        run_shadow_tracking(args.as_of)
        return write_pipeline_health(args.as_of, market_file, strict=bool(market_file))
    if not has_odds_key():
        market_file = select_market_file(args.as_of)
        if market_file:
            print(f"\nLocal odds key missing; using hosted Bet365 capture: {market_file}")
            if not run_comparison(args.as_of, market_file):
                return comparison_failure(args.as_of, market_file)
            run_shadow_tracking(args.as_of)
            health_exit = write_pipeline_health(args.as_of, market_file, strict=True)
            if health_exit != 0:
                return health_exit
            return 0
        msg = "No local ODDS_API_KEY / ODDS_API_IO_KEY configured; projections refreshed, Bet365 scrape skipped."
        write_pipeline_health(args.as_of, None)
        if args.require_odds:
            raise SystemExit(msg)
        print(f"\nWARNING: {msg}")
        run_shadow_tracking(args.as_of)
        return 0

    market_file = select_market_file(args.as_of)
    # The selected snapshot is the canonical union of all captured bookmakers,
    # including usable fallback snapshots when one capture source failed.
    if market_file and not run_comparison(args.as_of, market_file):
        return comparison_failure(args.as_of, market_file)
    run_shadow_tracking(args.as_of)
    health_exit = write_pipeline_health(args.as_of, market_file, strict=bool(market_file))
    if health_exit != 0:
        return health_exit

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
