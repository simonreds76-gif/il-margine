"""Small display-only daily histories. Never settle, reselect or write model records."""
from __future__ import annotations

import importlib.util
import json
import math
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path


def load_module(root, filename, name):
    spec = importlib.util.spec_from_file_location(name, root / 'scripts' / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def daily(entries, note):
    grouped = defaultdict(lambda: [0.0, 0])
    for day, profit in entries:
        day = str(day)[:10]
        if date.fromisoformat(day).isoformat() != day or not math.isfinite(profit):
            raise ValueError('Invalid dated result')
        grouped[day][0] += profit
        grouped[day][1] += 1
    cumulative = 0.0
    days = []
    for day, (profit, count) in sorted(grouped.items()):
        cumulative += profit
        days.append(dict(date=day, profit=round(profit, 6), cumulative=round(cumulative, 6), settled=count))
    return dict(days=days, settled=sum(v[1] for v in grouped.values()), profit=round(cumulative, 6), omitted=0, note=note)


def strict_history(root, tag, module):
    path = root / 'data/backtest' / f'strict-signals{tag}-archive.csv'
    rows = module.dedupe_rows(module.load_csv_rows(path))
    rows = [r for r in rows if not module.is_performance_audit_row(r)]
    cutoff = module.infer_clean_eval_start(path, None)
    entries = []
    for row in rows:
        day = module.parse_iso_date(row.get('date'))
        if day is None or day < cutoff or module.norm_key_val(row.get('policy_mode') or 'base') != 'base' or not module.is_settled(row):
            continue
        # Reuse the existing report arithmetic and its historical stake policy.
        # This does not regrade outcomes or change any ledger cell.
        summary = module.summarize_mode([row], 'base')
        if summary.settled != 1 or summary.invalid_odds:
            raise ValueError('Report row cannot be represented')
        entries.append((row.get('match_date') or row['date'], summary.pnl_units))
    return daily(entries, 'Same current-policy cohort and stake convention as the headline report. Voids contribute zero profit; pending selections are excluded.')


def provisional_histories(root, module):
    shared = set()
    backtest = root / 'data/backtest'
    for tag in ('', '-volume200', '-grass_bo3', '-clay_bo3', '-cpi_speed'):
        for row in module.read(backtest / f'strict-signals{tag}-archive.csv'):
            if row.get('side') in {'P1', 'P2'} and row.get('bet_type') != 'spread':
                shared.add(module.fixture_key(row)[:3])
    groups = {k: {} for k in ('provisional_hard', 'provisional_expansion')}
    rows = sorted(module.read(backtest / 'tennis-model-market-gap-archive.csv'), key=lambda r: (r.get('captured_at') or r.get('date') or '', r.get('time_utc', '')))
    for row in rows:
        lane = module.provisional_lane(row)
        if lane:
            groups[lane].setdefault(module.fixture_key(row), row)
    output = {}
    for lane, records in groups.items():
        entries = []
        for key, row in records.items():
            if key[:3] in shared:
                continue
            odds = module.num(row.get('selected_odds'))
            capture = row.get('captured_at', '')[:10]
            day = row.get('match_date')
            if odds is None or odds <= 1 or (row.get('settlement_status') == 'settled' and capture and day and capture > day):
                continue
            outcome = row.get('bet_outcome')
            if row.get('settlement_status') == 'settled' and row.get('settlement_version') == '2' and outcome in ('WIN', 'LOSS'):
                entries.append((day, .5 * (odds - 1 if outcome == 'WIN' else -1)))
        output[lane] = daily(entries, 'Reconstructed selections at the original first recorded price and 0.5u convention. Not verified forward bets or Telegram delivery.')
    return output


def astra_history(root):
    folder = root / 'data/tennis-ml-research/context-forward-v1'
    report = json.loads((folder / 'report.json').read_bytes())
    outcomes = json.loads((folder / 'outcomes.json').read_bytes())
    entries = []
    for path in sorted((folder / 'captures').glob('*.json')):
        row = json.loads(path.read_bytes())
        selection = row.get('candidate_selection')
        result = outcomes.get(row['fixture_key'])
        if row.get('input_contract', 'legacy-unversioned') != report['active_input_contract'] or not selection or not result:
            continue
        won = row['players'][selection['side']] == result['winner_id']
        entries.append((result['date'], selection['paper_stake'] * (selection['odds'] - 1 if won else -1)))
    return daily(entries, 'Frozen candidate, current corrected input contract only. Uses existing exact-fixture settlements; historical replay excluded.')


def build_admin_profit_histories(root: Path):
    output = {}
    try:
        module = load_module(root, 'strict-policy-performance.py', 'admin_profit_strict')
        for lane, tag in [('strict', ''), ('volume_200', '-volume200'), ('challenger', '-challenger-ml-v2'), ('spread_v1', '-spreadv1')]:
            try:
                output[lane] = strict_history(root, tag, module)
            except (OSError, ValueError, KeyError, TypeError):
                output[lane] = {'message': 'Dated selection history is unavailable; headline record retained.'}
    except (OSError, ImportError, ValueError):
        pass
    try:
        output.update(provisional_histories(root, load_module(root, 'tennis_provisional_performance.py', 'admin_profit_provisional')))
    except (OSError, ImportError, ValueError, KeyError, TypeError):
        pass
    try:
        output['astra'] = astra_history(root)
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return output
