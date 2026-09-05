#!/usr/bin/env python3
"""Freeze full-board paired forecasts before kickoff; never publish betting picks.

Registration is append-only, timestamped and hash chained. Outcomes are written
separately. Missing or stale inputs produce explicit health reasons, not signals.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parents[1]
MODEL = runpy.run_path(str(ROOT / 'scripts/tennis-props-fresh-data-challenger.py'))
SETTLE = runpy.run_path(str(ROOT / 'scripts/tennis-props-settle-shadow.py'))
norm, stamp, numeric = (MODEL[k] for k in ('norm', 'stamp', 'numeric'))


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def read_json(path, default):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def atomic_json(path, value):
    temp = path.with_suffix(path.suffix + '.tmp')
    with temp.open('w', encoding='utf-8') as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)


@contextmanager
def lock(directory):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / '.writer.lock'
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        os.write(fd, str(os.getpid()).encode())
        yield
    finally:
        os.close(fd)
        path.unlink()


def ledger(path):
    records = []
    previous = ''
    if path.exists():
        for line in path.read_text(encoding='utf-8').splitlines():
            record = json.loads(line)
            own = record.pop('hash')
            if record.get('previous_hash') != previous or digest(record) != own:
                raise ValueError('Registration ledger integrity failure')
            record['hash'] = own
            records.append(record)
            previous = own
    return records


def append(path, records, record):
    record['previous_hash'] = records[-1]['hash'] if records else ''
    record['hash'] = digest(record)
    with path.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(record, sort_keys=True, ensure_ascii=False, allow_nan=False) + '\n')
        handle.flush()
        os.fsync(handle.fileno())
    records.append(record)


def contract_key(row):
    # Provider event IDs and postponed dates cannot create a second contract.
    return digest([row.get('tour'), str(row.get('date', ''))[:4],
                   MODEL['tournament_identity'](row.get('tournament')),
                   sorted([norm(row.get('player')), norm(row.get('opponent'))]),
                   norm(row.get('player')), row.get('market'), norm(row.get('bookmaker')),
                   numeric(row.get('line'))])


def eligibility(row, now, max_age_hours=6):
    capture, kickoff = stamp(row.get('capture_ts')), stamp(row.get('match_start_utc'))
    if not capture or not kickoff or not capture <= now < kickoff:
        return 'missing_timestamp_or_started'
    if (now - capture).total_seconds() > max_age_hours * 3600:
        return 'stale_capture'
    if row.get('matched_board') != 'yes':
        return 'no_board_match'
    if row.get('market') not in ('aces', 'double_faults') or row.get('tour') not in ('ATP', 'WTA'):
        return 'unsupported_market'
    if not all(row.get(k) for k in ('player', 'opponent', 'tournament', 'bookmaker', 'date', 'surface')):
        return 'missing_identity_or_surface'
    if row.get('distribution') != 'negative_binomial':
        return 'unsupported_distribution'
    values = {k: numeric(row.get(k)) for k in ('projection_mean', 'line', 'over_odds', 'under_odds', 'fair_p_over', 'fair_p_under', 'fair_p_push')}
    if any(v is None for v in values.values()):
        return 'incomplete_contract'
    if values['projection_mean'] <= 0 or values['line'] < 0 or min(values['over_odds'], values['under_odds']) <= 1:
        return 'invalid_contract'
    probs = [values[k] for k in ('fair_p_over', 'fair_p_under', 'fair_p_push')]
    if any(p < 0 or p > 1 for p in probs) or abs(sum(probs)-1) > .001:
        return 'invalid_control_probability'
    return None


def policy(predictions, threshold):
    side = max(('OVER', 'UNDER'), key=lambda s: predictions[s]['ev'])
    return side if predictions[side]['ev'] >= threshold else None


def source_manifest(source, tours, now, max_age_hours):
    paths = [source/'courts.csv'] + [source/f'{kind}_{tour.lower()}.csv' for tour in tours
                                   for kind in ('players','tours','games','stat')]
    manifest = {}
    for path in paths:
        if not path.exists():
            return None, 'source_file_missing'
        stat = path.stat()
        age = now.timestamp() - stat.st_mtime
        if age < -60 or age > max_age_hours*3600:
            return None, 'source_export_stale'
        manifest[path.name] = {'size':stat.st_size, 'mtime_ns':stat.st_mtime_ns}
    return manifest, None


def settle(records, source, outcomes, now):
    pending = [r for r in records if r['id'] not in outcomes and stamp(r['row']['match_start_utc']) < now]
    index = SETTLE['load_oncourt_index'](source, [r['row'] for r in pending])
    for record in pending:
        row = record['row']
        key = (row['tour'], int(row['date'][:4]), SETTLE['pair_key'](row['player'], row['opponent']))
        # Exact day and normalized event only. Ambiguity remains pending.
        candidates = [c for c in index.get(key, [])
                      if str(c.get('tourney_date')).replace('-', '')[:8] == row['date'].replace('-', '')
                      and MODEL['tournament_identity'](c.get('tourney_name')) == MODEL['tournament_identity'](row['tournament'])]
        unique = {digest(c): c for c in candidates}
        if len(unique) != 1:
            continue
        candidate = next(iter(unique.values()))
        if SETTLE['is_void_score'](candidate.get('score')):
            result = {'status': 'void', 'actual': None}
        else:
            actual, _ = SETTLE['market_count'](candidate, SETTLE['norm_text'](row['player']), row['market'])
            if actual is None:
                continue
            result = {'status': 'settled', 'actual': actual}
        outcomes[record['id']] = dict(result, settled_at=now.isoformat(), source='oncourt', source_hash=digest(candidate))


def report(records, outcomes, health, config, now):
    markets = {}
    for market in config['markets']:
        group = [r for r in records if r['row']['market'] == market]
        settled = [r for r in group if outcomes.get(r['id'], {}).get('status') == 'settled']
        metrics = {}
        for model in ('control', 'candidate'):
            pnl, bets, brier = 0., 0, []
            for r in settled:
                actual = outcomes[r['id']]['actual']
                row, predictions = r['row'], r[model]
                side = r[f'{model}_side']
                if side:
                    payoff, _ = MODEL['outcomes'](actual, float(row['line']), side, float(row[side.lower()+'_odds']))
                    pnl += payoff
                    bets += 1
                if actual != float(row['line']):
                    brier.append((predictions['OVER']['p_conditional'] - int(actual > float(row['line'])))**2)
            metrics[model] = {'bets': bets, 'pnl_units': pnl, 'roi_pct': 100*pnl/bets if bets else None,
                              'brier': sum(brier)/len(brier) if brier else None}
        fixtures = {r['fixture_key'] for r in settled}
        tournaments = {MODEL['tournament_identity'](r['row']['tournament']) for r in settled}
        age_days = max(0, (now - stamp(group[0]['registered_at'])).days) if group else 0
        markets[market] = dict(registered=len(group), settled=len(settled), pending=sum(r['id'] not in outcomes for r in group),
                               independent_fixtures=len(fixtures), tournaments=len(tournaments), age_days=age_days,
                               review_floor_met=len(fixtures)>=200 and len(tournaments)>=4 and age_days>=56,
                               **metrics)
    return dict(schema_version=1, generated_at=now.isoformat(), model=config['id'], status='SHADOW_ONLY',
                automatic_promotion=False, config_hash=digest(config), health=health, markets=markets,
                interpretation='Paired full-board research; correlated lines are not independent bets. No ROI claim before prospective review.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', type=Path)
    parser.add_argument('--source', type=Path, default=ROOT/'data/oncourt')
    parser.add_argument('--out', type=Path, default=ROOT/'data/tennis-props/shadow/rate-trend-v1')
    parser.add_argument('--config', type=Path, default=ROOT/'config/tennis-props-rate-trend-prospective-v1.json')
    args = parser.parse_args()
    config = read_json(args.config, None)
    now = datetime.now(timezone.utc)
    with lock(args.out):
        registered_config = read_json(args.out/'registration.json', None)
        if registered_config and registered_config['config_hash'] != digest(config):
            raise ValueError('Frozen configuration changed; start a separately registered experiment')
        if not registered_config:
            atomic_json(args.out/'registration.json', {'registered_at':now.isoformat(), 'config_hash':digest(config), 'config':config})
        records = ledger(args.out/'observations.jsonl')
        seen = {r['id'] for r in records}
        health = Counter()
        rows = list(MODEL['rows'](args.comparison)) if args.comparison else []
        if not rows:
            health['no_comparison_rows'] += 1
        eligible = []
        for row in rows:
            if row.get('market') not in config['markets']:
                continue
            reason = eligibility(row, now)
            if reason:
                health[reason] += 1
            elif contract_key(row) in seen:
                health['already_registered'] += 1
            else:
                row['logged_at_utc'] = now.isoformat()
                eligible.append(row)
        if eligible:
            manifest, reason = source_manifest(args.source, sorted({r['tour'] for r in eligible}), now, config['max_source_age_hours'])
            if reason:
                health[reason] += len(eligible)
                eligible = []
        if eligible:
            histories, _, identities, quality = MODEL['load_source'](args.source, eligible, config)
            after_manifest, _ = source_manifest(args.source, sorted({r['tour'] for r in eligible}), datetime.now(timezone.utc), config['max_source_age_hours'])
            if manifest != after_manifest:
                raise RuntimeError('OnCourt exports changed during read; retry after the export finishes')
            frozen_history = {t: {p: [dict(r, played=r['played'].isoformat()) for r in rows] for p, rows in h.items()} for t,h in histories.items()}
            input_hash = digest(frozen_history)
            archive = args.out/'inputs'
            archive.mkdir(exist_ok=True)
            if not (archive/f'{input_hash}.json').exists():
                atomic_json(archive/f'{input_hash}.json', frozen_history)
            for row in eligible:
                registered_at = datetime.now(timezone.utc)
                reason = eligibility(row, registered_at)
                if reason:
                    health[reason] += 1
                    continue
                key = contract_key(row)
                if key in seen:
                    continue
                tour = row['tour']
                player, opponent = (identities[tour].get(norm(row[k])) for k in ('player','opponent'))
                if not player or not opponent:
                    health['unresolved_player_identity'] += 1
                    continue
                multiplier, features, reason = MODEL['rate_trend'](histories[tour][player], histories[tour][opponent], row['surface'],
                                                                  stamp(row['capture_ts']).date(), row['market'], config)
                if multiplier is None:
                    health[reason] += 1
                    continue
                predictions = {'control':{}, 'candidate':{}}
                for side in ('OVER','UNDER'):
                    quoted = dict(row, side=side, selected_odds=row[side.lower()+'_odds'])
                    predictions['candidate'][side] = MODEL['prediction'](float(row['projection_mean'])*multiplier, quoted, config)
                    p, push = float(row['fair_p_'+side.lower()]), float(row['fair_p_push'])
                    loss = float(row['fair_p_'+('under' if side=='OVER' else 'over')])
                    predictions['control'][side] = dict(mean=float(row['projection_mean']),p_win=p,p_push=push,
                                                        p_conditional=p/(1-push) if push<1 else .5,ev=p*(float(quoted['selected_odds'])-1)-loss)
                fixture = digest([tour, row['date'][:4], MODEL['tournament_identity'](row['tournament']), sorted([player,opponent])])
                append(args.out/'observations.jsonl', records, dict(id=key, fixture_key=fixture, registered_at=registered_at.isoformat(),
                       config_hash=digest(config), input_hash=input_hash, source_manifest=manifest, capture_hash=digest(row), row=row, features=features,
                       multiplier=multiplier, **predictions, **{m+'_side':policy(predictions[m],config['min_ev']) for m in predictions}))
                seen.add(key)
                health['registered_now'] += 1
        outcomes = read_json(args.out/'outcomes.json', {})
        settle(records, args.source, outcomes, now)
        atomic_json(args.out/'outcomes.json', outcomes)
        summary = report(records, outcomes, dict(health), config, datetime.now(timezone.utc))
        atomic_json(args.out/'report.json', summary)
        print(json.dumps({'status':summary['status'], 'health':health, 'markets':summary['markets']}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
