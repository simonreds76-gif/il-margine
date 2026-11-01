"""Refresh native inputs before paper capture; never publish model forecasts.

Standalone props polling may run after OnCourt was updated but before the next
Admin refresh. Reuse the normal export and quick input sync, then run the exact
current model in dry-run mode. This is acquisition plumbing, not a new model.
"""
from datetime import datetime, timezone, timedelta
from pathlib import Path
import argparse
import csv
from collections import Counter
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import time
from unittest.mock import patch

from tennis_match_shape import RELATIVE, read, atomic, immutable, digest, utc, fresh_components, fingerprints
from tennis_hardcourt_scout import locked

DATABASE = Path('C:/Program Files (x86)/OnCourt/OnCourt.mdb')
PY32 = 'C:/Python312-32/python.exe'
INPUTS = ('today_atp.csv', 'players_atp.csv', 'tours_atp.csv', 'games_atp.csv', 'stat_atp.csv')


def metadata(path):
    if not path.exists():return None
    s=path.stat();return {'size':s.st_size,'mtime_ns':s.st_mtime_ns}


def source_state(root, database=DATABASE):
    return {'database':metadata(database),'exports':{n:metadata(root/'data/oncourt'/n) for n in INPUTS}}


def readiness(root, clock=None, database=DATABASE):
    clock=clock or datetime.now(timezone.utc);out=root/RELATIVE
    state=source_state(root,database);reg=read(out/'registration.json')
    if not reg:return {'ready':False,'reason':'not_registered','source':state}
    if any(not v or v['size']==0 for v in state['exports'].values()):
        return {'ready':False,'reason':'native_exports_missing','source':state}
    db=state['database']
    if db and any(v['mtime_ns']<db['mtime_ns'] for v in state['exports'].values()):
        return {'ready':False,'reason':'database_newer_than_exports','source':state}
    stamp,packet=fresh_components(root,out,clock,utc(reg['registered_at']))
    latest=max(v['mtime_ns'] for v in state['exports'].values())/1e9
    if db:latest=max(latest,db['mtime_ns']/1e9)
    if not packet or stamp.timestamp()+.001<latest:
        return {'ready':False,'reason':'forecast_predates_current_inputs','source':state}
    return {'ready':True,'reason':'current','source':state,'forecast_at':stamp.isoformat()}


def load_env(root):
    for name in ('.env.local','env.local'):
        p=root/name
        if p.exists():
            for line in p.read_text(encoding='utf-8-sig').splitlines():
                if line.strip() and not line.lstrip().startswith('#') and '=' in line:
                    k,v=line.split('=',1);os.environ.setdefault(k.strip(),v.strip().strip('"').strip("'"))


def run_stage(root, label, args, timeout):
    folder=root/RELATIVE/'preparation';folder.mkdir(parents=True,exist_ok=True)
    log=folder/(label+'.log')
    # Stream diagnostics so a timed-out refresh retains its last completed stage.
    # Three logs, replaced on retry; never serialize env/headers.
    try:
        with log.open('w',encoding='utf-8') as stream:
            result=subprocess.run(args,cwd=root,stdout=stream,stderr=subprocess.STDOUT,
                                  timeout=timeout,env={**os.environ,'PYTHONUNBUFFERED':'1'})
    finally:
        if log.exists() and log.stat().st_size>200000:
            log.write_text(log.read_text(encoding='utf-8',errors='replace')[-200000:],encoding='utf-8')
    if result.returncode:raise RuntimeError(label+'_failed_exit_'+str(result.returncode))


def verify_remote_schedule(root):
    """The legacy loader can log failed inserts and still exit zero: verify data."""
    import requests
    load_env(root)
    base=(os.environ.get('NEXT_PUBLIC_SUPABASE_URL') or os.environ.get('SUPABASE_URL') or '').rstrip('/')
    key=os.environ.get('SUPABASE_SERVICE_ROLE_KEY')
    if not base or not key:raise RuntimeError('schedule_verification_credentials_missing')
    source=root/'data/oncourt/today_atp.csv';before=hashlib.sha256(source.read_bytes()).hexdigest()
    with source.open(encoding='utf-8-sig',newline='') as f:local=list(csv.DictReader(f))
    if not 0<len(local)<=20000:raise RuntimeError('unexpected_schedule_size')
    cols=('tour_id','player1_id','player2_id','round_id','draw')
    def identity(r):return tuple(int(r.get(k) or 0) for k in cols)+(str(r.get('result') or '').strip(),)
    remote=[]
    for offset in range(0,len(local)+1000,1000):
        response=requests.get(base+'/rest/v1/oncourt_today',headers={'apikey':key,'Authorization':'Bearer '+key},
            params={'select':','.join(cols)+',result','limit':1000,'offset':offset,
                    'order':'tour_id.asc,round_id.asc,draw.asc,player1_id.asc,player2_id.asc'},timeout=15)
        response.raise_for_status();page=response.json()
        if not isinstance(page,list):raise RuntimeError('invalid_remote_schedule')
        remote.extend(page)
        if len(page)<1000:break
    if Counter(map(identity,remote))!=Counter(map(identity,local)):raise RuntimeError('remote_schedule_does_not_match_native_export')
    if hashlib.sha256(source.read_bytes()).hexdigest()!=before:raise RuntimeError('schedule_changed_during_sync_verification')
    return {'rows':len(remote),'native_schedule_sha256':before,'verified_at':datetime.now(timezone.utc).isoformat()}


