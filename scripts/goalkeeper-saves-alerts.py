#!/usr/bin/env python3
"""Claim and notify newly registered GK signals; never resend an ambiguous attempt.

--prepare runs before the evidence commit. --send runs only after that commit
has been pushed. Claims survive failed sends and reruns (manual review required).
"""
import argparse
import csv
from datetime import datetime, timezone, timedelta
import html
import json
import os
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'data/goalkeeper-saves'
STATE = FOLDER / 'gk-saves-telegram-state.json'
LEDGER = FOLDER / 'gk-saves-v1-shadow-signals.csv'

def stamp(value):
    try:
        d = datetime.fromisoformat(str(value or '').replace('Z', '+00:00'))
        return d if d.tzinfo else None
    except ValueError:
        return None

def eligible(row, now):
    created, captured, kickoff = [stamp(row.get(k)) for k in ('created_at','captured_at','kickoff_at')]
    if not all((created,captured,kickoff)) or not (kickoff > now and timedelta(0) <= now-created <= timedelta(hours=6) and timedelta(0) <= now-captured <= timedelta(hours=6)):
        return False
    if str(row.get('status','')).lower() != 'pending' or row.get('duplicate_of') or row.get('quarantine_reason') or 'quarantin' in row.get('integrity_status',''):
        return False
    try:
        return bool(row.get('signal_id')) and float(row['edge']) >= .05 and 1.7 <= float(row['odds_decimal']) <= 3 and row.get('selection_policy') == 'near_even_value_v2'
    except (ValueError, KeyError):
        return False

def claim(rows, state, token, now):
    entries = state.setdefault('signals', {})
    added = 0
    for row in rows:
        key = row.get('signal_id','')
        if key in entries or not eligible(row, now) or added >= 10:
            continue
        entries[key] = {'status':'claimed','run_token':token,'claimed_at':now.isoformat(), 'signal':dict(row)}
        added += 1
    return added

def message(row):
    e = lambda k: html.escape(str(row.get(k) or ''))
    return ('<b>GK saves | New tracked signal</b>\n\n'
        f"<b>{e('home_team')} vs {e('away_team')}</b>\n"
        f"{e('goalkeeper')} - {e('side').title()} {e('line')} saves\n"
        f"Bet365 recorded odds: <b>{float(row['odds_decimal']):.2f}</b>\n"
        f"Model fair odds: {float(row['fair_odds']):.2f} | Estimated EV: +{float(row['edge'])*100:.1f}%\n"
        f"Kickoff: {e('kickoff_at')}\nCaptured: {e('captured_at')}\n"
        f"Lineup: {e('lineup_status').replace('_',' ')}\n\n"
        'Original odds are locked for tracking. Check the current bookmaker price before betting.\n'
        'Research model; 0.5u paper tracking, not a proven edge.')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare',action='store_true');p.add_argument('--send',action='store_true');p.add_argument('--state',type=Path,default=STATE);p.add_argument('--ledger',type=Path,default=LEDGER);a=p.parse_args()
    if a.prepare == a.send: p.error('Choose exactly one of --prepare or --send')
    token = os.environ.get('GITHUB_RUN_ID','') + ':' + os.environ.get('GITHUB_RUN_ATTEMPT','')
    bot=os.environ.get('OPS_ALERT_TELEGRAM_BOT_TOKEN','').strip();chat=os.environ.get('OPS_ALERT_TELEGRAM_CHAT_ID','').strip()
    if not bot or not chat or token==':': raise SystemExit('GK alerts require the configured ops Telegram destination and a workflow run token')
    state=json.loads(a.state.read_text(encoding='utf-8')) if a.state.exists() else {'signals':{}}
    def save():
        a.state.parent.mkdir(parents=True,exist_ok=True);tmp=a.state.with_suffix('.tmp');tmp.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');tmp.replace(a.state)
    if a.prepare:
        with a.ledger.open(encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
        count=claim(rows,state,token,datetime.now(timezone.utc));save();print(f'GK alert claims prepared: {count}');return
    failed=0;sent=0
    for item in state['signals'].values():
        if item.get('status')!='claimed' or item.get('run_token')!=token: continue
        if not eligible(item['signal'],datetime.now(timezone.utc)):
            item['status']='expired_before_send';save();continue
        # Persist uncertainty before HTTP. A replay cannot assume Telegram rejected it.
        item['status']='delivery_unconfirmed';save()
        try:
            r=requests.post(f'https://api.telegram.org/bot{bot}/sendMessage',json={'chat_id':chat,'text':message(item['signal']),'parse_mode':'HTML','disable_web_page_preview':True},timeout=20)
            payload=r.json()
            # A structured rejection confirms that this attempt was not accepted.
            # Never persist the response text or exception URL: either can expose credentials.
            if payload.get('ok') is False:
                item.update(status='delivery_rejected',error_kind='telegram_rejected',http_status=r.status_code)
                failed+=1;save();print(f'GK alert rejected: HTTP {r.status_code}; review required');continue
            if not r.ok or payload.get('ok') is not True: raise ValueError('Invalid Telegram response')
            item.update(status='sent',message_id=payload['result']['message_id'],sent_at=datetime.now(timezone.utc).isoformat());sent+=1
        except Exception as exc:
            kind = ('timeout' if isinstance(exc, requests.exceptions.Timeout) else
                    'connection_error' if isinstance(exc, requests.exceptions.ConnectionError) else
                    'invalid_response' if isinstance(exc, (ValueError, KeyError, TypeError)) else 'delivery_error')
            item['error_kind']=kind
            failed+=1
            print(f'GK alert delivery unconfirmed: {kind}; review required')
        save()
    print(f'GK alerts: {sent} sent; {failed} failed or unconfirmed; no automatic resend of ambiguous deliveries')
    if failed: raise SystemExit(1)

if __name__=='__main__':main()
