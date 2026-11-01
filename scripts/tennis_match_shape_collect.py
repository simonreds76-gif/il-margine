"""Bounded ATP-only fallback inside the existing refresh. No new schedule.

The shared ATP/WTA collector's earliest twelve events can all be WTA. Only when
it provides no eligible ATP games contract, fetch at most four ATP events using
the same public Grosvenor source. No Odds-API credits or betting alerts.
"""
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import time
import requests
from tennis_grosvenor import BASE, PARAMS, eligible
from tennis_match_shape import RELATIVE, parse_receipt, refresh, digest, immutable, read


def collect(get=requests.get, max_events=4):
    now=datetime.now(timezone.utc);began=time.monotonic()
    receipt=dict(source=BASE,bookmaker='Grosvenor',captured_at=now.isoformat(),requests=0,events=[],errors=[],
                 collector_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),scope='ATP games paper fallback')
    def fetch(path):
        receipt['requests']+=1
        response=get(f'{BASE}/{path}.json',params=PARAMS,timeout=8)
        response.raise_for_status()
        return response.json()
    try:
        catalogue=fetch('listView/tennis/all/all/all/matches')
        events=[i['event'] for i in catalogue.get('events',[]) if eligible(i.get('event',{}),now)
                and any(p.get('termKey')=='atp' for p in i['event'].get('path',[]))]
        events=sorted({e['id']:e for e in events}.values(),key=lambda e:(e['start'],e['id']))
        receipt['eligible_atp_events']=len(events)
        for event in events[:min(4,max(0,max_events))]:
            if time.monotonic()-began>35:receipt['errors'].append('wall_budget');break
            try:
                payload=fetch(f"betoffer/event/{event['id']}")
                receipt['events'].append(dict(requested_id=event['id'],captured_at=datetime.now(timezone.utc).isoformat(),payload=payload))
            except (requests.RequestException,ValueError,KeyError,TypeError) as exc:
                receipt['errors'].append(f"{event['id']}:{type(exc).__name__}")
    except (requests.RequestException,ValueError,KeyError,TypeError) as exc:
        receipt['errors'].append(f'catalogue:{type(exc).__name__}')
    return receipt


def capture_shared(root,receipt):
    out=root/RELATIVE
    if not (out/'registration.json').exists():return {}
    clock=datetime.now(timezone.utc)
    if not parse_receipt(receipt,clock):
        receipt=collect()
    path=out/'quote-evidence'/(digest(receipt)+'.json')
    if not path.exists():immutable(path,receipt)
    return refresh(root,receipt=receipt)


def refresh_saved(root):
    """No network. Reconcile after forecast generation and settle on every upload."""
    out=root/RELATIVE
    if not (out/'registration.json').exists():return {}
    clock=datetime.now(timezone.utc)
    paths=sorted((out/'quote-evidence').glob('*.json'),key=lambda p:p.stat().st_mtime,reverse=True)[:4]
    for path in paths:
        if path.stat().st_size>32*1024*1024:continue
        receipt=read(path)
        if parse_receipt(receipt,clock):return refresh(root,clock,receipt=receipt)
    return refresh(root,clock,settle_only=True)
