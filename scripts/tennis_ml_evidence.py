"""Bounded local-only all-candidate component snapshots, without live routing changes.

No network or database access. Snapshots are immutable and retained for research.
Capture time is NOT proof of pre-match timing; join verified schedules/prices later.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

MAX_DAILY_FILES = 8
MAX_SNAPSHOT_BYTES = 500_000

def capture_components(root: Path, rows: list[dict], captured_at: datetime | None = None) -> str:
    if not rows: return 'empty'
    now = captured_at or datetime.now(timezone.utc)
    if now.tzinfo is None: raise ValueError('capture timestamp must be timezone aware')
    now = now.astimezone(timezone.utc)
    # Only caller-supplied forecast fields are serialized; never environment/secrets.
    body = json.dumps(rows, sort_keys=True, separators=(',', ':'), allow_nan=False)
    digest = hashlib.sha256(body.encode()).hexdigest()
    folder = root / 'data/tennis-ml-research/components' / now.strftime('%Y-%m-%d')
    target = folder / f'{digest}.json'
    if target.exists(): return 'unchanged'
    if folder.exists() and len(list(folder.glob('*.json'))) >= MAX_DAILY_FILES: return 'daily_limit'
    model_file = root / 'scripts/oncourt-compute-fair-odds.py'
    model_hash = hashlib.sha256(model_file.read_bytes()).hexdigest()
    content = json.dumps({'schema_version':1,'captured_at':now.isoformat(),
        'model_file_sha256':model_hash,'payload_sha256':digest,'rows':rows,
        'timing_status':'capture_only_requires_verified_pre_match_price_join',
        'scope':'all computed eligible fixtures, including non-signals; no staking'},separators=(',', ':'),allow_nan=False)
    if len(content.encode()) > MAX_SNAPSHOT_BYTES: return 'size_limit'
    folder.mkdir(parents=True,exist_ok=True)
    try:
        with target.open('x',encoding='utf-8') as f: f.write(content)
    except FileExistsError: return 'unchanged'
    return f'saved:{len(rows)}'
