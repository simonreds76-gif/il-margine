#!/usr/bin/env python3
"""Send the current local tennis signals to the private ops Telegram chat.

OnCourt and the model run locally. This script renders their current CSV
outputs, then dispatches a small GitHub Actions relay so Telegram credentials
remain in GitHub Secrets rather than being copied onto the Windows laptop.
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
BACKTEST = ROOT / "data" / "backtest"
PROPS = ROOT / "data" / "tennis-props"
DEFAULT_REPORT = BACKTEST / "tennis-daily-signal-digest.txt"
DEFAULT_STATE = BACKTEST / "tennis-daily-signal-digest-state.json"
DEFAULT_READY_STATE = BACKTEST / "tennis-signal-generation-status.json"
DEFAULT_GAP_LIVE = BACKTEST / "tennis-model-market-gap-live.csv"
DEFAULT_REPOSITORY = "simonreds76-gif/il-margine"
DEFAULT_WORKFLOW = "tennis-daily-signal-digest.yml"
DEFAULT_REF = "golden-with-speed-insights"
TELEGRAM_LIMIT = 3900


@dataclass(frozen=True)
class Lane:
    label: str
    path: Path
    section: str
    priority: int


LANES = (
    Lane("STRICT", BACKTEST / "strict-signals-live.csv", "CORE", 0),
    Lane("VOL200", BACKTEST / "strict-signals-volume200-live.csv", "TRACKED EXPANSION", 10),
    Lane("SPREAD V1", BACKTEST / "strict-signals-spreadv1-live.csv", "SHADOW / RESEARCH", 20),
    Lane("GRASS BO3", BACKTEST / "strict-signals-grass_bo3-live.csv", "SHADOW / RESEARCH", 30),
    Lane("CLAY BO3", BACKTEST / "strict-signals-clay_bo3-live.csv", "SHADOW / RESEARCH", 31),
    Lane("CPI SPEED", BACKTEST / "strict-signals-cpi_speed-live.csv", "SHADOW / RESEARCH", 32),
)


@dataclass
class Signal:
    section: str
    priority: int
    labels: list[str]
    match: str
    selection: str
    edge_pct: float | None
    time_utc: str = ""
    key: tuple[str, ...] = field(default_factory=tuple)


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def parse_float(value: object) -> float | None:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def is_pending(row: dict[str, str]) -> bool:
    return (row.get("settlement_status") or "pending").strip().lower() in {"", "pending", "open"}


def fmt_odds(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.3f}".rstrip("0").rstrip(".")


def fmt_stake(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.2f}".rstrip("0").rstrip(".") + "u"


def norm(value: object) -> str:
    return " ".join(str(value or "").strip().lower().split())


def row_event_date(row: dict[str, str]) -> str:
    """Return only a confirmed event date, never a generation-date fallback."""
    status = (row.get("schedule_status") or "").strip().lower()
    scheduled = (row.get("scheduled_date") or row.get("match_date") or "").strip()
    if scheduled:
        return scheduled
    if status in {"tbd", "unknown", "unconfirmed"}:
        return ""
    # Backward compatibility for rows written before schedule metadata existed.
    return (row.get("date") or "").strip()


def row_to_signal(row: dict[str, str], lane: Lane, target_date: str) -> Signal | None:
    event_date = row_event_date(row)
    if event_date != target_date or not is_pending(row):
        return None
    player1 = (row.get("player1") or "").strip()
    player2 = (row.get("player2") or "").strip()
    side = (row.get("side") or "").strip().upper()
    if not player1 or not player2 or not side.startswith(("P1", "P2")):
        return None
    selected = player1 if side.startswith("P1") else player2
    market = (row.get("bet_type") or "match").strip().lower()
    edge = parse_float(row.get("value_pct"))
    stake = parse_float(row.get("stake_units"))
    time_utc = (row.get("time_utc") or "").strip()

    if market == "spread":
        line = parse_float(row.get("spread_line"))
        odds = parse_float(row.get("spread_odds"))
        if line is None or odds is None:
            return None
        selection = f"{selected} {line:+g} games @ {fmt_odds(odds)}"
        key_market = f"spread:{line:+g}"
    else:
        odds_field = "pin_odds1" if side.startswith("P1") else "pin_odds2"
        fair_field = "our_odds1" if side.startswith("P1") else "our_odds2"
        odds = parse_float(row.get(odds_field))
        fair = parse_float(row.get(fair_field))
        if odds is None:
            return None
        selection = f"{selected} ML @ {fmt_odds(odds)}"
        if fair is not None:
            selection += f" | fair {fmt_odds(fair)}"
        key_market = "ml"
    if edge is not None:
        selection += f" | edge {edge:+.1f}%"
    if stake is not None:
        selection += f" | {fmt_stake(stake)}"

    pair = tuple(sorted((norm(player1), norm(player2))))
    key = (event_date, *pair, norm(selected), key_market)
    return Signal(
        section=lane.section,
        priority=lane.priority,
        labels=[lane.label],
        match=f"{player1} vs {player2}",
        selection=selection,
        edge_pct=edge,
        time_utc=time_utc,
        key=key,
    )


def gap_replacement_signal(row: dict[str, str], target_date: str) -> Signal | None:
    event_date = row_event_date(row)
    if event_date != target_date or not is_pending(row):
        return None
    if (row.get("bet_type") or "match").strip().lower() == "spread":
        return None

    cohorts = [item for item in (row.get("replacement_cohorts") or "").split("|") if item]
    forward_flag = (row.get("replacement_forward_eligible") or "1").strip().lower()
    gap = parse_float(row.get("model_market_gap_pp"))
    policy_profiles = {
        item for item in (row.get("policy_profiles") or "").split("|") if item
    }
    side_flip = (row.get("side_flip") or "").strip().lower() in {"1", "true", "yes"}
    short_favorite = (row.get("short_favorite_guard") or "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    hard_side_flip_candidate = (
        side_flip
        and (row.get("surface") or "").strip().lower() == "hard"
        and gap is not None
        and gap <= 10.0
        and bool(policy_profiles & {"strict", "volume_200"})
        and (row.get("data_coverage_tag") or "").strip().upper() == "HIGH"
        and not short_favorite
    )
    registered_gap_candidate = bool(cohorts) and forward_flag in {"1", "true", "yes"}
    if not registered_gap_candidate and not hard_side_flip_candidate:
        return None

    player1 = (row.get("player1") or "").strip()
    player2 = (row.get("player2") or "").strip()
    selected = (row.get("selected_player") or "").strip()
    selected_side = (row.get("selected_side") or row.get("side") or "").strip().upper()
    odds = parse_float(row.get("selected_odds"))
    if not player1 or not player2 or not selected or selected_side not in {"P1", "P2"} or odds is None:
        return None

    fair = parse_float(row.get("fair_odds1" if selected_side == "P1" else "fair_odds2"))
    edge = parse_float(row.get("value_pct"))
    quality = (row.get("diagnostic_quality") or "UNKNOWN").strip().upper()
    labels: list[str] = []
    if "strict_gap_10_20_same_side" in cohorts:
        labels.append("STRICT GAP")
    if "volume200_gap_10_15_same_side" in cohorts:
        labels.append("VOL200 GAP")
    if hard_side_flip_candidate:
        labels.append("HARD FLIP")
    if not labels:
        labels.append("ML GAP")

    selection = f"{selected} ML @ {fmt_odds(odds)}"
    if fair is not None:
        selection += f" | fair {fmt_odds(fair)}"
    if edge is not None:
        selection += f" | edge {edge:+.1f}%"
    if gap is not None:
        selection += f" | gap {gap:.1f}pp"
    if hard_side_flip_candidate:
        selection += " | model/market side flip"
    selection += f" | quality {quality} | 0.5u"
    pair = tuple(sorted((norm(player1), norm(player2))))
    return Signal(
        section="PROVISIONAL HARD ML" if hard_side_flip_candidate else "PROVISIONAL ML EXPANSION",
        priority=14 if hard_side_flip_candidate else 15,
        labels=labels,
        match=f"{player1} vs {player2}",
        selection=selection,
        edge_pct=edge,
        time_utc=(row.get("time_utc") or "").strip(),
        key=(event_date, *pair, norm(selected), "ml"),
    )

def props_signals(target_date: str) -> list[Signal]:
    path = PROPS / f"comparison-{target_date}.csv"
    signals: list[Signal] = []
    for row in read_csv(path):
        event_date = row_event_date(row)
        if event_date != target_date:
            continue
        is_bettable = (row.get("bettable") or "").strip().lower() in {"1", "true", "yes"}
        is_shadow = (row.get("trackable_shadow") or "").strip().lower() in {"1", "true", "yes"}
        if not is_bettable and not is_shadow:
            continue
        side_field = "recommended_side" if is_bettable else "shadow_side"
        side = (row.get(side_field) or "").strip().upper()
        if side not in {"OVER", "UNDER"}:
            continue
        player = (row.get("player") or "").strip()
        opponent = (row.get("opponent") or "").strip()
        market = (row.get("market") or "").strip().lower()
        line = parse_float(row.get("line"))
        odds = parse_float(row.get("over_odds" if side == "OVER" else "under_odds"))
        fair = parse_float(row.get("fair_over_odds" if side == "OVER" else "fair_under_odds"))
        edge = parse_float(row.get("value_over_pct" if side == "OVER" else "value_under_pct"))
        if not player or not opponent or line is None or odds is None:
            continue
        if market.startswith("match_"):
            subject = "Match"
        else:
            subject = player
        is_service_break_market = "break" in market and "tiebreak" not in market and "tie_break" not in market
        if is_service_break_market:
            market_label = "service breaks"
        elif "ace" in market:
            market_label = "aces"
        else:
            market_label = "double faults"
        selection = f"{subject} {market_label} {side.title()} {line:g} @ {fmt_odds(odds)}"
        if fair is not None:
            selection += f" | fair {fmt_odds(fair)}"
        if edge is not None:
            selection += f" | edge {edge:+.1f}%"
        if is_shadow and not is_bettable:
            selection += " | shadow evidence only"
        bookmaker = (row.get("bookmaker") or "Bet365").strip()
        source_name = bookmaker.upper()
        pair = tuple(sorted((norm(player), norm(opponent))))
        if is_service_break_market:
            section = f"{source_name} BREAKS" if is_bettable else f"{source_name} BREAKS WATCHLIST"
            labels = ["BREAKS"] if is_bettable else ["BREAKS WATCH"]
        else:
            section = f"{source_name} PROPS" if is_bettable else f"{source_name} PROPS WATCHLIST"
            labels = ["ACES/DF"] if is_bettable else ["ACES/DF WATCH"]
        signals.append(
            Signal(
                section=section,
                priority=40 if is_bettable else 45,
                labels=labels,
                match=f"{player} vs {opponent}",
                selection=selection,
                edge_pct=edge,
                time_utc=(row.get("match_start_utc") or "").strip(),
                key=(event_date, *pair, norm(subject), market, f"{line:g}", side),
            )
        )
    return signals


def collect_signals(target_date: str) -> tuple[list[Signal], list[str]]:
    merged: dict[tuple[str, ...], Signal] = {}
    lane_counts: dict[str, int] = {}
    for lane in LANES:
        count = 0
        for row in read_csv(lane.path):
            signal = row_to_signal(row, lane, target_date)
            if signal is None:
                continue
            count += 1
            existing = merged.get(signal.key)
            if existing is None:
                merged[signal.key] = signal
            else:
                if lane.label not in existing.labels:
                    existing.labels.append(lane.label)
                if signal.priority < existing.priority:
                    signal.labels = existing.labels
                    merged[signal.key] = signal
        lane_counts[lane.label] = count

    gap_count = 0
    for row in read_csv(DEFAULT_GAP_LIVE):
        signal = gap_replacement_signal(row, target_date)
        if signal is None:
            continue
        gap_count += 1
        existing = merged.get(signal.key)
        if existing is None:
            merged[signal.key] = signal
        else:
            for label in signal.labels:
                if label == "HARD FLIP" and existing.section == "CORE":
                    label = "APPROVED MASTERS FLIP"
                    if "approved Hard/Masters side-flip" not in existing.selection:
                        existing.selection += " | approved Hard/Masters side-flip"
                if label not in existing.labels:
                    existing.labels.append(label)
    lane_counts["GUARD EXPANSION"] = gap_count

    props = props_signals(target_date)
    lane_counts["ACES/DF"] = len(props)
    for signal in props:
        merged.setdefault(signal.key, signal)

    signals = sorted(
        merged.values(),
        key=lambda signal: (
            signal.priority,
            -(signal.edge_pct if signal.edge_pct is not None else -999.0),
            signal.match,
        ),
    )
    empty = [lane.label for lane in LANES if lane_counts.get(lane.label, 0) == 0]
    if lane_counts.get("ACES/DF", 0) == 0:
        empty.append("ACES/DF")
    if lane_counts.get("GUARD EXPANSION", 0) == 0:
        empty.append("GUARD EXPANSION")
    return signals, empty


def render_messages(
    target_date: str,
    signals: list[Signal],
    empty_lanes: list[str],
    *,
    update_only: bool = False,
) -> list[str]:
    display_date = date.fromisoformat(target_date).strftime("%a %d %b").upper()
    title = "IL MARGINE TENNIS SIGNAL UPDATE" if update_only else "IL MARGINE TENNIS SIGNALS"
    header = f"{title} - {display_date}\nGenerated from the latest completed odds refresh."
    if update_only:
        header += "\nOnly selections not included in the earlier alert are shown."
    blocks: list[str] = []
    current_section = ""
    for signal in signals:
        if signal.section != current_section:
            current_section = signal.section
            blocks.append(f"\n{current_section}")
        label = "/".join(signal.labels)
        blocks.append(f"[{label}] {signal.match}\n{signal.selection}")
    if not signals:
        blocks.append("\nNo qualifying signals today.")
    if empty_lanes:
        blocks.append("\nNo signals: " + ", ".join(empty_lanes))
    blocks.append(
        "\nStatus guide: CORE and TRACKED EXPANSION are betting lanes at the stake shown. "
        "APPROVED MASTERS FLIP is a scoped Strict bet. PROVISIONAL selections are 0.5u "
        "forward trials. SHADOW/RESEARCH and WATCHLIST rows are evidence only, not bets."
    )

    messages: list[str] = []
    current = header
    for block in blocks:
        candidate = current + "\n" + block
        if len(candidate) <= TELEGRAM_LIMIT:
            current = candidate
            continue
        messages.append(current)
        current = f"{title} - {display_date} (continued)\n{block}"
    messages.append(current)
    return messages


def load_state(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def signal_generation_is_ready(path: Path, target_date: str) -> bool:
    state = load_state(path)
    return state.get("date") == target_date and state.get("status") == "ok"


def signal_id(signal: Signal) -> str:
    return "|".join(signal.key)


def new_signals_since_state(
    signals: list[Signal], state: dict[str, object], target_date: str
) -> list[Signal]:
    if state.get("date") != target_date:
        return signals
    previous = state.get("signal_ids")
    if not isinstance(previous, list):
        # A legacy state cannot prove which individual selections were sent.
        return signals
    previous_ids = {str(value) for value in previous}
    return [signal for signal in signals if signal_id(signal) not in previous_ids]


def github_token() -> str:
    for name in ("GH_TOKEN", "GITHUB_TOKEN"):
        token = os.environ.get(name, "").strip()
        if token:
            return token

    errors: list[str] = []
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        token = result.stdout.strip()
        if result.returncode == 0 and token:
            return token
        errors.append(f"gh auth token exit {result.returncode}")
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        errors.append(f"gh auth token: {type(exc).__name__}")

    try:
        result = subprocess.run(
            ["git", "credential-manager", "get"],
            input="protocol=https\nhost=github.com\n\n",
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        fields: dict[str, str] = {}
        for line in result.stdout.splitlines():
            key, separator, value = line.partition("=")
            if separator:
                fields[key.strip()] = value.strip()
        token = fields.get("password", "")
        if result.returncode == 0 and token:
            return token
        errors.append(f"credential-manager exit {result.returncode}")
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        errors.append(f"credential-manager: {type(exc).__name__}")

    raise RuntimeError("GitHub authentication unavailable (" + "; ".join(errors) + ")")


def dispatch(messages: list[str], *, repository: str, workflow: str, ref: str) -> None:
    encoded = base64.b64encode(json.dumps(messages, ensure_ascii=False).encode("utf-8")).decode("ascii")
    try:
        result = subprocess.run(
            [
                "gh",
                "workflow",
                "run",
                workflow,
                "--repo",
                repository,
                "--ref",
                ref,
                "--json",
            ],
            input=json.dumps({"payload_b64": encoded}),
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        if result.returncode == 0:
            print("GitHub Telegram relay dispatched via gh CLI.")
            return
        gh_error = (result.stderr or result.stdout).strip()[:300]
        print(f"WARNING: gh relay dispatch failed; using HTTP fallback: {gh_error}", file=sys.stderr)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        print(f"WARNING: gh relay dispatch unavailable; using HTTP fallback: {type(exc).__name__}", file=sys.stderr)

    token = github_token()
    payload = json.dumps({"ref": ref, "inputs": {"payload_b64": encoded}}).encode("utf-8")
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repository}/actions/workflows/{workflow}/dispatches",
        data=payload,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "il-margine-tennis-digest",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"GitHub Telegram relay dispatch failed: HTTP {exc.code} {detail}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"GitHub Telegram relay dispatch failed: {exc}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Send today's local tennis signal digest to Telegram")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--state", default=str(DEFAULT_STATE))
    parser.add_argument("--ready-state", default=str(DEFAULT_READY_STATE))
    parser.add_argument("--repository", default=os.environ.get("TENNIS_DIGEST_GITHUB_REPOSITORY", DEFAULT_REPOSITORY))
    parser.add_argument("--workflow", default=DEFAULT_WORKFLOW)
    parser.add_argument("--ref", default=os.environ.get("TENNIS_DIGEST_GITHUB_REF", DEFAULT_REF))
    parser.add_argument("--require-ready", action="store_true")
    parser.add_argument("--print-only", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--new-only",
        action="store_true",
        help="For a second same-day pass, send only selections absent from the earlier alert.",
    )
    args = parser.parse_args()

    try:
        date.fromisoformat(args.date)
    except ValueError as exc:
        raise SystemExit(f"Invalid --date: {args.date}") from exc

    if args.require_ready and not signal_generation_is_ready(Path(args.ready_state), args.date):
        print(f"Telegram digest skipped: signal generation is not ready for {args.date}.")
        return 0

    signals, empty_lanes = collect_signals(args.date)
    messages = render_messages(args.date, signals, empty_lanes)
    rendered = "\n\n--- MESSAGE BREAK ---\n\n".join(messages) + "\n"
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(rendered, encoding="utf-8")
    print(rendered, end="")

    digest_hash = hashlib.sha256(json.dumps(messages, ensure_ascii=False).encode("utf-8")).hexdigest()
    state_path = Path(args.state)
    state = load_state(state_path)
    if args.print_only:
        print(f"Digest preview only: {len(signals)} unique signals in {len(messages)} message(s)")
        return 0
    if not args.force and state.get("date") == args.date and state.get("digest_hash") == digest_hash:
        print("Telegram digest unchanged; dispatch skipped.")
        return 0

    dispatch_signals = signals
    dispatch_messages = messages
    if args.new_only and not args.force:
        dispatch_signals = new_signals_since_state(signals, state, args.date)
        if not dispatch_signals:
            preserved_dispatch = {}
            if state.get("date") == args.date and state.get("dispatched_at"):
                preserved_dispatch["dispatched_at"] = state["dispatched_at"]
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(
                json.dumps(
                    {
                        **preserved_dispatch,
                        "date": args.date,
                        "digest_hash": digest_hash,
                        "messages": len(messages),
                        "signal_ids": [signal_id(signal) for signal in signals],
                        "updated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            print("Telegram digest has no new selections; dispatch skipped.")
            return 0
        dispatch_messages = render_messages(args.date, dispatch_signals, [], update_only=True)

    dispatch(dispatch_messages, repository=args.repository, workflow=args.workflow, ref=args.ref)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(
            {
                "date": args.date,
                "digest_hash": digest_hash,
                "messages": len(messages),
                "signal_ids": [signal_id(signal) for signal in signals],
                "dispatched_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        f"Telegram relay dispatched: {len(dispatch_signals)} new unique signals "
        f"in {len(dispatch_messages)} message(s)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
