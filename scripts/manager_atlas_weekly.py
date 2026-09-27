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
    manifest_path=ROOT/'src/data/manager-atlas-release.json'
    before=json.loads(manifest_path.read_text(encoding='utf-8'))
    data=package.unpack(json.loads((ROOT/'public'/before['indexUrl'].lstrip('/')).read_text(encoding='utf-8')))
    state=Path(state)/'managers';state.mkdir(parents=True,exist_ok=True)
    archive=state/'candidate.json';archive.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
    command=[sys.executable,str(ROOT/'scripts/refresh-manager-atlas.py'),'--archive',str(archive),'--state',str(state),'--strict']
    if offline:command.append('--offline')
    subprocess.run(command,cwd=ROOT,check=True,timeout=900)
    candidate=json.loads(archive.read_text(encoding='utf-8'))
    # Existing manager assignments and prices cannot silently change on refresh.
    old={f['id']:f for f in data['fixtures']};new={f['id']:f for f in candidate['fixtures']}
    if any(new.get(fid)!=row for fid,row in old.items()):raise ValueError('Existing manager fixture changed')
    after,path=package.package(candidate)
    report=json.loads((state/'refresh-report.json').read_text(encoding='utf-8'))
    return {'changed':before['version']!=after['version'],'manifest':after,'previous':before['indexUrl'],'paths':[path.as_posix(),'src/data/manager-atlas-release.json'],'added':report['added']}
