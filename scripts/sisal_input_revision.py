"""Validate a dated, exact input repair without unfreezing the experiment."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

NAME = 'input-isolation-revision-20261105.json'


def accepted_input_revision(root, folder, registration_hash, before, after, now):
    path = Path(folder) / NAME
    if not path.exists():
        return None
    try:
        revision = json.loads(path.read_bytes())
        effective = datetime.fromisoformat(revision['effective_at'])
        if not (effective.tzinfo and effective <= now <= datetime.now(timezone.utc)):
            return None
        if (revision['scope'] != 'verified-input-isolation-20261105'
                or revision['pricing_changed'] is not False
                or revision['registration_sha256'] != registration_hash
                or revision['before'] != before or revision['after'] != after
                or revision['guard_sha256'] != hashlib.sha256(Path(__file__).read_bytes()).hexdigest()):
            return None
        # Preserve the pre-existing source revision and observation audit too.
        for name, digest in revision['prior_evidence'].items():
            if name not in {'source-filter-revision.json', 'observation-amendment-20261030.json', 'observation-proof-20261030.json'}:
                return None
            if hashlib.sha256((Path(folder) / name).read_bytes()).hexdigest() != digest:
                return None
        if len(revision['prior_evidence']) != 3:
            return None
        proof = Path(folder) / 'input-isolation-proof-20261105.json'
        if hashlib.sha256(proof.read_bytes()).hexdigest() != revision['proof_sha256']:
            return None
        evidence = json.loads(proof.read_bytes())
        if (evidence['model_formula_changed'] is not False
                or evidence['project_side_ast_identical'] is not True
                or evidence['paired_rows'] <= 0
                or evidence['paired_prices_identical'] is not True
                or evidence['new_board_sha256'] != after['scripts/build-tennis-props-board.py']):
            return None
        return dict(effective_at=revision['effective_at'], sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    except (OSError, ValueError, KeyError, TypeError):
        return None
