"""Append fixture-level coaches to existing, validated Football Atlas prices.

Bounded, cached weekly batch. No current-coach backfill, inferred prices or
website deployment. Missing/conflicting rows stay pending; the last archive is
replaced atomically only after validation. Run after the Football Atlas update.
"""
import argparse
from collections import defaultdict, Counter
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import time
import requests
from settlement_utils import normalize_team_name

ROOT=Path(__file__).resolve().parents[1]
LEAGUES={47:'premier-league',55:'serie-a',87:'la-liga',54:'bundesliga',53:'ligue-1'}
spec=importlib.util.spec_from_file_location('manager_builder',ROOT/'scripts/build-manager-atlas.py')
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)

def competition_id(group):
    """Provider group IDs may change; primaryId identifies the competition."""
    if not isinstance(group,dict):raise ValueError('Invalid competition group')
    value=group.get('primaryId')
    if value is None:value=group.get('id')
    try:return int(value)
    except (TypeError,ValueError):return None

def normalize_day(payload):
    if not isinstance(payload,dict) or not isinstance(payload.get('leagues'),list):
        raise ValueError('Invalid date-feed schema')
    result=[];seen={}
    for group in payload['leagues']:
        league=LEAGUES.get(competition_id(group))
        if league is None:continue
        if not isinstance(group.get('matches'),list):raise ValueError('Invalid league match list')
        matches=[]
        for match in group['matches']:
            if (not isinstance(match,dict) or not match.get('id')
                    or any(not isinstance(match.get(side),dict) or not match[side].get('name') for side in ('home','away'))):
                raise ValueError('Invalid date-feed fixture identity')
            key=str(match['id']);signature=(league,match)
            if key in seen:
                if seen[key]!=signature:raise ValueError('Conflicting duplicate provider fixture')
                continue
            seen[key]=signature;matches.append(match)
        result.append({'league':league,'matches':matches})
    return result

HOLD_CODES={'fixture_not_unique','unfinished','source_unavailable','invalid_evidence',
            'fixture_conflict','identity_review','batch_limit','date_limit'}

def cache_usable(path,offline=False):
    # Pending evidence can arrive late. A cached absence or coach payload must
    # not freeze a fixture forever. Offline verification never downloads.
    if not path.exists():return False
    if offline:return True
    try:
        stamp=datetime.fromisoformat(json.loads(path.read_text(encoding='utf-8'))['checkedAt'])
        if stamp.tzinfo is None:return False
        return 0<=time.time()-stamp.timestamp()<86400
    except (ValueError,KeyError,TypeError):return False

def fixture_quarantine_complete(candidates,added,pending):
    wanted=[r[0] for r in candidates];valid=[r['id'] for r in added];held=[r['id'] for r in pending]
    return (len(set(wanted))==len(wanted) and len(set(valid))==len(valid)
            and len(set(held))==len(held) and not set(valid)&set(held)
            and set(valid)|set(held)==set(wanted)
            and all(p.get('code') in HOLD_CODES and p.get('reason')
                    and p.get('date') and p.get('home') and p.get('away') for p in pending))

def save_pending_queue(path,pending,verified,checked_at):
    try:
        previous=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'fixtures':{}}
        if not isinstance(previous.get('fixtures'),dict) or any(not isinstance(v,dict) for v in previous['fixtures'].values()):raise ValueError('Invalid pending queue')
    except (ValueError,TypeError,AttributeError):
        # Retain the broken bytes as evidence, then reconstruct from the last
        # receipt if available. A corrupt cache must not require manual deletion.
        raw=path.read_bytes();path.with_name('pending-fixtures-invalid-'+hashlib.sha256(raw).hexdigest()[:12]+'.json').write_bytes(raw)
        previous={'fixtures':{}}
    if not previous['fixtures']:
        prior_report=path.parent/'refresh-report.json'
        if prior_report.exists():
            try:
                old=json.loads(prior_report.read_text(encoding='utf-8'))
                previous['fixtures']={r['id']:{**r,'firstSeenAt':r.get('firstSeenAt',old['checkedAt'])} for r in old.get('pending',[])}
            except (ValueError,KeyError,TypeError):pass
    entries=previous['fixtures']
    for row in pending:
        prior=entries.get(row['id'],{})
        row['firstSeenAt']=prior.get('firstSeenAt',checked_at)
        row['lastSeenAt']=checked_at
        entries[row['id']]={**row,'state':'pending'}
    for row in verified:
        if row['id'] in entries:
            entries[row['id']].update(state='verified',verifiedAt=checked_at)
    tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps({'schemaVersion':1,'checkedAt':checked_at,'fixtures':entries},ensure_ascii=False,indent=2),encoding='utf-8')
    tmp.replace(path)

