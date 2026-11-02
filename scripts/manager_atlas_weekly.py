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
    subprocess.run(command,cwd=ROOT,check=True,timeout=900)
    candidate=json.loads(archive.read_text(encoding='utf-8'))
    # Existing manager assignments and prices cannot silently change on refresh.
    old={f['id']:f for f in data['fixtures']};new={f['id']:f for f in candidate['fixtures']}
    if any(new.get(fid)!=row for fid,row in old.items()):raise ValueError('Existing manager fixture changed')
    if [p.read_bytes() for p in activity_paths]!=activity_before:
        raise ValueError('Weekly refresh changed reviewed manager activity; retain previous release')
    after,path=package.package(candidate)
    report=json.loads((state/'refresh-report.json').read_text(encoding='utf-8'))
    return {'changed':before['version']!=after['version'],'manifest':after,'previous':before['indexUrl'],'paths':[path.as_posix(),'src/data/manager-atlas-release.json'],'added':report['added'],'pending':report['pending']}
