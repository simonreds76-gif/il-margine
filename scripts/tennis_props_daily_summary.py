"""One daily paper-ace report through the existing private Telegram relay.

This reports existing evidence only. It never registers bets, fits a model,
changes stakes, fetches odds or adds a scheduler.
"""
from __future__ import annotations

import csv
from datetime import date, datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

from tennis_props_current_history import VERSION

REPORT = 'data/tennis-props/backtest/aces-over-v4-weekly-report.json'
LEDGER = 'data/tennis-props/shadow/aces-over-v4-observations.csv'
STATE = 'data/tennis-props/shadow/aces-over-v4-daily-telegram-state.json'
PREVIEW = 'data/tennis-props/backtest/aces-over-v4-daily-summary.txt'


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, dict):
        raise ValueError(f'Expected an object: {path.name}')
    return value


def number(value: object) -> float | None:
    try:
        result = float(str(value))
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def metrics(rows: list[dict], previous_ids: set[str]) -> dict:
    settled = [r for r in rows if r.get('settlement_status') == 'settled']
    paper = [r for r in rows if r.get('phase') == 'WALK_FORWARD' and r.get('v4_signal') == 'true']
    settled_paper = [r for r in paper if r.get('settlement_status') == 'settled']
    valid_paper = [r for r in settled_paper if number(r.get('pnl')) is not None and r.get('result') in {'win','loss','push'}]
    profit = sum(number(r['pnl']) or 0 for r in valid_paper)
    ids = sorted(r['observation_id'] for r in settled if r.get('observation_id'))
    fixture_keys = {r.get('event_id') or '|'.join([r.get('date',''), *sorted([r.get('player',''),r.get('opponent','')])]) for r in settled}
    return dict(
        registered=len(rows), settled=len(settled), settled_fixtures=len(fixture_keys),
        pending=sum(r.get('settlement_status') == 'pending' for r in rows),
        void=sum(r.get('settlement_status') == 'void' for r in rows),
        newly_settled=len(set(ids)-previous_ids), settled_ids=ids,
        paper_settled=len(valid_paper), paper_pending=sum(r.get('settlement_status') == 'pending' for r in paper),
        wins=sum(r.get('result') == 'win' for r in valid_paper), losses=sum(r.get('result') == 'loss' for r in valid_paper),
        pushes=sum(r.get('result') == 'push' for r in valid_paper), profit=profit,
        roi=profit/len(valid_paper)*100 if valid_paper else None,
        invalid_paper=len(settled_paper)-len(valid_paper),
    )


