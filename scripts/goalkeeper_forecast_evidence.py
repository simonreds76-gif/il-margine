"""Append bounded pre-match input/price packets. No downloads or selection changes."""
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import json
import math
from pathlib import Path


def source_hashes(paths):
    return {str(p): sha256(p.read_bytes()).hexdigest() if p.exists() else None
            for p in sorted(set(paths), key=str)}


def timestamp(value):
    try:
        result = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return result.astimezone(UTC) if result.tzinfo else None
    except (ValueError, TypeError):
        return None


def encode(value):
    return json.dumps(value, sort_keys=True, allow_nan=False, separators=(',', ':')).encode()


def archive(folder, candidates, params, before, *, now=None):
    now = now or datetime.now(UTC)
    counts = Counter()
    status = {'checked_at': now.isoformat(), 'actual_stake': 0, 'saved': 0}
    if not now.tzinfo:
        raise ValueError('Timezone required')
    if not before or source_hashes([Path(p) for p in before]) != before:
        return {**status, 'status': 'BLOCKED', 'reason': 'inputs_changed_during_forecast'}
    groups = defaultdict(list)
    names = params.get('features') or []
    if len(names) != 9 or len(set(names)) != 9:
        return {**status, 'status': 'BLOCKED', 'reason': 'unsupported_feature_specification'}
    for row in candidates:
        captured, kickoff = timestamp(row.get('captured_at')), timestamp(row.get('kickoff_at'))
        if not captured or not kickoff or not captured <= now < kickoff or now - captured > timedelta(hours=6):
            counts['not_fresh_prematch'] += 1
            continue
        if not row.get('event_id') or not row.get('_research_quote'):
            counts['missing_identity_or_raw_quote'] += 1
            continue
        features = row.get('_research_features')
        if features is not None and (len(features) != len(names) or not all(math.isfinite(x) for x in features)):
            counts['invalid_features'] += 1
            continue
        groups[(str(row['event_id']), kickoff.isoformat())].append(row)
    if len(groups) > 60:
        return {**status, 'status': 'BLOCKED', 'reason': 'fixture_budget_exceeded'}
    for identity, rows in sorted(groups.items()):
        rows = sorted(rows, key=lambda r: (str(r.get('goalkeeper')), str(r.get('line')), str(r.get('side'))))
        contracts = [(str(r.get('bookmaker')), str(r.get('goalkeeper')), str(r.get('line')), str(r.get('side'))) for r in rows]
        if len(set(contracts)) != len(contracts):
            counts['ambiguous_duplicate_contract'] += len(rows)
            continue
        payload = {'schema_version': 1, 'event_id': identity[0], 'kickoff_at': identity[1],
                   'cohort': 'new pre-match input capture; not a candidate model trial',
                   'coverage': 'All captured offered lines supplied to this run; market completeness not established',
                   'model_params': params, 'source_hashes': before,
                   'offers': [{k: v for k, v in row.items() if k != 'generated_at'} for row in rows],
                   'actual_stake': 0}
        digest = sha256(encode(payload)).hexdigest()
        raw = encode({**payload, 'registered_at': now.isoformat(), 'payload_sha256': digest})
        if len(raw) > 1_000_000:
            counts['packet_size_limit'] += 1
            continue
        path = folder / 'packets' / (digest + '.json')
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open('xb') as stream:
                stream.write(raw)
            status['saved'] += 1
            counts['offers_saved'] += len(rows)
        except FileExistsError:
            counts['already_saved'] += 1
    return {**status, 'status': 'CAPTURED' if status['saved'] else 'NO_NEW_ELIGIBLE_INPUTS',
            'counts': dict(counts)}
