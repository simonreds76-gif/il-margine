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
    if row is not None and (str(row.get('providerMatchId'))!=str(provider_id) or not row.get('evidence') or not row.get('reviewedAt')):
        raise ValueError('Invalid fixture-specific manager review')
    return row

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--archive',type=Path,required=True);ap.add_argument('--state',type=Path,required=True)
    ap.add_argument('--max-matches',type=int,default=300);ap.add_argument('--max-dates',type=int,default=45)
    ap.add_argument('--offline',action='store_true')
    ap.add_argument('--strict',action='store_true',help='Retain the previous archive if any eligible fixture remains unresolved')
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
    dates_dir=args.state/'dates';matches_dir=args.state/'matches'
    dates_dir.mkdir(exist_ok=True);matches_dir.mkdir(exist_ok=True)
    session=requests.Session();session.headers['User-Agent']='IlMargineManagerAtlas/1.0'
    requests_count=0
    def get(url,params=None):
        nonlocal requests_count
        if args.offline:raise ValueError('Not cached; offline mode')
        response=session.get(url,params=params,timeout=30);requests_count+=1
        response.raise_for_status();time.sleep(.35);return response
    def day(date):
        p=dates_dir/(date+'.json')
        if not p.exists():
            d=get('https://www.fotmob.com/api/data/matches',{'date':date.replace('-',''),'timezone':'Europe/London','ccode3':'GBR'}).json()
            slim=[{'league':LEAGUES[l['id']],'matches':l['matches']} for l in d.get('leagues',[]) if l['id'] in LEAGUES]
            p.write_text(json.dumps(slim),encoding='utf-8')
        return json.loads(p.read_text(encoding='utf-8'))
    def details(mid):
        p=matches_dir/(str(mid)+'.json')
        if not p.exists():
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
    pending=[];added=[];days={};new_coaches={};failures=[]
    try:
        for f in candidates[:args.max_matches]:
            date=f[1];league=atlas['leagues'][f[2]];home=atlas['teams'][f[4]];away=atlas['teams'][f[5]]
            if date not in days:
                if len(days)>=args.max_dates:break
                days[date]=day(date)
            matches=[m for l in days[date] if l['league']==league for m in l['matches'] if club_key(m['home']['name'])==club_key(home) and club_key(m['away']['name'])==club_key(away)]
            if len(matches)!=1:pending.append({'id':f[0],'date':date,'home':home,'away':away,'reason':'No unique exact fixture match'});continue
            m=matches[0]
            if not m.get('status',{}).get('finished'):pending.append({'id':f[0],'reason':'Unfinished'});continue
            try:row=reviewed_fixture(reviews,f[0],m['id']) or details(m['id'])
            except (ValueError,KeyError) as e:
                pending.append({'id':f[0],'date':date,'home':home,'away':away,'providerMatchId':m['id'],'reason':str(e)});continue
            if (row['date'],row['league'],club_key(row['home']),club_key(row['away']),row['hg'],row['ag'])!=(date,league,club_key(home),club_key(away),f[6],f[7]):
                pending.append({'id':f[0],'reason':'Match date/teams/score conflict','providerMatchId':m['id']});continue
            try:ids=[resolve_coach(row['coaches'][i],club,date,registry,crosswalk) for i,club in enumerate([home,away])]
            except ValueError as e:
                pending.append({'id':f[0],'reason':str(e),'home':home,'away':away,'coaches':row['coaches']});continue
            if ids[0]==ids[1]:raise ValueError('Same manager on both sides')
            priced=all(type(v) in (int,float) and 1<v<1001 for v in f[8:11]) and f[11] in (1,2,3,4,5)
            added.append({'id':f[0],'date':date,'league':league,'season':atlas['seasons'][f[3]],'home':home,'away':away,'hg':f[6],'ag':f[7],'odds':f[8:11] if priced else None,'basis':({1:'closing',2:'last-pre-match',3:'bet365-last-pre-match',4:'bet365-closing',5:'bet365-pre-match'}[f[11]]) if priced else None,'homeManager':ids[0],'awayManager':ids[1]})
            for i,mid in enumerate(ids):new_coaches[row['coaches'][i]['id']]={'managerId':mid,'name':row['coaches'][i]['name']}
            if len(added)%20==0:print('Validated',len(added),'pending',len(pending),'requests',requests_count,flush=True)
    except Exception as e:failures.append(str(e))
    if args.strict and len(added)!=len(candidates):
        failures.append(f'Manager verification incomplete: {len(candidates)-len(added)} eligible fixtures require review; previous archive retained')
    report={'checkedAt':datetime.now(timezone.utc).isoformat(),'candidates':len(candidates),'added':len(added),'pending':pending,'failures':failures,'requests':requests_count,'coachMappings':new_coaches,'atlasVersion':release['version'],'through':max([archive['through']]+[r['date'] for r in added])}
    # A request/schema failure leaves the public candidate archive untouched.
    if not failures:
        for r in added:existing[r['id']]=r
        archive['fixtures']=sorted(existing.values(),key=lambda r:(r['date'],r['id']))
        used={r[k] for r in existing.values() for k in ['homeManager','awayManager']}
        archive['managers']=[{'id':r['id'],'name':r['name']} for r in registry['managers'] if r['id'] in used]
        archive.update(through=report['through'],atlasVersion=release['version'])
        archive['coverage'].update(currentSeasonConnected=bool(added) or archive['coverage'].get('currentSeasonConnected',False),basis=dict(Counter(r['basis'] for r in existing.values())),managerRefresh={'checkedAt':report['checkedAt'],'pending':len(pending),'automaticPublication':False})
        tmp=args.archive.with_suffix('.json.tmp');tmp.write_text(json.dumps(archive,ensure_ascii=False,separators=(',',':')),encoding='utf-8');tmp.replace(args.archive)
    (args.state/'refresh-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ['pending','coachMappings']},ensure_ascii=False),flush=True)
    if failures:raise SystemExit(1)

if __name__=='__main__':main()