def build(root: Path, target_day: str, previous: dict) -> tuple[str, dict]:
    report = read_json(root/REPORT)
    history = read_json(root/'data/tennis-props/player-history-status.json')
    health = read_json(root/'data/tennis-props/pipeline-health.json')
    rows = []
    if (root/LEDGER).exists():
        with (root/LEDGER).open(encoding='utf-8-sig', newline='') as handle:
            rows = list(csv.DictReader(handle))
    current = [r for r in rows if r.get('history_version') == VERSION]
    older = [r for r in rows if r.get('history_version') != VERSION]
    earlier = set(previous.get('settled_ids') or [])
    current_stats = metrics(current, earlier)
    older_stats = metrics(older, set())
    warning = []
    if history.get('state') != 'CURRENT' or history.get('version') != VERSION or history.get('as_of') != target_day:
        warning.append('Player inputs have not passed today\'s freshness check.')
    try:
        generated = datetime.fromisoformat(str(report.get('generated_at') or '').replace('Z','+00:00'))
        if generated.tzinfo is None or generated.astimezone(ZoneInfo('Europe/London')).date().isoformat() != target_day:
            warning.append('The ace report has not refreshed today.')
    except ValueError:
        warning.append('The ace report is missing or has no valid update time.')
    if len(rows) != report.get('rows_registered') or sum(r.get('settlement_status')=='settled' for r in rows) != report.get('rows_settled'):
        warning.append('Report and saved observations disagree; review the refresh.')
    if health.get('as_of') != target_day or health.get('structural_error') or health.get('state') in {'CORE_RUN_IN_PROGRESS','CORE_RUN_FAILED','PLAYER_HISTORY_BLOCKED','PLAYER_HISTORY_COMPARISON_STALE'}:
        warning.append('The props pipeline needs a health check.')
    if current_stats['invalid_paper']:
        warning.append(f"{current_stats['invalid_paper']} settled paper selections have incomplete results and are excluded from ROI.")

    title = date.fromisoformat(target_day).strftime('%d %B %Y')
    lines = [f'PAPER ACE MODEL DAILY | {title}', 'ATP Aces Over v4 | paper only, no real stake', '']
    if warning:
        lines.extend(['DATA CHECK: '+ ' '.join(warning), 'Figures below are the last recorded evidence, not a fresh betting signal.', ''])
    lines.extend([
        'CORRECTED PLAYER INPUTS',
        f"{current_stats['registered']} forecasts | {current_stats['settled']} settled across {current_stats['settled_fixtures']} matches | {current_stats['pending']} pending | {current_stats['void']} void",
        (f"New settlements since the previous daily summary: {current_stats['newly_settled']}" if previous.get('date') else 'Daily tracking starts with this summary; existing settlements are not counted as new today.'),
    ])
    if current_stats['roi'] is None:
        lines.append('Paper bets: none settled yet. W/L, profit and ROI start when qualifying selections settle.')
    else:
        lines.append(f"Paper bets: {current_stats['wins']}W / {current_stats['losses']}L / {current_stats['pushes']} push | {current_stats['paper_pending']} pending")
        lines.append(f"Profit {current_stats['profit']:+.2f}u | ROI {current_stats['roi']:+.2f}% | {current_stats['paper_settled']}u settled paper stake")
        lines.append('1u is one equal paper stake per selection; voids are excluded.')
    # Fitting must use the same input and frozen-model version as the new row.
    gate = read_json(root/'data/tennis-props/backtest/aces-dfs-v3-all-tour-gate.json')
    relative = ((gate.get('deployment_safe_aces') or {}).get('ATP') or {}).get('model_path')
    model_file = root/str(relative) if relative else None
    model_hash = hashlib.sha256(model_file.read_bytes()).hexdigest() if model_file and model_file.is_file() else None
    cutoff = date.fromisoformat(target_day).replace(day=1).isoformat()
    fit_ready = [r for r in current if model_hash and r.get('model_sha256') == model_hash and r.get('settlement_status')=='settled'
                 and r.get('date','9999') < cutoff and all(number(r.get(f)) is not None for f in ('actual','mu_v3','mu_mkt'))]
    minimum = int(report.get('minimum_prefit_settled') or 200)
    lines.append(f"Training sample eligible this month: {len(fit_ready)}/{minimum} earlier settled forecasts using these inputs and the same model.")
    if not model_hash:
        lines.append('The frozen model file could not be verified; training readiness is unconfirmed.')
    lines.extend(['', f"EARLIER INPUTS: {older_stats['registered']} forecasts | {older_stats['settled']} settled | {older_stats['pending']} pending | {older_stats['void']} void. Kept separate."])
    milestones = [n for n in (50,100,200,600) if current_stats['settled'] >= n and n not in (previous.get('milestones') or [])]
    if milestones:
        lines.append('REVIEW MILESTONE: '+', '.join(map(str,milestones))+' corrected-input forecasts settled. Review evidence; no automatic promotion.')
    lines.append('Monitor: https://ilmargine.bet/model-monitor/tennis-props?tab=shadow')
    message = '\n'.join(lines)
    if len(message)>3800:
        raise ValueError('Paper summary exceeds the existing Telegram relay limit')
    state = dict(date=target_day, history_version=VERSION, settled_ids=current_stats['settled_ids'],
                 milestones=sorted(set(previous.get('milestones') or [])|set(milestones)),
                 summary_sha256=hashlib.sha256(message.encode()).hexdigest(),
                 current_metrics={k:v for k,v in current_stats.items() if k!='settled_ids'},
                 health_warnings=warning)
    return message, state


def daily_summary(root: Path, target_day: str, sender: Callable[[list[str]], None], *, print_only: bool=False) -> str:
    state_path=root/STATE
    previous=read_json(state_path)
    if previous.get('date')==target_day and previous.get('relay_accepted_at') and not print_only:
        print('Paper ace daily summary already dispatched for this day; skipped.')
        return 'already_dispatched'
    # Reject accidental historical replay as a current alert; explicit previews remain available.
    if not print_only and target_day!=datetime.now(ZoneInfo('Europe/London')).date().isoformat():
        raise ValueError('Daily paper alerts must use the current UK date')
    message,state=build(root,target_day,previous)
    report_path=root/PREVIEW
    report_path.parent.mkdir(parents=True,exist_ok=True)
    report_path.write_text(message+'\n',encoding='utf-8')
    print(message)
    if print_only:
        return 'preview'
    sender([message])
    # Record acceptance only after successful relay dispatch. Failed dispatches can retry.
    state['relay_accepted_at']=datetime.now(timezone.utc).isoformat()
    state_path.parent.mkdir(parents=True,exist_ok=True)
    temporary=state_path.with_suffix('.tmp')
    temporary.write_text(json.dumps(state,indent=2)+'\n',encoding='utf-8')
    temporary.replace(state_path)
    print('Paper ace daily summary accepted by the existing private Telegram relay.')
    return 'dispatched'
