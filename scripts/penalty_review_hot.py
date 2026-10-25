"""Incremental completed-match penalty review, independent of goalscorer tiers.

Uses the existing evidence and editorial rules. No hierarchy/model changes.
At most three daily listings and sixteen due matches, including durable backlog.
Overnight scans still reconcile delayed corrections across the wider window.
"""
import copy
import argparse
from datetime import datetime, timedelta, timezone
import importlib.util
import json
import os
import re
from pathlib import Path
import sys


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def evidence_ids(row):
    return {str(e['match_id']) for e in row.get('event_evidence', []) if e.get('match_id')}


def merge_rows(old, fresh, replaced, earliest, retain=()):
    kept = [r for r in old if (r.get('date','') >= earliest or evidence_ids(r).intersection(retain)) and not evidence_ids(r).intersection(replaced)]
    return sorted(kept + fresh, key=lambda r:(r.get('date',''),r.get('match',''),r.get('actual_taker','')), reverse=True)


def select_due(fixtures, now, limit=16):
    """Never let repeatedly failing older games monopolise the bounded batch."""
    due=[(mid,f) for mid,f in fixtures.items() if f['state'] not in {'verified','excluded'}
         and datetime.fromisoformat(f['match']['status']['utcTime'].replace('Z','+00:00')) <= now-timedelta(hours=3)
         and (not f.get('next_attempt') or datetime.fromisoformat(f['next_attempt']) <= now)]
    return sorted(due,key=lambda item:(item[1].get('last_attempt',''),item[1]['match']['status']['utcTime'],item[0]))[:limit]


def validate_payload(payload, fixture):
    v=payload.get('props',{}).get('pageProps',{})
    g=v.get('general') or {};h=(v.get('header') or {}).get('status') or {};c=v.get('content') or {}
    m=fixture['match']
    if str(g.get('matchId')) != str(m['id']):raise ValueError('match_identity_mismatch')
    if g.get('parentLeagueId',g.get('leagueId')) != fixture['league_id']:raise ValueError('competition_identity_mismatch')
    if [g.get(k+'Team',{}).get('id') for k in ('home','away')] != [m[k]['id'] for k in ('home','away')]:raise ValueError('participant_identity_mismatch')
    if not all(g.get(k+'Team',{}).get('name') for k in ('home','away')) or not g.get('matchTimeUTCDate'):raise ValueError('missing_match_metadata')
    if g.get('finished') is not True or h.get('finished') is not True or h.get('cancelled') or h.get('awarded'):raise ValueError('match_not_confirmed_complete')
    shots=(c.get('shotmap') or {}).get('shots')
    if not isinstance(shots,list) or not shots:raise ValueError('empty_or_missing_shotmap')
    teams={m['home']['id'],m['away']['id']}
    if any(shot.get('teamId') not in teams for shot in shots):raise ValueError('unrecognized_shot_team')
    score=re.fullmatch(r'\s*(\d+)\s*-\s*(\d+)\s*',str(h.get('scoreStr','')))
    # Own goals also contribute to the total, regardless of shot team attribution.
    goals=sum(s.get('eventType')=='Goal' for s in shots if s.get('period')!='PenaltyShootout')
    if not score or goals != sum(map(int,score.groups())):raise ValueError('shotmap_score_disagreement')
    feed=(c.get('matchFacts') or {}).get('events') or {}
    if feed.get('ongoing') is not False or not isinstance(feed.get('events'),list):raise ValueError('incomplete_event_timeline')
    penalties=[shot for shot in shots if str(shot.get('situation','')).lower()=='penalty' and str(shot.get('period','')).lower()!='penaltyshootout']
    if any(not shot.get('id') or not shot.get('playerId') or not (shot.get('fullName') or shot.get('playerName')) for shot in penalties):raise ValueError('incomplete_penalty_identity')
    ids={str(shot['id']) for shot in penalties}
    for event in feed['events']:
        if event.get('isPenaltyShootoutEvent'):continue
        linked=event.get('shotmapEvent') or {}
        is_pen=(linked.get('situation')=='Penalty' or str(event.get('goalDescriptionKey','')).lower() in {'penalty','penalty_missed','missed_penalty'}
                or str(event.get('type','')).lower() in {'missedpenalty','penaltymissed'})
        if not is_pen:continue
        if linked.get('id'):
            if str(linked['id']) not in ids:raise ValueError('penalty_event_shotmap_disagreement')
        else:
            # FotMob's MissedPenalty events omit shotmapEvent. Join only an
            # unambiguous exact player, side and minute, never by display name.
            player=event.get('playerId') or (event.get('player') or {}).get('id')
            side=event.get('isHome')
            team=m['home']['id'] if side is True else m['away']['id'] if side is False else None
            matches=[s for s in penalties if s.get('playerId')==player and s.get('teamId')==team
                     and str(s.get('min'))==str(event.get('time'))
                     and (s.get('minAdded') or 0)==(event.get('overloadTime') or 0)]
            if len(matches)!=1:raise ValueError('penalty_event_shotmap_disagreement')
    return ids


