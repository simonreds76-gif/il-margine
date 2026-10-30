"""Accept one explicitly reviewed observation-only implementation map, never drift."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

def accepted_observation_amendment(folder, registration_hash, before, after, section, now=None):
    folder=Path(folder);path=folder/'observation-amendment-20261030.json'
    if not path.exists():return None
    data=json.loads(path.read_bytes());entry=data.get('sections',{}).get(section,{})
    now=now or datetime.now(timezone.utc)
    effective=datetime.fromisoformat(data['effective_at_utc'])
    if now.tzinfo is None or effective.tzinfo is None or effective>now:return None
    if data.get('scope')!='instrumentation-only-20261030' or data.get('pricing_changed') is not False:return None
    if entry.get('registration_sha256')!=registration_hash or entry.get('before')!=before or entry.get('after')!=after:return None
    proof=folder/'observation-proof-20261030.json'
    if not proof.exists() or hashlib.sha256(proof.read_bytes()).hexdigest()!=data.get('parity_proof_sha256'):return None
    if hashlib.sha256(Path(__file__).read_bytes()).hexdigest()!=data.get('guard_sha256'):return None
    caller=entry.get('caller_guard_file')
    if caller not in {'sisal_event_comparison.py'}:return None
    if hashlib.sha256((Path(__file__).parent/caller).read_bytes()).hexdigest()!=entry.get('caller_guard_sha256'):return None
    return hashlib.sha256(path.read_bytes()).hexdigest()
