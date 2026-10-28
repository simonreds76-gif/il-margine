"""Existing PC poller: bounded price capture only; cloud owns forecasts/alerts."""
import json
import os
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path
import requests
from aerial_data import read, save, utc
from paddy_headed import capture
from skyline_store import update

PUBLIC_AERIAL='https://jsuu8rjgs8aaukun.public.blob.vercel-storage.com/fair-odds-lab/aerial.json'


def publish(root, prices, status, writer=update):
    def change(state):
        current=state.setdefault('source_prices',{}).get('paddy',{})
        if current.get('status',{}).get('generated_at','') >= status['generated_at']:
            return False
        state['source_prices']['paddy']={'prices':prices,'status':status}
    return writer(root,change)


def run(root, now=None, get=requests.get, collector=capture, writer=update):
    now=now or datetime.now(timezone.utc)
    if os.environ.get('GITHUB_ACTIONS') == 'true': return {'status':'LOCAL_ONLY'}
    directory=root/'data/aerial/paddy'
    previous=read(directory/'bridge.json',{})
    if previous.get('next_attempt_at') and now < utc(previous['next_attempt_at']):
        return {'status':'NOT_DUE'}
    directory.mkdir(parents=True,exist_ok=True)
    lock=directory/'bridge.lock'
    if lock.exists() and now-utc(lock.read_text()) > timedelta(minutes=20):
        lock.unlink()
    try:
        with lock.open('x') as handle: handle.write(now.isoformat())
    except FileExistsError:
        return {'status':'LOCKED'}
    status=None
    result={'status':'FAILED','error':'Interrupted'}
    try:
        response=get(PUBLIC_AERIAL,timeout=15);response.raise_for_status()
        payload=response.json()
        if not isinstance(payload.get('fixtures'),list) or not timedelta(0) <= now-utc(payload['generated_at']) <= timedelta(hours=2):
            raise ValueError('Public fixture snapshot missing or stale')
        status=collector(root,payload,now=now)
        prices=read(directory/'prices.json',{'generated_at':now.isoformat(),'events':[]})
        saved=publish(root,prices,status,writer)
        result={'status':'PUBLISHED' if saved else 'NEWER_CAPTURE_EXISTS','source_status':status['status'],
                'headed_sot':status.get('headed_sot',0),'headed_goals':status.get('headed_goals',0)}
    except Exception as exc:
        result={'status':'FAILED','error':type(exc).__name__}
    finally:
        delay=timedelta(hours=24) if status and status.get('http_status') in (403,429) else timedelta(minutes=30)
        save(directory/'bridge.json',dict(result,attempted_at=now.isoformat(),next_attempt_at=(now+delay).isoformat()))
        lock.unlink(missing_ok=True)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    result=run(parser.parse_args().root)
    if result['status']!='NOT_DUE':print('Paddy local bridge: '+json.dumps(result))
