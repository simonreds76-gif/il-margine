"""Read-only reporting of frozen ace/DF contracts. No prices or forecasts change."""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

RELATIVE = Path('data/tennis-props/shadow/full-refresh-v1')
ARMS = ('control', 'candidate')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def label(line, side):
    if side == 'OVER' and line % 1 == .5:
        return f'{math.floor(line) + 1}+'
    return f'{side.title()} {line:g}'


def breakdown(records, outcomes):
    groups = defaultdict(list)
    for record in records:
        row = record['row']
        for side in ('OVER', 'UNDER'):
            if side in record['control'] and side in record['candidate']:
                groups[(row['market'], row['tour'], side, float(row['line']))].append(record)
    result = []
    for (market, tour, side, line), rows in sorted(groups.items()):
        item = dict(market=market, tour=tour, side=side, line=line, label=label(line, side),
                    quoted=len(rows), fixtures=len({r['fixture_key'] for r in rows}))
        for arm in ARMS:
            selected = [r for r in rows if r[arm + '_side'] == side]
            m = dict(selected=len(selected), settled=0, wins=0, losses=0, pushes=0,
                     pending=0, void=0, stake_units=0, pnl_units=0., roi_pct=None)
            for r in selected:
                outcome = outcomes.get(r['id'], {})
                if outcome.get('status') == 'void':
                    m['void'] += 1
                elif outcome.get('status') == 'settled':
                    actual = float(outcome['actual'])
                    odds = float(r['row'][side.lower() + '_odds'])
                    win = actual > line if side == 'OVER' else actual < line
                    m['settled'] += 1
                    m['stake_units'] += 1
                    if actual == line:
                        m['pushes'] += 1
                    elif win:
                        m['wins'] += 1
                        m['pnl_units'] += odds - 1
                    else:
                        m['losses'] += 1
                        m['pnl_units'] -= 1
                else:
                    m['pending'] += 1
            if m['stake_units']:
                m['roi_pct'] = 100 * m['pnl_units'] / m['stake_units']
            item[arm] = m
        result.append(item)
    return result


def build(folder):
    report = json.loads((folder / 'report.json').read_text(encoding='utf-8'))
    records = []
    previous = ''
    for line in (folder / 'observations.jsonl').read_text(encoding='utf-8').splitlines():
        row = json.loads(line)
        own = row.pop('hash')
        if row.get('previous_hash') != previous or digest(row) != own:
            raise ValueError('Frozen ledger integrity failure')
        previous = own
        records.append(row)
    outcomes = json.loads((folder / 'outcomes.json').read_text(encoding='utf-8'))
    from tennis_event_integrity import revision_records
    records, archived = revision_records(records, report.get('implementation_revision'))
    archive_reports = report.get('archived_revisions') or ([report['archived_revision']] if report.get('archived_revision') else [])
    archive_by_hash = {r['config_hash']: r for r in archive_reports}
    if len(archived) != sum(m['registered'] for a in archive_reports for m in a.get('markets', {}).values()):
        raise ValueError('Archived report and ledger differ')
    if any(r['config_hash'] not in archive_by_hash for r in archived):
        raise ValueError('Unregistered archived experiment configuration')
    for config_hash, archive in archive_by_hash.items():
        if sum(r['config_hash']==config_hash for r in archived) != sum(m['registered'] for m in archive['markets'].values()):
            raise ValueError('Archived cohort count differs')
    if len(records) != sum(m['registered'] for m in report['markets'].values()):
        raise ValueError('Report and ledger differ; rerun after the collector completes')
    if any(r['config_hash'] != report['config_hash'] for r in records):
        raise ValueError('Mixed experiment configuration')
    result = {k: v for k, v in report.items() if k != 'pending_rows'}
    if archived:
        result['archived_revisions'] = [dict(a, milestones=breakdown([r for r in archived if r['config_hash']==a['config_hash']], outcomes)) for a in archive_reports]
        result['archived_revision'] = result['archived_revisions'][0] if len(archive_reports)==1 else None
    result.update(milestones=breakdown(records, outcomes), reporting_version=1,
                  reporting_generated_at=datetime.now(timezone.utc).isoformat(),
                  ledger_head=previous)
    return result


