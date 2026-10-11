"""Use approved public hierarchies in scheduled evidence review; never publish them."""
import argparse
import copy
import json
from pathlib import Path
import subprocess

LEAGUES=('epl','la-liga','serie-a','bundesliga','ligue-1')
def stamp(entry):
    return max(str(entry.get('last_updated') or ''),str(entry.get('public_updated_at') or ''))[:10]
def reconcile(local, published):
    if not isinstance(published,dict) or not isinstance(published.get('_meta'),dict):
        raise ValueError('Published hierarchy unavailable or malformed')
    result=copy.deepcopy(local);changed=[]
    for club,entry in published.items():
        if club.startswith('_'):continue
        if not isinstance(entry,dict) or not all(k in entry for k in ('primary','secondary','tertiary')):
            raise ValueError('Invalid published club '+club)
        existing=local.get(club,{})
        if stamp(entry)>=stamp(existing) and entry!=existing:
            result[club]=entry;changed.append(club)
    return result,changed
def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--ref',required=True);a=p.parse_args()
    prepared=[]
    for league in LEAGUES:
        relative=f'data/goalscorer/{league}-penalty-takers.json';file=a.root/relative
        published=json.loads(subprocess.check_output(['git','-c','gc.auto=0','show',f'{a.ref}:{relative}'],cwd=a.root))
        local=json.loads(file.read_text(encoding='utf8'));updated,changed=reconcile(local,published)
        prepared.append((file,updated,changed))
    for file,updated,changed in prepared:
        if changed:
            temp=file.with_suffix('.sync-tmp');temp.write_text(json.dumps(updated,ensure_ascii=False,indent=2)+'\n',encoding='utf8');temp.replace(file)
        print(file.name+': '+str(len(changed))+' approved club records synchronized')
if __name__=='__main__':main()
