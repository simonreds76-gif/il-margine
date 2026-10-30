"""Operational paper delivery only; the frozen DF probabilities remain untouched."""
from datetime import datetime,timezone,timedelta
from hashlib import sha256
from pathlib import Path
import json

REL=Path('data/tennis-props/shadow/most-df-v1')
def read(p): return json.loads(p.read_bytes())
def hashed(p): return sha256(p.read_bytes()).hexdigest()
def utc(v):
    try:
        d=datetime.fromisoformat(v.replace('Z','+00:00'))
        return d if d.tzinfo else None
    except (TypeError,ValueError,AttributeError):return None

def activated(root,registration,now=None):
    now=now or datetime.now(timezone.utc);folder=root/REL
    try:
        a=read(folder/'delivery-activation.json');effective=utc(a.get('effective_at'))
        return (a['scope']=='most-df-paper-delivery-only' and a['pricing_changed'] is False
            and a['real_stake']==0 and a['paper_stake']==1 and effective is not None and effective<=now
            and a['registration_sha256']==hashed(folder/'registration.json')
            and a['original_code_sha256']==registration['code_sha256']
            and a['current_code_sha256']==hashed(root/'scripts/tennis_most_df.py')
            and a['delivery_code_sha256']==hashed(root/'scripts/tennis_most_df_delivery.py')
            and a['model_sha256']==registration['model_sha256']==hashed(root/'scripts/tennis_props_model.py'))
    except (OSError,ValueError,KeyError,TypeError):return False

def alert_rows(root,*,now=None):
    """Never replay an old, started, changed-price or already-settled capture."""
    from tennis_most_df import current_prices,csvrows,select
    now=now or datetime.now(timezone.utc);folder=root/REL
    try:
        reg=read(folder/'registration.json');report=read(folder/'report.json')
        if not activated(root,reg,now):return []
        generated=utc(report.get('generated_at'))
        if not generated or not timedelta(0)<=now-generated<=timedelta(hours=2):return []
        outcomes=read(folder/'outcomes.json')
        quotes=csvrows(root/'data/tennis-props/inbox'/f'most-df-1x2-{now.date().isoformat()}.csv')
        rows=[]
        for p in sorted((folder/'captures').glob('*.json')):
            r=read(p);s=r['selection'];start=utc(r['start']);captured=utc(r['captured_at'])
            if (r['id'] in outcomes or not s['selected'] or not start or start<=now or not captured
                or not timedelta(0)<=now-captured<=timedelta(minutes=30)
                or r['registration_sha256']!=hashed(folder/'registration.json')):continue
            inputs={x['player_id']:x for x in r['inputs']}
            prices,reason=current_prices(quotes,inputs[r['players'][0]],inputs[r['players'][1]],now)
            if reason:continue
            _,current=select(prices,r['probabilities'])
            # Entry odds and ROI stay frozen. A changed quote is not advertised as current.
            if (not current['selected'] or current['outcome']!=s['outcome']
                or current['bookmaker']!=s['bookmaker'] or abs(current['odds']-s['odds'])>1e-8):continue
            rows.append(r)
        return rows
    except (OSError,ValueError,KeyError,TypeError):return []
