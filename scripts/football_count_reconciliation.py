"""Audited paper-accounting overlays; never rewrite or regrade original rows."""
import json
from pathlib import Path

def reconcile(rows,root):
    path=Path(root)/'config/football-count-reconciliations.json'
    cases=json.loads(path.read_text(encoding='utf8')).get('cases',[]) if path.exists() else []
    by_id={r.get('pick_id'):r for r in rows}; excluded=[]; applied=[]
    for case in cases:
        duplicate=by_id.get(case['duplicate_pick_id']); original=by_id.get(case['retained_pick_id'])
        if duplicate is None or original is None: continue
        expected=case['expected_duplicate']
        for key,value in expected.items():
            actual=duplicate.get(key)
            if key=='book_odds': actual=duplicate.get('book_price_at_publication') or actual
            equal=float(actual)==float(value) if key in {'book_odds','line'} else str(actual)==value
            if not equal: raise ValueError('Reconciliation evidence no longer matches: '+case['id'])
        excluded.append(case['duplicate_pick_id']);applied.append(case)
    return [r for r in rows if r.get('pick_id') not in excluded],dict(
        excluded_pick_ids=excluded,excluded_duplicates=len(excluded),cases=applied,
        historical_records_unchanged=True)
