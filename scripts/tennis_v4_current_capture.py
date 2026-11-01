"""Register current v4 ladders without historical closing-price/settlement scans.

Uses the existing frozen v4 registration/probability/report functions verbatim.
Historical settlement continues on its existing scheduled path.
"""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import argparse
import importlib.util
import sys

ROOT = Path(__file__).resolve().parents[1]

def capture(module, comparison, now):
    rows = module.read_csv(module.DEFAULT_LEDGER)
    module.assert_integrity(rows)
    original = [dict(r) for r in rows]
    import json
    gate = json.loads(module.DEFAULT_GATE.read_text(encoding='utf-8-sig'))
    sha = module.model_hash(gate)
    candidates, rejected = module.ladder_candidates([comparison])
    seen = {r['observation_id'] for r in rows}
    added = 0
    registration_rejected = Counter()
    for candidate in candidates:
        rid = module.observation_id(candidate['row'])
        if rid in seen:
            continue
        reason = module.registration_problem(candidate, now)
        if reason:
            registration_rejected[reason] += 1
            continue
        rows.append(module.build_registration(candidate, ledger=rows, gate=gate, sha256=sha, now=now))
        seen.add(rid)
        added += 1
    module.assert_integrity(rows)
    if rows[:len(original)] != original:
        raise ValueError('Current capture altered an existing v4 observation')
    if added:
        temporary = module.DEFAULT_LEDGER.with_suffix('.current.tmp')
        module.write_csv(temporary, rows)
        temporary.replace(module.DEFAULT_LEDGER)
    payload = module.report_payload(rows, accepted_ladders=len(candidates), rejected=rejected, generated_at=now)
    payload['registration_reject_reasons'] = dict(registration_rejected)
    payload['refresh_mode'] = 'CURRENT_CAPTURE_ONLY'
    payload['historical_settlement_refreshed'] = False
    module.write_report(module.DEFAULT_REPORT, module.DEFAULT_JSON, payload)
    print(f'Current v4: added={added}; observations={len(rows)}; original observations unchanged; settlement remains scheduled')
    return added

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--comparison', type=Path, required=True)
    args=parser.parse_args()
    if not args.comparison.exists():
        raise FileNotFoundError('Current v4 comparison is unavailable')
    sys.path.insert(0,str(ROOT/'scripts'))
    spec=importlib.util.spec_from_file_location('v4_current_frozen',ROOT/'scripts/tennis-props-aces-over-v4.py')
    module=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=module
    spec.loader.exec_module(module)
    capture(module,args.comparison,datetime.now(timezone.utc))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
