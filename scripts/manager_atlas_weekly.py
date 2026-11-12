"""Manager append step inside the existing Football Atlas weekly transaction."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('manager_package',ROOT/'scripts/package-manager-release.py')
package=importlib.util.module_from_spec(spec);spec.loader.exec_module(package)

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
    command=[sys.executable,str(ROOT/'scripts/refresh-manager-atlas.py'),'--archive',str(archive),'--state',str(state),'--strict','--quarantine-unknown-managers']
    if offline:command.append('--offline')
    prior_report=state/'refresh-report.json'
    prior_stamp=prior_report.stat().st_mtime_ns if prior_report.exists() else None
    try:
        subprocess.run(command,cwd=ROOT,check=True,timeout=900)
    except subprocess.CalledProcessError:
        # Unverified new coaching assignments hold only the manager archive.
        # They must not prevent the independently validated club/schedule update.
        report_path=state/'refresh-report.json'
        report=json.loads(report_path.read_text(encoding='utf-8')) if report_path.exists() else {}
        failures=report.get('failures') or []
        if (not report_path.exists() or report_path.stat().st_mtime_ns == prior_stamp
                or not failures or not all(str(f).startswith('Manager verification incomplete:') for f in failures)
                or not report.get('pending') or report.get('atlasVersion') != json.loads((ROOT/'src/data/football-atlas-release.json').read_text())['version']
                or json.loads(manifest_path.read_text(encoding='utf-8')) != before
                or [p.read_bytes() for p in activity_paths] != activity_before):
            raise
        return {'changed':False,'manifest':before,'previous':before['indexUrl'],'paths':[],
                'added':0,'pending':report['pending'],'publicationState':'retained_pending_verified_assignments'}
    candidate=json.loads(archive.read_text(encoding='utf-8'))
    # Existing manager assignments and prices cannot silently change on refresh.
    old={f['id']:f for f in data['fixtures']};new={f['id']:f for f in candidate['fixtures']}
    if any(new.get(fid)!=row for fid,row in old.items()):raise ValueError('Existing manager fixture changed')
    if [p.read_bytes() for p in activity_paths]!=activity_before:
        raise ValueError('Weekly refresh changed reviewed manager activity; retain previous release')
    after,path=package.package(candidate)
    report=json.loads((state/'refresh-report.json').read_text(encoding='utf-8'))
    return {'changed':before['version']!=after['version'],'manifest':after,'previous':before['indexUrl'],'paths':[path.as_posix(),'src/data/manager-atlas-release.json'],'added':report['added'],'pending':report['pending']}
