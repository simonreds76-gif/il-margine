"""Manager append step inside the existing Football Atlas weekly transaction."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('manager_package',ROOT/'scripts/package-manager-release.py')
package=importlib.util.module_from_spec(spec);spec.loader.exec_module(package)

def refresh_or_retain(state, offline=False):
    """A failed manager stage must not prevent an independent club/calendar run.

    Keep failure explicit and retain the last validated manifest; never label a
    failed collector as a successful update or publish its partial candidate.
    """
    manifest_path=ROOT/'src/data/manager-atlas-release.json'
    before_bytes=manifest_path.read_bytes()
    before=json.loads(before_bytes)
    # If the fallback itself is invalid, do not claim a usable old archive.
    package.validate(package.unpack(json.loads((ROOT/'public'/before['indexUrl'].lstrip('/')).read_text(encoding='utf-8'))))
    try:
        result=refresh(state,offline=offline)
        result.setdefault('publicationState','verified_partial' if result['pending'] else 'verified')
        result['checkedAt']=datetime.now(timezone.utc).isoformat()
        p=Path(state)/'managers';p.mkdir(parents=True,exist_ok=True)
        (p/'publication-status.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        return result
    except Exception as exc:
        if manifest_path.read_bytes()!=before_bytes:
            manifest_path.write_bytes(before_bytes)
        report={'changed':False,'manifest':before,'previous':before['indexUrl'],'paths':[],
                'added':0,'pending':[],'publicationState':'retained_manager_failure',
                'error':type(exc).__name__,'errorDetail':str(exc)[:500],
                'checkedAt':datetime.now(timezone.utc).isoformat()}
        p=Path(state)/'managers';p.mkdir(parents=True,exist_ok=True)
        try:
            queue=json.loads((p/'pending-fixtures.json').read_text(encoding='utf-8'))
            report['pending']=[r for r in queue['fixtures'].values() if r.get('state')=='pending']
            report['pendingCountKnown']=True
        except (OSError,ValueError,KeyError,TypeError,AttributeError):
            report['pendingCountKnown']=False
        (p/'publication-status.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print('::warning::Manager refresh failed ('+type(exc).__name__+'); previous verified manager archive retained. Independent club/calendar refresh continues.',flush=True)
        return report

def refresh(state, offline=False):
    # Monthly editorial decisions are authoritative. A weekly history append
    # must neither regenerate them from old rosters nor publish a stale copy.
    activity_paths=[ROOT/'config/manager-atlas-activity.json',ROOT/'public/manager-atlas/activity.json']
    activity_before=[p.read_bytes() for p in activity_paths]
    if json.loads(activity_before[0])!=json.loads(activity_before[1]):
        raise ValueError('Manager activity source/public copy mismatch; retain previous release')
    manifest_path=ROOT/'src/data/manager-atlas-release.json'
    before=json.loads(manifest_path.read_text(encoding='utf-8'))
    data=package.unpack(json.loads((ROOT/'public'/before['indexUrl'].lstrip('/')).read_text(encoding='utf-8')))
    state=Path(state)/'managers';state.mkdir(parents=True,exist_ok=True)
    archive=state/'candidate.json';archive.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
    command=[sys.executable,str(ROOT/'scripts/refresh-manager-atlas.py'),'--archive',str(archive),'--state',str(state),'--strict','--quarantine-unresolved-fixtures']
    if offline:command.append('--offline')
    prior_report=state/'refresh-report.json'
    prior_stamp=prior_report.stat().st_mtime_ns if prior_report.exists() else None
    subprocess.run(command,cwd=ROOT,check=True,timeout=900)
    report=json.loads(prior_report.read_text(encoding='utf-8'))
    if (prior_report.stat().st_mtime_ns==prior_stamp or report.get('failures')
            or not report.get('fullyAccounted')
            or report.get('atlasVersion')!=json.loads((ROOT/'src/data/football-atlas-release.json').read_text())['version']
            or json.loads(manifest_path.read_text(encoding='utf-8'))!=before):
        raise ValueError('Manager refresh receipt invalid or stale; retain previous release')
    candidate=json.loads(archive.read_text(encoding='utf-8'))
    # Existing manager assignments and prices cannot silently change on refresh.
    old={f['id']:f for f in data['fixtures']};new={f['id']:f for f in candidate['fixtures']}
    new_ids=set(new)-set(old);verified=report.get('verifiedIds',[])
    pending_ids=[r['id'] for r in report.get('pending',[])]
    candidate_ids=report.get('candidateIds',[])
    if (len(new)!=len(candidate['fixtures']) or len(set(verified))!=len(verified)
            or len(set(pending_ids))!=len(pending_ids) or len(set(candidate_ids))!=len(candidate_ids)
            or new_ids!=set(verified) or new_ids&set(pending_ids)
            or new_ids|set(pending_ids)!=set(candidate_ids)
            or report.get('candidates')!=len(candidate_ids) or report.get('added')!=len(new_ids)):
        raise ValueError('Manager additions do not match exact receipt partition')
    if any(new.get(fid)!=row for fid,row in old.items()):raise ValueError('Existing manager fixture changed')
    if [p.read_bytes() for p in activity_paths]!=activity_before:
        raise ValueError('Weekly refresh changed reviewed manager activity; retain previous release')
    if not new_ids:
        return {'changed':False,'manifest':before,'previous':before['indexUrl'],'paths':[],
                'added':0,'pending':report['pending'],'publicationState':'retained_no_verified_additions'}
    after,path=package.package(candidate)
    return {'changed':before['version']!=after['version'],'manifest':after,'previous':before['indexUrl'],'paths':[path.as_posix(),'src/data/manager-atlas-release.json'],'added':report['added'],'pending':report['pending']}