def club_key(name):
    # Reviewed provider spelling differences only; no approximate club joins.
    name={'Ipswich Town':'Ipswich','Deportivo A Coruña':'Deportivo La Coruña'}.get(name,name)
    return normalize_team_name(name)

def extract_coaches(page, match_id):
    g=page['general'];h=page['header'];lineup=page['content']['lineup']
    if str(g['matchId'])!=str(match_id) or not h['status'].get('finished'):
        raise ValueError(f"Fixture ID mismatch or unfinished match: requested {match_id}, received {g['matchId']}")
    if h['status'].get('cancelled') or h['status'].get('awarded'):
        raise ValueError('Cancelled/awarded match')
    teams=h['teams'];result={'providerMatchId':str(match_id),'date':h['status']['utcTime'][:10],
        'league':LEAGUES[int(g['leagueId'])],'home':teams[0]['name'],'away':teams[1]['name'],
        'hg':teams[0]['score'],'ag':teams[1]['score'],'coaches':[]}
    for i,side in enumerate(['homeTeam','awayTeam']):
        team=lineup[side];coach=team['coach']
        if str(team['id'])!=str(teams[i]['id']) or not coach.get('id') or not coach.get('name') or not coach.get('isCoach'):
            raise ValueError('Coach/team identity missing or inconsistent')
        result['coaches'].append({'id':str(coach['id']),'name':coach['name']})
    return result

def resolve_coach(coach, club, date, registry, crosswalk):
    byid={r['id']:r for r in registry['managers']}
    known=crosswalk.get(coach['id'])
    if known:
        if known['managerId'] not in byid:raise ValueError('Invalid coach crosswalk')
        if builder.norm(coach['name']) not in [builder.norm(n) for n in known['names']]:raise ValueError('Provider coach name changed')
        return known['managerId']
    name=builder.resolve_contextual_name(coach['name'],club,date,registry)
    found={r['id'] for r in registry['managers'] if builder.norm(name) in {builder.norm(n) for n in [r['name']]+r['aliases']}}
    if len(found)!=1:raise ValueError('Manager needs identity review: '+coach['name'])
    return found.pop()

def reviewed_fixture(reviews, fixture_id, provider_id):
    row=reviews.get(fixture_id)
    # A review can precede the next odds archive release. Bind it to the exact
    # provider match ID, never a club/name/date wildcard. The caller additionally
    # verifies date, league, both teams and final score before using either form.
    provider_row=reviews.get('fotmob:'+str(provider_id))
    if row is not None and provider_row is not None and row!=provider_row:
        raise ValueError('Conflicting fixture-specific manager reviews')
    if row is None:row=provider_row
    if row is not None and (str(row.get('providerMatchId'))!=str(provider_id) or not row.get('evidence') or not row.get('reviewedAt')):
        raise ValueError('Invalid fixture-specific manager review')
    return row

