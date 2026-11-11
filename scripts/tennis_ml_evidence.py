"""Bounded local-only all-candidate component snapshots, without live routing changes.

No network or database access. Snapshots are immutable and retained for research.
Capture time is NOT proof of pre-match timing; join verified schedules/prices later.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import gzip
import sys

MAX_DAILY_FILES = 8
MAX_SNAPSHOT_BYTES = 500_000

def capture_components(root: Path, rows: list[dict], captured_at: datetime | None = None) -> str:
    if not rows: return 'empty'
    now = captured_at or datetime.now(timezone.utc)
    if now.tzinfo is None: raise ValueError('capture timestamp must be timezone aware')
    now = now.astimezone(timezone.utc)
    # Paper-only observer; no live forecasting or delivery changes.
    try:
        from tennis_indoor_paper import observe
        observe(root, rows, now=now, forecast_generated_at=now.isoformat())
    except Exception as exc:
        print("Indoor Scout observer unavailable:", type(exc).__name__)
    # Separately registered scope; never changes live routing or alerts.
    try:
        from tennis_indoor_expansion import observe as observe_indoor_expansion
        observe_indoor_expansion(root, rows, now=now, forecast_generated_at=now.isoformat())
    except Exception as exc:
        print('Indoor expansion observer unavailable:', type(exc).__name__)
    # Only caller-supplied forecast fields are serialized; never environment/secrets.
    body = json.dumps(rows, sort_keys=True, separators=(',', ':'), allow_nan=False)
    digest = hashlib.sha256(body.encode()).hexdigest()
    trace = None
    trace_status = 'unavailable_caller'
    try:
        from tennis_elo_input_trace import build_trace
        trace = build_trace(root, rows, sys._getframe(1), now)
        if trace is not None: trace_status = 'loaded_inputs_retained'
    except Exception as exc:
        # Diagnostic failure must never prevent the existing forecast evidence.
        trace_status = 'unavailable:' + type(exc).__name__
        print('Elo input trace unavailable:', type(exc).__name__)
    trace_hash = hashlib.sha256(trace).hexdigest() if trace is not None else None
    folder = root / 'data/tennis-ml-research/components' / now.strftime('%Y-%m-%d')
    target = folder / (f'{digest}-{trace_hash[:16]}.json' if trace_hash else f'{digest}.json')
    if target.exists(): return 'unchanged'
    if folder.exists() and len(list(folder.glob('*.json'))) >= MAX_DAILY_FILES: return 'daily_limit'
    model_file = root / 'scripts/oncourt-compute-fair-odds.py'
    model_bytes = model_file.read_bytes()
    model_hash = hashlib.sha256(model_bytes).hexdigest()
    content = json.dumps({'schema_version':2 if trace_hash else 1,'captured_at':now.isoformat(),
        'model_file_sha256':model_hash,'payload_sha256':digest,'rows':rows,
        'input_trace_status':trace_status, 'input_trace_sha256':trace_hash,
        'input_trace_file':f'inputs/{trace_hash}.json.gz' if trace_hash else None,
        'model_source_file':f'inputs/{model_hash}.py' if trace_hash else None,
        'timing_status':'capture_only_requires_verified_pre_match_price_join',
        'scope':'all computed eligible fixtures, including non-signals; no staking'},separators=(',', ':'),allow_nan=False)
    if len(content.encode()) > MAX_SNAPSHOT_BYTES: return 'size_limit'
    folder.mkdir(parents=True,exist_ok=True)
    if trace is not None:
        inputs = folder / 'inputs'
        try:
            inputs.mkdir(exist_ok=True)
            for path, blob in ((inputs/f'{trace_hash}.json.gz', gzip.compress(trace,mtime=0)),
                               (inputs/f'{model_hash}.py', model_bytes)):
                try:
                    with path.open('xb') as handle: handle.write(blob)
                except FileExistsError:
                    if path.read_bytes() != blob: raise ValueError('immutable input trace conflict')
        except Exception as exc:
            # Never claim that a missing sidecar was saved successfully.
            value=json.loads(content)
            value.update(input_trace_status='write_failed:'+type(exc).__name__,
                         input_trace_sha256=None,input_trace_file=None,model_source_file=None)
            content=json.dumps(value,separators=(',', ':'),allow_nan=False)
            target=folder/f'{digest}.json'
            print('Elo input trace write failed:', type(exc).__name__)
    try:
        with target.open('x',encoding='utf-8') as f: f.write(content)
    except FileExistsError: return 'unchanged'
    return f'saved:{len(rows)}'
