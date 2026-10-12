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
    if not args.settlement_only:
        sys.argv=[sys.argv[0]]
        P.main()
    form=ROOT/'data/football-form'; path=form/'team-shots-paired-reference.jsonl'
    if not path.exists():return
    ledger=P.current_cohort([json.loads(s) for s in path.read_text(encoding='utf8').splitlines() if s.strip()])
    now=datetime.now(timezone.utc)
    base=P.PUB.load_csv(form/'team-match-base.csv')
    results,audit=paired_result_rows(ledger,base,snapshot_index(ROOT,now),now)
    target=form/'team-shots-paired-reference-status.json'
    previous=json.loads(target.read_text(encoding='utf8')) if target.exists() else {}
    status={**previous,**P.summarize(ledger,results,now), 'generated_at':P.PUB.fmt_dt(now),
        'latest_result_date':max((r['date'] for r in results),default=None),
        'settlement_source':'exact_fixture_base_and_verified_snapshots',
        'snapshot_settlement_contracts':len(audit)}
    for out,data in [(target,status),(form/'team-shots-paired-settlement-audit.json',dict(generated_at=P.PUB.fmt_dt(now),results=audit))]:
        temp=out.with_suffix('.tmp');temp.write_text(json.dumps(data,indent=2)+'\n',encoding='utf8');temp.replace(out)
    print(f"Paired evidence: {status['settled_contracts']} settled contracts, {status['paired_fixtures']} complete paired fixtures")

if __name__=='__main__':main()
