"""Private Skyline persistence in the existing Supabase snapshot table."""
import json
import os
from copy import deepcopy
from datetime import datetime, timezone
import requests
from aerial_data import read, save

KEY = 'skyline_paper_v1'

def fetch(root):
    url,headers=connection(root)
    response=requests.get(url,headers=headers,params={'snapshot_key':'eq.'+KEY,'select':'payload,updated_at'},timeout=30)
    response.raise_for_status();rows=response.json()
    if not isinstance(rows,list) or len(rows)>1:raise ValueError('Invalid private Skyline state')
    if rows and rows[0]['payload'].get('version')!='skyline-v1':raise ValueError('Wrong private Skyline state version')
    return rows[0] if rows else None

def update(root, change):
    """Compare-and-swap the private row so refreshes cannot erase alert receipts."""
    url,headers=connection(root)
    for _ in range(4):
        row=fetch(root)
        if row is None:
            response=requests.post(url,headers={**headers,'Prefer':'resolution=ignore-duplicates'},
                params={'on_conflict':'snapshot_key'},json=[{'snapshot_key':KEY,
                'updated_at':datetime.now(timezone.utc).isoformat(),'payload':{'version':'skyline-v1'}}],timeout=30)
            response.raise_for_status();continue
        state=deepcopy(row['payload'])
        if change(state) is False:return False
        response=requests.patch(url,headers={**headers,'Prefer':'return=representation'},
            params={'snapshot_key':'eq.'+KEY,'updated_at':'eq.'+row['updated_at']},
            json={'updated_at':datetime.now(timezone.utc).isoformat(),'payload':state},timeout=45)
        response.raise_for_status()
        if response.json():return True
    raise RuntimeError('Private Skyline state changed concurrently; retry next refresh')

def connection(root):
    values = dict(os.environ)
    path = root/'.env.local'
    if path.exists():
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            if '=' in line and not line.lstrip().startswith('#'):
                k,v=line.split('=',1);values.setdefault(k.strip(),v.strip().strip('"').strip("'"))
    base=(values.get('NEXT_PUBLIC_SUPABASE_URL') or values.get('SUPABASE_URL') or '').rstrip('/')
    key=values.get('SUPABASE_SERVICE_ROLE_KEY')
    if not base or not key:raise ValueError('Private Skyline storage credentials unavailable')
    return base+'/rest/v1/goalscorer_live_snapshot',{'apikey':key,'Authorization':'Bearer '+key,'Content-Type':'application/json'}

def restore(root):
    url,headers=connection(root)
    response=requests.get(url,headers=headers,params={'snapshot_key':'eq.'+KEY,'select':'payload'},timeout=30)
    response.raise_for_status();rows=response.json()
    if not isinstance(rows,list) or len(rows)>1:raise ValueError('Invalid private Skyline state')
    if not rows:return
    state=rows[0]['payload']
    if state.get('version')!='skyline-v1':raise ValueError('Wrong private Skyline state version')
    directory=root/'data/aerial/skyline'
    for kind in ('forecasts','outcomes'):
        for key,value in state.get(kind,{}).items():
            if len(key)!=64 or any(c not in '0123456789abcdef' for c in key):raise ValueError('Invalid Skyline record key')
            path=directory/kind/(key+'.json')
            if path.exists() and read(path)!=value:raise ValueError('Conflicting local/private Skyline record')
            if not path.exists():save(path,value)

def persist(root,report):
    directory=root/'data/aerial/skyline'
    def merge(state):
        if state.get('generated_at','')>report['generated_at']:
            raise ValueError('Cannot replace a newer Skyline report')
        for kind in ('forecasts','outcomes'):
            records=state.setdefault(kind,{})
            for p in sorted((directory/kind).glob('*.json')):
                value=read(p)
                if p.stem in records and records[p.stem]!=value:raise ValueError('Conflicting private Skyline record')
                records[p.stem]=value
        state.update(generated_at=report['generated_at'],report=report)
    update(root,merge)
