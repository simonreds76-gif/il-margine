"""Fresh qualifying v4 paper selections through the existing private relay.

Reads frozen observations. Does not fit, register, settle or change any bet.
"""
from __future__ import annotations

from collections import Counter
import csv
from datetime import date, datetime, timedelta, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Callable
from zoneinfo import ZoneInfo

from tennis_props_daily_summary import LEDGER, REPORT, VERSION, build, metrics, number, read_json

STATE = 'data/tennis-props/shadow/aces-over-v4-selection-alert-state.json'
PREVIEW = 'data/tennis-props/backtest/aces-over-v4-selection-alerts.txt'
STATUS = 'data/tennis-props/backtest/aces-over-v4-selection-alert-status.json'
UK = ZoneInfo('Europe/London')


def timestamp(value: object) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else None
    except (TypeError, ValueError):
        return None


def verify_ledger(root: Path, rows: list[dict]):
    """Use the producer's exact integrity contract and fixed eligibility rules."""
    path = root/'scripts/tennis-props-aces-over-v4.py'
    spec = importlib.util.spec_from_file_location('tennis_props_v4_alert_integrity', path)
    if not spec or not spec.loader:
        raise RuntimeError('The v4 integrity checker is unavailable')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.assert_integrity(rows)
    return module.MIN_PREFIT_SETTLED, module.SIGNAL_EDGE_PCT, module.MAX_CAPTURE_AGE_HOURS


def clean(value: object) -> str:
    return ' '.join(str(value or '').split())[:150]


def selection_problem(row: dict, now: datetime, model_hash: str, minimum: int, edge_floor: float, max_age: float) -> str | None:
    if row.get('history_version') != VERSION or row.get('model_sha256') != model_hash:
        return 'EARLIER_INPUTS_OR_MODEL'
    if row.get('phase') != 'WALK_FORWARD':
        return 'INITIAL_CALIBRATION_NOT_READY'
    if row.get('settlement_status') != 'pending' or row.get('v4_signal') != 'true':
        return 'NOT_AN_OPEN_SELECTION'
    if row.get('tour') != 'ATP' or row.get('market') != 'aces':
        return 'WRONG_MARKET'
    if not all(row.get(key) for key in ('observation_id', 'event_id', 'player', 'opponent', 'bookmaker', 'history_fingerprint')):
        return 'INCOMPLETE_IDENTITY'
    start, capture, registered = (timestamp(row.get(key)) for key in ('match_start_utc', 'capture_ts', 'registered_at_utc'))
    if not start or not capture or not registered:
        return 'UNCONFIRMED_TIME'
    if not capture <= registered <= now < start:
        return 'NOT_FRESH_PREMATCH'
    if start > now + timedelta(days=3) or now-capture > timedelta(hours=max_age):
        return 'OUTSIDE_FRESH_WINDOW'
    if row.get('history_as_of') != now.astimezone(UK).date().isoformat():
        return 'OLDER_PLAYER_HISTORY'
    training_n = number(row.get('fit_training_n'))
    try:
        cutoff = date.fromisoformat(row.get('fit_cutoff', ''))
        forecast_date = date.fromisoformat(row.get('date', ''))
    except ValueError:
        return 'INVALID_FIT_CUTOFF'
    if training_n is None or training_n < minimum or cutoff != forecast_date.replace(day=1):
        return 'INITIAL_CALIBRATION_NOT_READY'
    line, odds, probability, push, edge = (number(row.get(key)) for key in ('line', 'selected_odds', 'p_over_v4', 'p_push_v4', 'edge_v4_pct'))
    if any(value is None for value in (line, odds, probability, push, edge)):
        return 'INCOMPLETE_PRICE_OR_FORECAST'
    if line < 0 or not (line*2).is_integer() or odds <= 1 or not 0 < probability < 1 or not 0 <= push < 1 or probability+push > 1:
        return 'INVALID_PRICE_OR_FORECAST'
    if edge < edge_floor or abs((probability*odds+push-1)*100-edge) > .1:
        return 'EDGE_CHECK_FAILED'
    return None


