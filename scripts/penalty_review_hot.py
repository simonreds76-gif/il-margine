"""Incremental completed-match penalty review, independent of goalscorer tiers.

Uses the existing evidence and editorial rules. No hierarchy/model changes.
At most two daily listings and sixteen previously unchecked completed matches.
Overnight scans still reconcile delayed corrections across the wider window.
"""
import copy
import argparse
from datetime import datetime, timedelta, timezone
import importlib.util
import json
import os
from pathlib import Path
import sys


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def evidence_ids(row):
    return {str(e['match_id']) for e in row.get('event_evidence', []) if e.get('match_id')}


def merge_rows(old, fresh, replaced, earliest):
    kept = [r for r in old if r.get('date','') >= earliest and not evidence_ids(r).intersection(replaced)]
    return sorted(kept + fresh, key=lambda r:(r.get('date',''),r.get('match',''),r.get('actual_taker','')), reverse=True)


def run(root, now=None):
    now = now or datetime.now(timezone.utc)
    root = Path(root)
    sys.path.insert(0, str(root/'scripts'))
    review = load('hot_penalty_evidence', root/'scripts/goalscorer-live-penalty-review.py')
    alerts = load('hot_penalty_alerts', root/'scripts/club-penalty-review-alert.py')
    state_path = root/'data/goalscorer/penalty-hot-capture-state.json'
    state = json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else {'checked':{}}
    earliest = (now-timedelta(days=8)).date().isoformat()
    state['checked'] = {k:v for k,v in state['checked'].items() if v >= earliest}
    dates = [(now-timedelta(days=i)).strftime('%Y%m%d') for i in (1,0)]
    fetch = review._fetch_json
    days = {d:fetch(review.MATCHES_URL, {'date':d,'timezone':'Europe/London','ccode3':'GBR'}) for d in dates}
    league_ids = {c['league_id'] for c in review.LEAGUE_CONFIGS.values()}
    eligible = []
    for day in days.values():
        for league in day.get('leagues',[]):
            if league.get('id') not in league_ids:
                continue
            for m in league.get('matches',[]):
                s=m.get('status') or {}
                if s.get('finished') and not s.get('cancelled') and not s.get('awarded') and str(m['id']) not in state['checked']:
                    eligible.append(m)
    chosen = {str(m['id']) for m in sorted(eligible,key=lambda m:m['status']['utcTime'])[:16]}
    if not chosen and state_path.exists():
        print('Penalty hot capture: no unchecked completed matches; no files changed.')
        return state
    for day in days.values():
        for league in day.get('leagues',[]):
            league['matches']=[m for m in league.get('matches',[]) if str(m['id']) in chosen]
    review._fetch_json = lambda url, params: copy.deepcopy(days[params['date']]) if url == review.MATCHES_URL else fetch(url,params)
    failures=[]
    for name, config in review.LEAGUE_CONFIGS.items():
        ids={str(m['id']) for day in days.values() for league in day.get('leagues',[]) if league.get('id')==config['league_id'] for m in league['matches']}
        if not ids:
            continue
        health={}
        fresh=review.build_live_review_rows(name,dates,health)
        failed={str(e.get('match_id')) for e in health.get('errors',[])}
        failures.extend(health.get('errors',[]))
        safe=ids-failed
        fresh=[r for r in fresh if not evidence_ids(r).intersection(failed)]
        path=config['output_json']
        old=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'rows':[]}
        rows=merge_rows(old['rows'],fresh,safe,earliest)
        review._write_csv(config['output_csv'],rows)
        review._write_json(path,{**old,'schema_version':1,'league':name,'generated_at':now.isoformat(),'row_count':len(rows),'rows':rows,'hot_source_health':health})
        # Unknown timeline is retryable, not marked as fully collected.
        uncertain=set().union(*(evidence_ids(r) for r in fresh if not alerts.has_reliable_pitch_context(r))) if fresh else set()
        for mid in safe-uncertain:
            state['checked'][mid]=now.date().isoformat()
    state.update(updated_at=now.isoformat(),checked_this_run=len(chosen),errors=failures)
    state_path.parent.mkdir(parents=True,exist_ok=True)
    tmp=state_path.with_suffix('.tmp');tmp.write_text(json.dumps(state,indent=2)+'\n',encoding='utf-8');tmp.replace(state_path)
    print(f'Penalty hot capture: {len(chosen)} completed matches checked, {len(failures)} source errors; existing queues preserved.')
    if failures:
        print('::warning::Some penalty match evidence remains retryable; see penalty-hot-capture-state.json')
    return state


def notify(root, dry_run=False):
    root=Path(root)
    sys.path.insert(0,str(root/'scripts'))
    alerts=load('hot_penalty_notify',root/'scripts/club-penalty-review-alert.py')
    state_path=root/alerts.DEFAULT_ALERT_STATE
    if state_path.exists():
        saved=json.loads(state_path.read_text(encoding='utf-8'))
        if not isinstance(saved.get('items'),dict):
            raise ValueError('Invalid delivery history; no alerts sent')
    state=alerts.load_alert_state(state_path)
    reviews=alerts.load_reviews()
    # From installation onward, being in yesterday's queue is NOT proof that
    # Telegram received it. The durable delivery ledger and Admin decisions win.
    previous=[r for r in alerts.previous_rows(alerts.REVIEW_FILES,'HEAD') if r.get('date','') < '2026-10-25']
    rows=alerts.new_actionable_rows(alerts.current_rows(alerts.REVIEW_FILES),previous,alerts.priority_hierarchy_teams(),set(state['items']),reviews)
    token=os.environ.get('OPS_ALERT_TELEGRAM_BOT_TOKEN','')
    chat=os.environ.get('OPS_ALERT_TELEGRAM_CHAT_ID','')
    if rows and not dry_run and (not token or not chat):
        raise ValueError('Penalty alert credentials missing; delivery remains pending')
    for start in range(0,len(rows),4):
        batch=rows[start:start+4]
        message=alerts.build_message(batch,os.environ.get('PENALTY_REVIEW_URL',alerts.DEFAULT_REVIEW_URL))
        if dry_run:
            print(message)
        else:
            alerts.send_telegram(message,token,chat)
            alerts.write_alert_state(state_path,state,batch)
            state=alerts.load_alert_state(state_path)
    print(f'Penalty review notification: {len(rows)} new actionable ticket(s), dry_run={dry_run}.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--notify',action='store_true')
    parser.add_argument('--dry-run',action='store_true')
    args=parser.parse_args()
    root=os.environ.get('PENALTY_RUNTIME_ROOT',os.getcwd())
    if args.notify:notify(root,args.dry_run)
    else:run(root)
