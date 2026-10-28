"""Private primary Skyline paper alerts, using the immutable forecast price."""
from datetime import datetime, timezone, timedelta
import os
import paddy_headed
from zoneinfo import ZoneInfo
from aerial_alerts import send
from skyline_model import utc
from skyline_store import fetch, update

VARIANT='baseline'

def eligible(record, state, now):
    try:
        report=state.get('report',{})
        return (record['version']=='skyline-v1'
            and record['cohort']=='prospective_paper' and record['lineup']=='confirmed'
            and record['selections'].get(VARIANT) is True
            and record['key'] not in state.get('alerts',{})
            and record['key'] not in state.get('outcomes',{})
            and record['model_sha256']==report['model_sha256']
            and VARIANT in report.get('stats',{})
            and any(r.get('key')==record['key'] and r.get('lineup')=='confirmed' for r in report.get('board',[]))
            and (record['quote'].get('bookmaker')=='Bet365' or
                 (paddy_headed.DIRECT_COLLECTION_ENABLED and record['quote'].get('bookmaker')=='Paddy Power' and record['quote'].get('contract') in ('paddy_super_sub_v1','paddy_named_player_v1')))
            and report.get('status')=='CAPTURING'
            and timedelta(0)<=now-utc(report['generated_at'])<=timedelta(hours=3)
            and timedelta(0)<=now-utc(record['captured_at'])<=timedelta(hours=2)
            and timedelta(0)<=now-utc(record['lineup_observed_at'])<=timedelta(hours=2)
            and timedelta(0)<=now-utc(record['quote']['captured_at'])<=timedelta(hours=2)
            and now+timedelta(minutes=5)<utc(record['kickoff'])
            and 0<record['predictions'][VARIANT]<1 and record['odds']>1)
    except (KeyError,TypeError,ValueError):return False

def message(record, state, now):
    # Use the monitor's exact totals, including its settlement-conflict holds.
    stats=state['report']['stats'][VARIANT]
    p=record['predictions'][VARIANT]
    kickoff=utc(record['kickoff']).astimezone(ZoneInfo('Europe/London'))
    quote=utc(record['quote']['captured_at']).astimezone(ZoneInfo('Europe/London'))
    lines=['SKYLINE v1 | PAPER ONLY | BASELINE',record['match'],
        record['player']+' | 1+ headed shot on target',
        f"{record['quote'].get('bookmaker','Bet365')} recorded odds: {record['odds']:.2f}",
        f'Model fair odds: {1/p:.2f} | Estimated EV: {(p*record["odds"]-1)*100:+.1f}%',
        f'Estimated chance: {p*100:.1f}% | CONFIRMED XI',
        f'Kickoff: {kickoff:%d %b %H:%M %Z}',f'Price captured: {quote:%d %b %H:%M %Z}','',
        'Skyline baseline forward paper record:']
    if stats['settled']:
        lines += [f"ROI: {stats['roi']:+.1f}% | Profit: {stats['profit']:+.2f}u",
            f"{stats['wins']}W / {stats['losses']}L | {stats['settled']} settled | {stats['settled_stake']:.0f}u staked"]
    else:lines += ['No settled selections yet; ROI not established.']
    lines += [f"{stats['pending']} pending | {stats['void']} void",'',
        '1u paper tracking, zero real stake. Experimental selection, not an established edge.',
        'Original price locked for the record. Check current bookmaker odds and market terms.',
        'Admin > Monitor > Skyline: https://ilmargine.bet/admin']
    if record['quote'].get('contract')=='paddy_super_sub_v1':
        lines.insert(7,'Paddy Super Sub: replacement counts for settlement. Fair odds/EV above use the named player only; no promotion uplift.')
    return '\n'.join(lines)

def run(root, now=None, transmit=False, sender=send, reader=fetch, writer=update):
    now=now or datetime.now(timezone.utc)
    row=reader(root)
    if not row:return {'status':'no_snapshot','eligible':0,'sent':0}
    state=row['payload']
    records=sorted(state.get('forecasts',{}).values(),key=lambda r:(r['kickoff'],r['key']))
    records=[r for r in records if eligible(r,state,now)]
    result={'status':'no_new_qualifiers' if not records else 'preview','eligible':len(records),'sent':0,'uncertain':0}
    if not transmit or not records:return result
    token=os.environ.get('OPS_ALERT_TELEGRAM_BOT_TOKEN','').strip()
    chat=os.environ.get('OPS_ALERT_TELEGRAM_CHAT_ID','').strip()
    if not token or not chat:return {**result,'status':'credentials_missing'}
    for record in records:
        key=record['key'];prepared={}
        def claim(current):
            r=current.get('forecasts',{}).get(key,{})
            if not eligible(r,current,now):return False
            prepared['text']=message(r,current,now)
            current.setdefault('alerts',{})[key]={'variant':VARIANT,'status':'reserved',
                'reserved_at':now.isoformat()}
        # Persist before delivery. A timeout or crash is held, never blindly resent.
        if not writer(root,claim):continue
        receipt=sender(prepared['text'],token,chat)
        def finish(current):
            current['alerts'][key].update(status='sent' if receipt is not None else 'delivery_uncertain',
                message_id=receipt,attempted_at=now.isoformat())
        writer(root,finish)
        result['sent' if receipt is not None else 'uncertain']+=1
    result['status']='delivery_uncertain' if result['uncertain'] else 'sent' if result['sent'] else 'already_claimed'
    return result