def prepare(root: Path, now: datetime, previous: dict) -> tuple[list[tuple[str, str]], dict]:
    target_day = now.astimezone(UK).date().isoformat()
    _, summary = build(root, target_day, {})
    warnings = list(summary['health_warnings'])
    report = read_json(root/REPORT)
    updated = timestamp(report.get('generated_at'))
    if not updated or not timedelta(0) <= now-updated <= timedelta(hours=6):
        warnings.append('The v4 report is older than six hours or has an invalid timestamp.')
    status = dict(checked_at=now.isoformat(), history_version=VERSION, eligible=0, new=0, excluded={}, warnings=warnings)
    if warnings:
        return [], dict(status, state='BLOCKED_DATA_CHECK')
    with (root/LEDGER).open(encoding='utf-8-sig', newline='') as handle:
        rows = list(csv.DictReader(handle))
    minimum, edge_floor, max_age = verify_ledger(root, rows)
    gate = read_json(root/'data/tennis-props/backtest/aces-dfs-v3-all-tour-gate.json')
    relative = ((gate.get('deployment_safe_aces') or {}).get('ATP') or {}).get('model_path')
    if not relative:
        raise ValueError('No frozen ATP model is configured')
    model_hash = hashlib.sha256((root/relative).read_bytes()).hexdigest()
    stats = metrics([r for r in rows if r.get('history_version') == VERSION and r.get('model_sha256') == model_hash], set())
    if stats['invalid_paper']:
        return [], dict(status, state='BLOCKED_DATA_CHECK', warnings=['Some settled v4 selections have incomplete results.'])
    record = ('Current model record: no settled paper selections yet.' if stats['roi'] is None else
              f"Current model: {stats['wins']}W / {stats['losses']}L / {stats['pushes']} push | {stats['paper_settled']} settled | "
              f"P/L {stats['profit']:+.2f}u | ROI {stats['roi']:+.2f}%")
    sent = previous.get('sent') or {}
    messages = []
    excluded = Counter()
    for row in sorted(rows, key=lambda r: (r.get('match_start_utc', ''), r.get('observation_id', ''))):
        problem = selection_problem(row, now, model_hash, minimum, edge_floor, max_age)
        if problem:
            excluded[problem] += 1
            continue
        status['eligible'] += 1
        key = row['observation_id']
        if key in sent:
            excluded['ALREADY_DISPATCHED'] += 1
            continue
        line, probability, push = (float(row[key]) for key in ('line', 'p_over_v4', 'p_push_v4'))
        selection = f"{int(line+.5)}+ aces" if line % 1 == .5 else f"Over {line:g} aces (exactly {line:g} returns the stake)"
        start = timestamp(row['match_start_utc']).astimezone(UK)
        capture = timestamp(row['capture_ts'])
        text = '\n'.join([
            'ATP ACES OVER V4 | NEW PAPER SELECTION',
            f"{clean(row['player'])} vs {clean(row['opponent'])}",
            f"{clean(row.get('tournament'))} | {start:%d %b %H:%M %Z}",
            f"{clean(row['player'])}: {selection} @ {float(row['selected_odds']):g} ({clean(row['bookmaker'])})",
            f"Model probability {probability:.1%} | fair odds {(1-push)/probability:.2f} | estimated EV {float(row['edge_v4_pct']):+.1f}%",
            f"Odds captured {capture:%d %b %H:%M UTC}. Recheck the available price.",
            f"Player history verified {row['history_as_of']}.",
            '', record,
            'Recorded at 1u paper stake. Research only; no real stake assigned.',
            'Monitor: https://ilmargine.bet/model-monitor/tennis-props?tab=shadow',
        ])
        if len(text) > 3800:
            raise ValueError('v4 selection exceeds the Telegram relay limit')
        messages.append((key, text))
    return messages, dict(status, state='READY' if messages else 'NO_NEW_QUALIFYING_SELECTIONS', new=len(messages), excluded=dict(excluded))


def selection_alerts(root: Path, target_day: str, sender: Callable[[list[str]], None], *, print_only: bool = False, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    if target_day != now.astimezone(UK).date().isoformat():
        raise ValueError('v4 selection alerts must use the current UK date')
    path = root/STATE
    previous = read_json(path)
    try:
        messages, status = prepare(root, now, previous)
    except (OSError, ValueError, RuntimeError) as exc:
        write_json(root/STATUS, dict(state='BLOCKED_DATA_CHECK', checked_at=now.isoformat(), warnings=[str(exc)]))
        raise
    write_json(root/STATUS, status)
    preview = root/PREVIEW
    preview.parent.mkdir(parents=True, exist_ok=True)
    preview.write_text('\n\n'.join(text for _, text in messages) if messages else json.dumps(status, indent=2), encoding='utf-8')
    print(f"v4 selection alerts: {status['state']} | {len(messages)} new | {status['eligible']} eligible")
    if status['warnings']:
        print('Data check: '+' '.join(status['warnings']))
    if print_only:
        for _, text in messages:
            print(text)
        return 'preview'
    if status['state'] == 'BLOCKED_DATA_CHECK':
        raise RuntimeError('v4 alerts blocked: '+' '.join(status['warnings']))
    sent = dict(previous.get('sent') or {})
    # One relay batch avoids overlapping workflow dispatches replacing pending
    # GitHub jobs. Persist only after acceptance; never reset IDs each day.
    if messages:
        sender([text for _, text in messages])
    for key, text in messages:
        sent[key] = dict(relay_accepted_at=now.isoformat(), message_sha256=hashlib.sha256(text.encode()).hexdigest())
    if messages:
        write_json(path, dict(history_version=VERSION, sent=sent))
    return 'dispatched' if messages else 'no_new_selections'


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(payload, indent=2)+'\n', encoding='utf-8')
    temporary.replace(path)