def forecast_only(root):
    """Same engine and settings; no daily_fair_odds or other tracker writes."""
    load_env(root);sys.path.insert(0,str(root));sys.path.insert(0,str(root/'scripts'))
    import tennis_hardcourt_scout as scout
    import requests
    before=source_state(root);model_path=root/'scripts/oncourt-compute-fair-odds.py'
    model_sha=hashlib.sha256(model_path.read_bytes()).hexdigest();rows=[]
    def observe(_root, values, **kwargs):
        rows.extend(values);return 'Match Shape isolated paper components only'
    request=requests.sessions.Session.request
    def read_only(session, method, url, *args, **kwargs):
        if method.upper() not in ('GET','HEAD'):raise RuntimeError('paper_forecast_attempted_HTTP_write')
        return request(session,method,url,*args,**kwargs)
    spec=importlib.util.spec_from_file_location('_match_shape_current_dry_run',model_path)
    model=importlib.util.module_from_spec(spec);sys.modules[spec.name]=model;spec.loader.exec_module(model)
    with patch.object(scout,'capture_current',observe), patch.object(sys,'argv',[str(model_path),'--dry-run','--hardcourt-scout-capture']), \
         patch.object(requests.sessions.Session,'request',read_only):
        model.main()
    if not rows:raise RuntimeError('empty_paper_forecast')
    if source_state(root)!=before:raise RuntimeError('inputs_changed_during_forecast')
    if hashlib.sha256(model_path.read_bytes()).hexdigest()!=model_sha:raise RuntimeError('model_changed_during_forecast')
    packet={'schema_version':1,'captured_at':datetime.now(timezone.utc).isoformat(),'rows':rows,
            'payload_sha256':digest(rows),'model_file_sha256':model_sha,'native_source_state':before,
            'schedule_sha256':hashlib.sha256((root/'data/oncourt/today_atp.csv').read_bytes()).hexdigest(),
            'scope':'Current formula dry-run after native input refresh; no live forecast publication'}
    # Identical probabilities recomputed later are a fresh calculation, not a
    # timestamp rewrite of an older packet. Existing packets remain immutable.
    immutable(root/RELATIVE/'component-evidence'/(digest(packet)+'.json'),packet)
    print('Saved fresh Match Shape components:',len(rows))


def prepare(root, clock=None, database=DATABASE, runner=run_stage):
    clock=clock or datetime.now(timezone.utc);out=root/RELATIVE
    if not (out/'registration.json').exists():return {'ready':False,'reason':'not_registered','refreshed':False}
    with locked(out/'preparation'):
        status=readiness(root,clock,database)
        if status['ready']:return {**status,'refreshed':False}
        reg=read(out/'registration.json')
        if reg['fingerprints']!=fingerprints(root):raise RuntimeError('frozen_model_changed')
        previous=read(out/'preparation/status.json');last=utc(previous.get('checked_at'))
        if previous.get('state')=='FAILED' and previous.get('source')==status['source'] and last and clock-last<timedelta(minutes=15):
            return {**status,'ready':False,'refreshed':False,'reason':'input_refresh_retry_cooldown: '+previous.get('reason','failed')}
        load_env(root);started=status['source'];steps=[];began=time.monotonic()
        def stage(label,args,timeout):
            remaining=int(900-(time.monotonic()-began))
            if remaining<=0:raise RuntimeError('input_recovery_wall_budget')
            runner(root,label,args,min(timeout,remaining));steps.append(label)
        try:
            if status['reason'] in ('database_newer_than_exports','native_exports_missing'):
                if not started['database']:raise RuntimeError('native_database_unavailable')
                stage('export',[PY32,str(root/'scripts/oncourt-extract-all.py')],240)
                after=source_state(root,database)
                if after['database']!=started['database']:raise RuntimeError('database_changed_during_export')
                if any(not v or v['size']==0 or v['mtime_ns']<after['database']['mtime_ns'] for v in after['exports'].values()):
                    raise RuntimeError('native_export_did_not_refresh_all_required_files')
            # Uses the same established input sync as Admin refresh; historical
            # result/stat tables are skipped and pricing tables are untouched.
            stage('sync',[sys.executable,str(root/'scripts/oncourt-load-supabase.py'),'--quick','--current-players'],180)
            verified_schedule=verify_remote_schedule(root)
            before_forecast=source_state(root,database)
            stage('forecast',[sys.executable,str(root/'scripts/tennis_match_shape_prepare.py'),'--root',str(root),'--forecast-only'],600)
            if source_state(root,database)!=before_forecast:raise RuntimeError('inputs_changed_during_recovery')
            result=readiness(root,datetime.now(timezone.utc),database)
            if not result['ready']:raise RuntimeError(result['reason'])
            result.update(refreshed=True,state='READY',steps=steps,verified_schedule=verified_schedule,checked_at=datetime.now(timezone.utc).isoformat())
        except Exception as exc:
            # Surface a specific blocker; never proceed with the older schedule.
            result={'ready':False,'refreshed':False,'state':'FAILED','reason':type(exc).__name__+': '+str(exc),
                    'steps':steps,'checked_at':datetime.now(timezone.utc).isoformat(),'source':source_state(root,database)}
        atomic(out/'preparation/status.json',result);return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--forecast-only',action='store_true');a=p.parse_args()
    if a.forecast_only:forecast_only(a.root)
    else:
        result=prepare(a.root);print(json.dumps(result));raise SystemExit(0 if result['ready'] else 1)