def identity_quarantine_complete(candidates, added, pending):
    """Only known identity-review holds may accompany a validated partial release.

    Missing fixtures, conflicting scores/dates, failed requests and exhausted
    bounds are not identity holds and must still stop strict publication.
    """
    candidate_ids={r[0] for r in candidates}
    added_ids={r['id'] for r in added}
    pending_ids={r['id'] for r in pending}
    return (bool(pending) and len(candidate_ids)==len(candidates)
            and len(added_ids)==len(added) and len(pending_ids)==len(pending)
            and not added_ids & pending_ids and added_ids | pending_ids == candidate_ids
            and all(p.get('reason','').startswith('Manager needs identity review: ')
                    and len(p.get('coaches',[]))==2 for p in pending))

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--archive',type=Path,required=True);ap.add_argument('--state',type=Path,required=True)
    ap.add_argument('--max-matches',type=int,default=300);ap.add_argument('--max-dates',type=int,default=45)
    ap.add_argument('--offline',action='store_true')
    ap.add_argument('--strict',action='store_true',help='Retain the previous archive if any eligible fixture remains unresolved')
    ap.add_argument('--quarantine-unknown-managers',action='store_true',help='Publish verified fixtures while retaining exact unknown-manager fixtures for review')
    ap.add_argument('--quarantine-unresolved-fixtures',action='store_true',help='Publish only verified additions; durably hold every unresolved fixture independently')
    args=ap.parse_args()
    archive=json.loads(args.archive.read_text(encoding='utf-8'))
    release=json.loads((ROOT/'src/data/football-atlas-release.json').read_text())
    atlas=json.loads((ROOT/'public'/release['indexUrl'].lstrip('/')).read_text(encoding='utf-8'))
    registry=json.loads((ROOT/'scripts/config/manager-atlas-identities.json').read_text(encoding='utf-8'))
    xfile=ROOT/'scripts/config/manager-fotmob-identities.json'
    crosswalk=json.loads(xfile.read_text(encoding='utf-8')) if xfile.exists() else {}
    reviewfile=ROOT/'scripts/config/manager-fixture-reviews.json'
    reviews=json.loads(reviewfile.read_text(encoding='utf-8')) if reviewfile.exists() else {}
    args.state.mkdir(parents=True,exist_ok=True)
    # Legacy date caches discarded groups whose id differed from primaryId.
    # Keep them for evidence, but never reuse that incomplete projection.
    dates_dir=args.state/'dates-v2';matches_dir=args.state/'matches'
    dates_dir.mkdir(exist_ok=True);matches_dir.mkdir(exist_ok=True)
    session=requests.Session();session.headers['User-Agent']='IlMargineManagerAtlas/1.0'
    requests_count=0;consecutive_errors=0
    def get(url,params=None):
        nonlocal requests_count,consecutive_errors
        if args.offline:raise ValueError('Not cached; offline mode')
        if consecutive_errors>=3:raise requests.RequestException('Source paused after three consecutive request failures')
        requests_count+=1
        try:
            response=session.get(url,params=params,timeout=30)
            response.raise_for_status();consecutive_errors=0;return response
        except requests.RequestException:
            consecutive_errors+=1;raise
        finally:time.sleep(.35)
    def day(date):
        p=dates_dir/(date+'.json')
        if not cache_usable(p,args.offline):
            d=get('https://www.fotmob.com/api/data/matches',{'date':date.replace('-',''),'timezone':'Europe/London','ccode3':'GBR'}).json()
            slim=normalize_day(d)
            cache={'schemaVersion':2,'date':date,'checkedAt':datetime.now(timezone.utc).isoformat(),
                   'source':'https://www.fotmob.com/api/data/matches',
                   'payloadSha256':hashlib.sha256(json.dumps(d,sort_keys=True).encode()).hexdigest(),'leagues':slim}
            p.write_text(json.dumps(cache),encoding='utf-8')
        cache=json.loads(p.read_text(encoding='utf-8'))
        if cache.get('schemaVersion')!=2 or cache.get('date')!=date or not isinstance(cache.get('leagues'),list):
            raise ValueError('Invalid versioned date cache')
        return cache['leagues']
    def details(mid):
        p=matches_dir/(str(mid)+'.json')
        if not cache_usable(p,args.offline):
            d=get('https://www.fotmob.com/api/data/match',{'id':mid}).json()
            url=d.get('pageUrl','')
            if not url.startswith('/matches/'):raise ValueError('Unexpected match page URL')
            raw=get('https://www.fotmob.com'+url).text
            m=re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',raw)
            if not m:raise ValueError('No match payload')
            row=extract_coaches(json.loads(m[1])['props']['pageProps'],mid)
            row.update(source='https://www.fotmob.com'+url,checkedAt=datetime.now(timezone.utc).isoformat(),payloadSha256=hashlib.sha256(m[1].encode()).hexdigest())
            p.write_text(json.dumps(row,ensure_ascii=False),encoding='utf-8')
        return json.loads(p.read_text(encoding='utf-8'))
    existing={r['id']:r for r in archive['fixtures']}
    candidates=[r for r in atlas['fixtures'] if r[0] not in existing and r[1]>'2026-05-24']
    candidates.sort(key=lambda r:(r[1],r[0]))
    pending=[];added=[];days={};day_errors={};new_coaches={};failures=[];fetched_dates=set()
    if len(existing)!=len(archive['fixtures']):raise ValueError('Duplicate existing manager fixture ID')
    if len({r[0] for r in candidates})!=len(candidates):raise ValueError('Duplicate candidate fixture ID')
    def hold(f,code,reason,**extra):
        pending.append({'id':f[0],'date':f[1],'league':atlas['leagues'][f[2]],
                        'home':atlas['teams'][f[4]],'away':atlas['teams'][f[5]],
                        'code':code,'reason':reason,**extra})
    try:
        for position,f in enumerate(candidates):
            date=f[1];league=atlas['leagues'][f[2]];home=atlas['teams'][f[4]];away=atlas['teams'][f[5]]
            if position>=args.max_matches:
                hold(f,'batch_limit','Per-run match limit; retry next refresh');continue
            if date not in days and date not in day_errors:
                if not cache_usable(dates_dir/(date+'.json'),args.offline):
                    if len(fetched_dates)>=args.max_dates:
                        hold(f,'date_limit','Per-run fresh date limit; retry next refresh');continue
                    fetched_dates.add(date)
                try:days[date]=day(date)
                except (requests.RequestException,ValueError,KeyError,TypeError,AttributeError,IndexError) as e:
                    day_errors[date]=type(e).__name__
            if date in day_errors:
                hold(f,'source_unavailable','Date evidence unavailable or invalid: '+day_errors[date]);continue
            try:
                matches=[m for l in days[date] if l['league']==league for m in l['matches'] if club_key(m['home']['name'])==club_key(home) and club_key(m['away']['name'])==club_key(away)]
            except (ValueError,KeyError,TypeError,AttributeError,IndexError) as e:
                hold(f,'invalid_evidence','Invalid date fixture: '+type(e).__name__);continue
            if len(matches)!=1:hold(f,'fixture_not_unique','No unique exact fixture match');continue
            m=matches[0]
            if not isinstance(m.get('status'),dict):hold(f,'invalid_evidence','Missing fixture status',providerMatchId=m['id']);continue
            if not m['status'].get('finished'):hold(f,'unfinished','Unfinished',providerMatchId=m['id']);continue
            try:row=reviewed_fixture(reviews,f[0],m['id']) or details(m['id'])
            except requests.RequestException:
                hold(f,'source_unavailable','Fixture evidence request failed',providerMatchId=m['id']);continue
            except (ValueError,KeyError,TypeError,AttributeError,IndexError) as e:
                hold(f,'invalid_evidence',str(e),providerMatchId=m['id']);continue
            try:
                identity=(row['date'],row['league'],club_key(row['home']),club_key(row['away']),row['hg'],row['ag'])
                if not isinstance(row['coaches'],list) or len(row['coaches'])!=2:
                    raise ValueError('Exactly two fixture coaches required')
                if any(not isinstance(c,dict) or not c.get('id') or not c.get('name') for c in row['coaches']):
                    raise ValueError('Incomplete coach identity')
            except (ValueError,KeyError,TypeError,AttributeError,IndexError) as e:
                hold(f,'invalid_evidence',str(e),providerMatchId=m['id']);continue
            if identity!=(date,league,club_key(home),club_key(away),f[6],f[7]):
                hold(f,'fixture_conflict','Match date/teams/score conflict',providerMatchId=m['id']);continue
            try:ids=[resolve_coach(row['coaches'][i],club,date,registry,crosswalk) for i,club in enumerate([home,away])]
            except ValueError as e:
                hold(f,'identity_review',str(e),providerMatchId=m['id'],source=row.get('source'),coaches=row['coaches']);continue
            if ids[0]==ids[1]:hold(f,'identity_review','Same manager on both sides',providerMatchId=m['id']);continue
            priced=all(type(v) in (int,float) and 1<v<1001 for v in f[8:11]) and f[11] in (1,2,3,4,5)
            added.append({'id':f[0],'date':date,'league':league,'season':atlas['seasons'][f[3]],'home':home,'away':away,'hg':f[6],'ag':f[7],'odds':f[8:11] if priced else None,'basis':({1:'closing',2:'last-pre-match',3:'bet365-last-pre-match',4:'bet365-closing',5:'bet365-pre-match'}[f[11]]) if priced else None,'homeManager':ids[0],'awayManager':ids[1]})
            for i,mid in enumerate(ids):new_coaches[row['coaches'][i]['id']]={'managerId':mid,'name':row['coaches'][i]['name']}
            if len(added)%20==0:print('Validated',len(added),'pending',len(pending),'requests',requests_count,flush=True)
    except Exception as e:failures.append(str(e))
    quarantine_ok=(args.quarantine_unknown_managers and identity_quarantine_complete(candidates,added,pending)) or (args.quarantine_unresolved_fixtures and fixture_quarantine_complete(candidates,added,pending))
    if args.strict and len(added)!=len(candidates) and not quarantine_ok:
        failures.append(f'Manager verification incomplete: {len(candidates)-len(added)} eligible fixtures require review; previous archive retained')
    checked_at=datetime.now(timezone.utc).isoformat()
    save_pending_queue(args.state/'pending-fixtures.json',pending,added if not failures else [],checked_at)
    report={'checkedAt':checked_at,'candidates':len(candidates),'candidateIds':[r[0] for r in candidates],
            'verifiedIds':[r['id'] for r in added],'verified':len(added),'added':len(added) if not failures else 0,
            'pending':pending,'quarantinedIdentities':sum(p.get('code')=='identity_review' for p in pending),
            'fullyAccounted':fixture_quarantine_complete(candidates,added,pending),'failures':failures,'requests':requests_count,'coachMappings':new_coaches,'atlasVersion':release['version'],'through':max([archive['through']]+[r['date'] for r in added])}
    # Unexpected global failures retain the archive; known fixture holds do not
    # prevent unrelated verified additions when exact accounting has passed.
    if not failures:
        for r in added:existing[r['id']]=r
        archive['fixtures']=sorted(existing.values(),key=lambda r:(r['date'],r['id']))
        used={r[k] for r in existing.values() for k in ['homeManager','awayManager']}
        prior_managers={r['id']:r for r in archive['managers']}
        archive['managers']=[prior_managers.get(r['id'],{'id':r['id'],'name':r['name']}) for r in registry['managers'] if r['id'] in used]
        archive.update(through=report['through'],atlasVersion=release['version'])
        archive['coverage'].update(currentSeasonConnected=bool(added) or archive['coverage'].get('currentSeasonConnected',False),basis=dict(Counter(r['basis'] for r in existing.values())),managerRefresh={'checkedAt':report['checkedAt'],'pending':len(pending),'automaticPublication':False})
        tmp=args.archive.with_suffix('.json.tmp');tmp.write_text(json.dumps(archive,ensure_ascii=False,separators=(',',':')),encoding='utf-8');tmp.replace(args.archive)
    (args.state/'refresh-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ['pending','coachMappings']},ensure_ascii=False),flush=True)
    if failures:raise SystemExit(1)

if __name__=='__main__':main()