def run(root, now=None):
    now=now or datetime.now(timezone.utc);root=Path(root)
    sys.path.insert(0,str(root/'scripts'))
    review=load('hot_penalty_evidence',root/'scripts/goalscorer-live-penalty-review.py')
    alerts=load('hot_penalty_alerts',root/'scripts/club-penalty-review-alert.py')
    path=root/'data/goalscorer/penalty-hot-capture-state.json'
    state=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    # Legacy checked IDs are not evidence of the stricter complete-match contract.
    fixtures=state.setdefault('fixtures',{});state['schema_version']=2
    discovery=state.setdefault('discovery',{})
    today=now.strftime('%Y%m%d');yesterday=(now-timedelta(days=1)).strftime('%Y%m%d')
    dates=[yesterday,today]
    # Calendar gaps survive even a prolonged scheduler outage.
    if state.get('updated_at'):
        cursor=datetime.fromisoformat(state['updated_at']).date()
        while cursor <= now.date():
            discovery.setdefault(cursor.strftime('%Y%m%d'),{'ok':False,'reason':'not_discovered','checked_at':''})
            cursor+=timedelta(days=1)
    outstanding=sorted((d for d,v in discovery.items() if not v.get('ok') and d not in dates),key=lambda d:(discovery[d].get('checked_at',''),d))
    older=[(now-timedelta(days=i)).strftime('%Y%m%d') for i in range(8,1,-1)]
    extra=(outstanding or [d for d in older if d not in discovery] or sorted(older,key=lambda d:discovery[d].get('checked_at','')))[:1]
    dates+=extra
    fetch=review._fetch_json;by_id={v['league_id']:k for k,v in review.LEAGUE_CONFIGS.items()}
    for date in dates:
        try:
            day=fetch(review.MATCHES_URL,{'date':date,'timezone':'Europe/London','ccode3':'GBR'})
            if not isinstance(day.get('leagues'),list):raise ValueError('invalid_daily_listing')
            discovered=0;listing_errors=[]
            for league in day['leagues']:
                lid=league.get('primaryId',league.get('id'))
                if lid not in by_id:continue
                matches=league.get('matches')
                if not isinstance(matches,list):
                    listing_errors.append('missing_league_matches:'+str(lid));continue
                for m in matches:
                    try:
                        status=m.get('status') or {}
                        if not m.get('id') or not status.get('utcTime') or not all((m.get(k) or {}).get('id') for k in ('home','away')):raise ValueError('incomplete_fixture_listing')
                        kickoff=datetime.fromisoformat(status['utcTime'].replace('Z','+00:00'))
                        if kickoff.tzinfo is None:raise ValueError('missing_fixture_timezone')
                        mid=str(m['id']);old=fixtures.get(mid,{})
                        stub={k:copy.deepcopy(m[k]) for k in ('id','home','away','status')}
                        changed=old and (any(old['match'][k]!=stub[k] for k in ('home','away')) or old['match']['status']['utcTime']!=stub['status']['utcTime'])
                        entry={**old,'league':by_id[lid],'league_id':lid,'match':stub,'date':status['utcTime'][:10]}
                        entry.setdefault('state','pending');entry.setdefault('first_seen',now.isoformat())
                        if changed:entry.update(state='pending',reason='fixture_changed',next_attempt='')
                        if status.get('cancelled') or status.get('awarded'):entry.update(state='excluded',reason='cancelled_or_awarded')
                        fixtures[mid]=entry;discovered+=1
                    except Exception as exc:
                        listing_errors.append(str(exc) if isinstance(exc,ValueError) else type(exc).__name__)
            if listing_errors:raise ValueError('incomplete_listing:'+','.join(sorted(set(listing_errors))))
            if discovered < discovery.get(date,{}).get('expected',0):raise ValueError('daily_listing_coverage_drop')
            discovery[date]={'ok':True,'checked_at':now.isoformat(),'expected':discovered}
        except Exception as exc:
            discovery[date]={**discovery.get(date,{}),'ok':False,'checked_at':now.isoformat(),'reason':str(exc) if isinstance(exc,ValueError) else type(exc).__name__}
    for f in fixtures.values():
        if f['state']=='verified' and f['date'] >= (now-timedelta(days=8)).date().isoformat() and datetime.fromisoformat(f['verified_at']) <= now-timedelta(hours=24):
            f.update(state='pending',reason='daily_reconciliation',next_attempt='')
    chosen=select_due(fixtures,now)
    failures=[];raw_fetch=review._fetch_match_payload
    earliest=(now-timedelta(days=8)).date().isoformat()
    for mid,f in chosen:
        f.update(last_attempt=now.isoformat(),attempts=f.get('attempts',0)+1)
        try:
            payload=raw_fetch(int(mid));expected=validate_payload(payload,f)
            # Use the confirmed completed detail, even after an older pending game
            # has left all rolling calendar windows.
            m=copy.deepcopy(f['match']);m['status'].update(started=True,finished=True)
            day={'leagues':[{'id':f['league_id'],'matches':[m]}]}
            review._fetch_json=lambda url,params:copy.deepcopy(day) if url==review.MATCHES_URL else fetch(url,params)
            review._fetch_match_payload=lambda match_id:payload
            health={};fresh=review.build_live_review_rows(f['league'],[f['date'].replace('-','')],health)
            if not health.get('complete') or health.get('matches_checked')!=1:raise ValueError('incomplete_match_processing')
            emitted={str(e.get('source_event_id')) for r in fresh for e in r.get('event_evidence',[])}
            if expected!=emitted:raise ValueError('penalty_parse_coverage_mismatch')
            config=review.LEAGUE_CONFIGS[f['league']];out=config['output_json']
            old=json.loads(out.read_text(encoding='utf-8')) if out.exists() else {'rows':[]}
            rows=merge_rows(old['rows'],fresh,{mid},earliest,{k for k,v in fixtures.items() if v['state']=='pending'})
            review._write_csv(config['output_csv'],rows)
            review._write_json(out,{**old,'schema_version':1,'league':f['league'],'generated_at':now.isoformat(),'row_count':len(rows),'rows':rows,'hot_source_health':health})
            if any(not alerts.has_reliable_pitch_context(r) for r in fresh):raise ValueError('unresolved_player_timeline')
            f.update(state='verified',reason='penalties_verified' if expected else 'verified_no_penalty',verified_at=now.isoformat(),penalty_count=len(expected),next_attempt='')
        except Exception as exc:
            reason=str(exc) if isinstance(exc,ValueError) else type(exc).__name__
            f.update(state='pending',reason=reason,next_attempt=(now+timedelta(minutes=60)).isoformat())
            failures.append({'match_id':mid,'reason':reason})
        finally:
            review._fetch_match_payload=raw_fetch
    pending=[f for f in fixtures.values() if f['state']=='pending']
    overdue=[f for f in pending if datetime.fromisoformat(f['match']['status']['utcTime'].replace('Z','+00:00')) < now-timedelta(hours=24)]
    stalled=[f for f in overdue if datetime.fromisoformat(f['first_seen']) < now-timedelta(hours=24)]
    state.update(updated_at=now.isoformat(),checked={mid:f['verified_at'][:10] for mid,f in fixtures.items() if f['state']=='verified'},
        checked_this_run=len(chosen),errors=failures,coverage={'expected':len(fixtures),'verified':sum(f['state']=='verified' for f in fixtures.values()),'pending':len(pending),'overdue':len(overdue),'stalled':len(stalled),'excluded':sum(f['state']=='excluded' for f in fixtures.values()),'failed_discovery_days':[d for d,v in discovery.items() if not v['ok']]})
    path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');tmp.replace(path)
    print('Penalty coverage: '+json.dumps(state['coverage'])+'; processed '+str(len(chosen)))
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a',encoding='utf-8') as summary:
            summary.write('## Penalty match coverage\n'+json.dumps(state['coverage'])+'\n')
            for f in overdue:summary.write('- '+f['date']+' '+f['match']['home']['name']+' vs '+f['match']['away']['name']+': '+f.get('reason','awaiting check')+'\n')
    if overdue or state['coverage']['failed_discovery_days']:print('::warning::Penalty coverage is incomplete; unresolved fixtures remain in the durable queue.')
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
    parser.add_argument('--check-health',action='store_true')
    parser.add_argument('--dry-run',action='store_true')
    args=parser.parse_args()
    root=os.environ.get('PENALTY_RUNTIME_ROOT',os.getcwd())
    if args.check_health:
        health=json.loads((Path(root)/'data/goalscorer/penalty-hot-capture-state.json').read_text(encoding='utf-8'))['coverage']
        if health['stalled'] or health['failed_discovery_days']:raise SystemExit('Penalty coverage needs attention; inspect the durable queue and workflow summary')
    elif args.notify:notify(root,args.dry_run)
    else:run(root)
