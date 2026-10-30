"""Bounded, immutable observations of actual count inputs; never a bet ledger."""
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import uuid

MAX_BYTES = 64 * 1024 * 1024
MAX_FILES = 10000
MAX_DAILY_FILES = 8


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def capture_count_inputs(root, rows, history, source_paths, now=None, board_path=None):
    if not rows:
        return 'empty'
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError('timezone_required')
    folder = Path(root) / 'data/tennis-props/input-diagnostics'
    files = list(folder.glob('*/*.json.gz')) if folder.exists() else []
    first_date = min([p.parent.name for p in files] + [now.astimezone(timezone.utc).strftime('%Y-%m-%d')])
    sources = {str(Path(p).resolve()): sha(p) for p in source_paths}
    body = {'schema_version': 1, 'rows': rows, 'history': history, 'source_hashes': sources,
            'instrumentation_version': 'count-input-trace-20261030',
            'first_instrumented_date': first_date,
            'source_hash_timing': 'observed_after_calculation_not_atomic_input_reads',
            'board_file_sha256': sha(board_path) if board_path else None,
            'timing_status': 'observation_only_requires_exact_prematch_join',
            'scope': 'actual executed general-count intermediates; no forecast or bet backfill'}
    encoded = json.dumps(body, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    digest = hashlib.sha256(encoded).hexdigest()
    day = folder / now.astimezone(timezone.utc).strftime('%Y-%m-%d')
    target = day / (digest + '.json.gz')
    if target.exists():
        return 'unchanged'
    if day.exists() and len(list(day.glob('*.json.gz'))) >= MAX_DAILY_FILES:
        return 'daily_limit'
    body.update(captured_at_utc=now.astimezone(timezone.utc).isoformat(), payload_sha256=digest)
    raw = gzip.compress(json.dumps(body, sort_keys=True, allow_nan=False).encode(), mtime=0)
    if len(files) >= MAX_FILES or sum(p.stat().st_size for p in files) + len(raw) > MAX_BYTES:
        return 'capacity_limit'
    day.mkdir(parents=True, exist_ok=True)
    temporary = day / (digest + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('xb') as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        # Atomic publication without replacing an existing immutable receipt.
        if os.name == 'nt':
            os.rename(temporary, target)  # Windows refuses an existing destination.
        else:
            os.link(temporary, target)
    except FileExistsError:
        return 'unchanged'
    finally:
        temporary.unlink(missing_ok=True)
    return 'saved:' + str(len(rows))
