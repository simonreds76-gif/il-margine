"""Allow only the reviewed quote-join repair, never unregistered model drift."""
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone


def accepted(root, folder, registration_hash, current_hashes, now):
    path=Path(folder)/'quote-repair-20261111.json'
    if not path.exists(): return None
    data=json.loads(path.read_bytes())
    if data.get('scope')!='quote-identity-only-20261111' or data.get('pricing_changed') is not False: return None
    if data.get('registration_sha256')!=registration_hash or data.get('after')!=current_hashes: return None
    if datetime.fromisoformat(data['effective_at'])>now: return None
    before=data.get('before_operating',{})
    allowed={'scripts/tennis_hardcourt_scout.py'}
    if Path(folder).name=='indoor-scout-v1': allowed.add('scripts/tennis_indoor_paper.py')
    if {k for k in set(before)|set(current_hashes) if before.get(k)!=current_hashes.get(k)} != allowed: return None
    for name,value in data.get('implementation_sha256',{}).items():
        if name not in {'scripts/tennis_paper_quote_identity.py','scripts/tennis_paper_quote_guard.py','scripts/tennis_price_identity.py'}: return None
        if hashlib.sha256((Path(root)/name).read_bytes()).hexdigest()!=value: return None
    if len(data.get('implementation_sha256',{}))!=3: return None
    proof=Path(folder)/'quote-repair-proof-20261111.json'
    if not proof.exists() or hashlib.sha256(proof.read_bytes()).hexdigest()!=data.get('proof_sha256'): return None
    checked=json.loads(proof.read_bytes())
    if checked.get('selector_ast_unchanged') is not True or checked.get('pricing_files_unchanged') is not True: return None
    return hashlib.sha256(path.read_bytes()).hexdigest()