def load_summary(root):
    folder = root / RELATIVE
    try:
        summary = json.loads((folder / 'milestones.json').read_text(encoding='utf-8'))
        if not summary.get('markets') or 'milestones' not in summary:
            raise ValueError('Milestone summary is incomplete')
        if (folder / 'report.json').exists():
            current = json.loads((folder / 'report.json').read_text(encoding='utf-8'))
            if summary.get('generated_at') != current.get('generated_at'):
                return dict(status='REPORT_OUTDATED', markets={}, error='Milestone report has not caught up with the collector')
        return summary
    except (OSError, ValueError) as exc:
        return dict(status='SOURCE_MISSING', markets={}, error=str(exc))


def text(summary):
    if not summary.get('markets'):
        return 'Full input refresh: ' + summary.get('status', 'SOURCE_MISSING') + '; performance unavailable.'
    retired = summary.get('status') == 'SOURCE_UPGRADE_APPLIED_SETTLING'
    lines = ['Input upgrade applied | retained paper comparison' if retired else 'Full input refresh | paper tracking only',
             'Evidence: ' + str(summary.get('generated_at', 'unknown'))]
    try:
        age = datetime.now(timezone.utc) - datetime.fromisoformat(summary['generated_at'].replace('Z', '+00:00'))
        if age.total_seconds() > 48 * 3600:
            lines.append('STALE: source evidence is over 48 hours old.')
    except (KeyError, ValueError, TypeError):
        lines.append('Source freshness unavailable.')
    if retired:
        lines.append('Current OnCourt history is the standard input. New comparison capture retired; pending forecasts still settle.')
    if summary.get('error') or summary.get('status') == 'BLOCKED':
        lines.append('Collector needs attention: ' + str(summary.get('error') or summary['status']))
    if summary.get('implementation_revision'):
        lines.append('Current data version: ' + summary['implementation_revision'])
    archives = summary.get('archived_revisions') or ([summary['archived_revision']] if summary.get('archived_revision') else [])
    if archives:
        old = sum(g.get('registered', 0) for a in archives for g in a['markets'].values())
        lines.append(f'{old} earlier quotes are retained in the separate pre-repair record.')
    for market, group in summary['markets'].items():
        name = 'Aces' if market == 'aces' else 'Double faults'
        lines.append(f"{name}: {group.get('settled', 0)} settled quotes, {group.get('pending', 0)} pending, {group.get('overdue', 0)} overdue; {group.get('independent_fixtures', 0)}/200 settled matches, {group.get('tournaments', 0)}/4 tournaments, {group.get('age_days', 0)}/56 days.")
        for arm in ARMS:
            m = group.get(arm, {})
            roi = f"{m['roi_pct']:+.1f}%" if m.get('roi_pct') is not None else 'awaiting settlement'
            lines.append(f"{'Old history' if arm == 'control' else 'Updated history'}: ROI {roi}, {m.get('pnl_units', 0):+.2f}u, W/L/P {m.get('wins', 0)}/{m.get('losses', 0)}/{m.get('pushes', 0)}, {m.get('stake_units', 0)}u settled stake.")
    lines.append('Milestones with selected paper bets (current / refreshed):')
    for row in summary.get('milestones', []):
        if not any(row[a]['selected'] for a in ARMS):
            continue
        values = []
        for a in ARMS:
            m = row[a]
            roi = f"{m['roi_pct']:+.1f}%" if m['roi_pct'] is not None else 'pending'
            values.append(f"{roi}, {m['pnl_units']:+.2f}u, {m['settled']} settled/{m['pending']} pending")
        lines.append(f"{row['tour']} {'aces' if row['market'] == 'aces' else 'DF'} {row['label']}: " + ' / '.join(values))
    lines.append('One paper unit per selected line. Milestones on the same match are correlated. No automatic promotion.')
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--folder', type=Path, default=Path(__file__).resolve().parents[1] / RELATIVE)
    args = parser.parse_args()
    # Share the collector lock without importing or changing its frozen implementation.
    import os
    lock = args.folder / '.writer.lock'
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        result = build(args.folder)
        target = args.folder / 'milestones.json'
        temp = target.with_suffix('.tmp')
        temp.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
        temp.replace(target)
        print(f"Milestone reporting: {len(result['milestones'])} market/tour/side/line groups")
    finally:
        os.close(fd)
        lock.unlink()


if __name__ == '__main__':
    main()
