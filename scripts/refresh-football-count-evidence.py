#!/usr/bin/env python3
"""Refresh paired settlements without changing the frozen inference fingerprint."""
import argparse
import importlib.util
import json
import sys
from datetime import datetime,timezone
from pathlib import Path
from football_count_results import snapshot_index, paired_result_rows

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('paired_evidence',ROOT/'scripts/team-shots-paired-reference.py')
P=importlib.util.module_from_spec(spec);spec.loader.exec_module(P)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--settlement-only',action='store_true')
    args=parser.parse_args()
    # Independent archive: no change to guarded inference or selected ledgers.
    # Run before the shots lane so an unrelated capture failure cannot lose it.
    from corners_candidate_evidence import refresh as refresh_corners
    try:
        corners_status=refresh_corners(ROOT,settle_only=args.settlement_only)
        print('Corners opportunity archive: '+json.dumps(corners_status,sort_keys=True))
    except Exception as exc:
        print('::warning::Corners opportunity archive incomplete; see corners-candidate-evidence-v1/capture-status.json: '+str(exc))
    capture_error=None
    if not args.settlement_only:
        sys.argv=[sys.argv[0]]
        try:
            P.main()
        except P.ModelFingerprintMismatch as exc:
            # New predictions remain blocked. Existing forecasts can still settle,
            # and the independent shots/corners snapshots must still publish.
            capture_error=str(exc)
            print('WARNING: paired capture held: '+capture_error)
    form=ROOT/'data/football-form'; path=form/'team-shots-paired-reference.jsonl'
    if not path.exists():return
    ledger=[json.loads(s) for s in path.read_text(encoding='utf8').splitlines() if s.strip()]
    now=datetime.now(timezone.utc)
    base=P.PUB.load_csv(form/'team-match-base.csv')
    results,audit=paired_result_rows(ledger,base,snapshot_index(ROOT,now),now)
    target=form/'team-shots-paired-reference-status.json'
    previous=json.loads(target.read_text(encoding='utf8')) if target.exists() else {}
    cohorts={version:P.summarize([r for r in ledger if r.get('version')==version],results,now)
             for version in sorted({r.get('version','unversioned') for r in ledger})}
    status={**previous,**P.summarize(ledger,results,now), 'generated_at':P.PUB.fmt_dt(now),
        'version':P.VERSION,'cohorts':cohorts,'record_scope':'All retained prospective cohorts; original predictions and prices unchanged.',
        'capture_status':'BLOCKED_MODEL_CHANGE' if capture_error else 'SETTLEMENT_ONLY' if args.settlement_only else 'ACTIVE',
        'capture_error':capture_error,
        'latest_result_date':max((r['date'] for r in results),default=None),
        'settlement_source':'exact_fixture_base_and_verified_snapshots',
        'snapshot_settlement_contracts':len(audit)}
    status['interpretation']+=' Identity repairs registered 28 October 2026; inspect cohort breakdown for consistent-input comparisons.'
    from team_shots_strength_paper import refresh as refresh_strength, RELATIVE as STRENGTH_PATH
    from frozen_paper_common import atomic
    try:
        status['strength_comparison']=refresh_strength(ROOT,now,settle_only=args.settlement_only)
    except Exception as exc:
        health=dict(state='REFRESH_ERROR',reason=str(exc),checked_at=now.isoformat())
        atomic(ROOT/STRENGTH_PATH/'capture-status.json',health)
        status['strength_comparison']={**previous.get('strength_comparison',{}),'capture':health}
    if capture_error:status.update(status='CAPTURE_BLOCKED_MODEL_CHANGE',new_contracts=0)
    for out,data in [(target,status),(form/'team-shots-paired-settlement-audit.json',dict(generated_at=P.PUB.fmt_dt(now),results=audit))]:
        temp=out.with_suffix('.tmp');temp.write_text(json.dumps(data,indent=2)+'\n',encoding='utf8');temp.replace(out)
    print(f"Paired evidence: {status['settled_contracts']} settled contracts, {status['paired_fixtures']} complete paired fixtures")

if __name__=='__main__':main()
