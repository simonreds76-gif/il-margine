#!/usr/bin/env python3
"""Bounded current-season fallback when the primary count CSVs lag.

Completed Understat fixtures provide identity, goals and xG. Exact-date FotMob
full-time fixtures supply shots, SOT and corners. No odds, estimates or missing
statistics are invented. Durable supplements are reapplied after normal builds.
"""
from __future__ import annotations
import argparse
import csv
import importlib.util
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
import requests
import fotmob_match_stats as F
from football_team_names import football_form_team_key as key
from football_count_results import count, stamp

ROOT=Path(__file__).resolve().parents[1]
FORM=ROOT/'data/football-form'
LEAGUES={'epl':'EPL','serie-a':'Serie_A','la-liga':'La_liga','bundesliga':'Bundesliga','ligue-1':'Ligue_1'}
spec=importlib.util.spec_from_file_location('count_form_builder',ROOT/'scripts/build-football-form-layer.py')
B=importlib.util.module_from_spec(spec);sys.modules[spec.name]=B;spec.loader.exec_module(B)

def fixture_id(day, league, home, away):return '|'.join([day,league,key(home),key(away)])

def verified_stat_pair(stats, name):
    matches=[]
    for section in stats.get('Periods',{}).get('All',{}).get('stats',[]):
        for item in section.get('stats',[]):
            if item.get('key')!=name:continue
            values=item.get('stats') or []
            if len(values)!=2:return None
            pair=tuple(count(value) for value in values)
            if None in pair:return None
            matches.append(pair)
    return matches[0] if matches and len(set(matches))==1 else None

def verified_rows(league, fixture, match, props, observed):
    day=str(fixture.get('datetime','')).split(' ')[0]
    home=(fixture.get('h') or {}).get('title','');away=(fixture.get('a') or {}).get('title','')
    if fixture.get('isResult') is not True or not home or not away:return None
    status=match.get('status') or {};kickoff=stamp(status.get('utcTime'))
    if not status.get('finished') or status.get('cancelled') or status.get('awarded'):return None
    if kickoff is None or kickoff.date().isoformat()!=day or observed<kickoff+timedelta(hours=3):return None
    general=props.get('general') or {}
    if str(general.get('matchTimeUTCDate',''))[:10]!=day:return None
    for side,name in [('home',home),('away',away)]:
        if key((match.get(side) or {}).get('name'))!=key(name):return None
        if key((general.get(side+'Team') or {}).get('name'))!=key(name):return None
    goals=[count((fixture.get('goals') or {}).get(s)) for s in ('h','a')]
    if None in goals or goals!=[count((match.get(s) or {}).get('score')) for s in ('home','away')]:return None
    stats=(props.get('content') or {}).get('stats') or {}
    values={name:verified_stat_pair(stats,stat) for name,stat in [('shots','total_shots'),('sot','ShotsOnTarget'),('corners','corners')]}
    if any(v is None or any(count(x) is None for x in v) for v in values.values()):return None
    if any(values['sot'][i]>values['shots'][i] for i in (0,1)):return None
    try:
        xg=[float(fixture['xG'][s]) for s in ('h','a')]
        import math
        if not all(math.isfinite(x) and x>=0 for x in xg):return None
    except (KeyError,ValueError,TypeError):return None
    year=int(day[:4]) if int(day[5:7])>=8 else int(day[:4])-1
    common=dict(date=day,league=league,season=f'{year}-{year+1}',home_team=home,away_team=away,
        b365h='',b365d='',b365a='',market_team_win_prob='',market_opp_win_prob='',
        match_source='fotmob_verified_fulltime',xg_source='understat')
    output=[]
    for i,(team,opp,venue) in enumerate([(home,away,'home'),(away,home,'away')]):
        row=dict(common,team=team,team_key=key(team),opponent=opp,opponent_key=key(opp),venue=venue,
            goals_for=goals[i],goals_against=goals[1-i],xg_for=xg[i],xg_against=xg[1-i])
        for metric,v in values.items():row.update({metric+'_for':v[i],metric+'_against':v[1-i]})
        output.append(row)
    return output

def merge_supplements(base, supplements):
    output=list(base)
    existing={fixture_id(r['date'],r['league'],r['home_team'],r['away_team']) for r in base}
    occupied={(r['date'],r['league'],key(r['team'])) for r in base}
    added=0
    for fid,record in sorted(supplements.items()):
        row=record['rows'][0]
        fid=fixture_id(row['date'],row['league'],row['home_team'],row['away_team'])
        # Prefer a subsequently recovered primary-provider match; never duplicate
        # or silently overwrite it with a secondary provider's definitions.
        if fid not in existing and not any((r['date'],r['league'],key(r['team'])) in occupied for r in record['rows']):
            output.extend(record['rows']);existing.add(fid);added+=1
            occupied.update((r['date'],r['league'],key(r['team'])) for r in record['rows'])
    output=B.unique_team_results(output,key)
    return output,added

def atomic_json(path,data):
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(data,indent=2)+'\n',encoding='utf8');temp.replace(path)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh',action='store_true',help='Fetch missing current-season inputs, within request limits')
    parser.add_argument('--max-matches',type=int,default=30)
    parser.add_argument('--max-requests',type=int,default=75)
    args=parser.parse_args();now=datetime.now(timezone.utc)
    base_path=FORM/'team-match-base.csv'
    with base_path.open(encoding='utf-8-sig',newline='') as f:base=list(csv.DictReader(f))
    supplement_path=FORM/'count-input-supplement.json'
    supplement=json.loads(supplement_path.read_text(encoding='utf8')) if supplement_path.exists() else {}
    supplement={fixture_id(v['rows'][0]['date'],v['rows'][0]['league'],v['rows'][0]['home_team'],v['rows'][0]['away_team']):v for v in supplement.values()}
    known={fixture_id(r['date'],r['league'],r['home_team'],r['away_team']) for r in base}|set(supplement)
    primary_latest={league:max((r['date'] for r in base if r['league']==league and r.get('match_source')!='fotmob_verified_fulltime'),default='') for league in LEAGUES}
    report=dict(generated_at=now.isoformat(),network_refresh=args.refresh,requests=0,recovered=0,unresolved=[],leagues={})
    if args.refresh:
        request_count=0
        def get(url,params=None):
            nonlocal request_count
            if request_count>=args.max_requests:raise RuntimeError('request_budget_exhausted')
            request_count+=1
            r=requests.get(url,params=params,headers={**F.HEADERS,'X-Requested-With':'XMLHttpRequest'},timeout=30)
            r.raise_for_status();return r
        season=now.year if now.month>=8 else now.year-1
        jobs=[]
        for league,slug in LEAGUES.items():
            try:
                payload=get(f'https://understat.com/getLeagueData/{slug}/{season}').json()
                completed=[x for x in payload.get('dates',[]) if x.get('isResult') is True and str(x.get('datetime',''))[:10]<now.date().isoformat()]
                report['leagues'][league]={'latest_completed':max((x['datetime'][:10] for x in completed),default=None),'completed':len(completed)}
                for fixture in completed:
                    fid=fixture_id(fixture['datetime'][:10],league,fixture['h']['title'],fixture['a']['title'])
                    if fixture['datetime'][:10]>primary_latest[league] and fid not in known:jobs.append((league,fixture,fid))
            except (requests.RequestException,ValueError,RuntimeError) as e:
                report['leagues'][league]={'error':type(e).__name__}
        # Oldest missing matches first, so a daily cap cannot leave permanent holes.
        jobs.sort(key=lambda x:(x[1]['datetime'],x[0],x[2]));boards={}
        for league,fixture,fid in jobs[:max(0,args.max_matches)]:
            try:
                day=fixture['datetime'][:10]
                if day not in boards:boards[day]=get(F.MATCHES_URL,{'date':day.replace('-',''),'timezone':'UTC','ccode3':'GBR'}).json()
                league_board=next((x for x in boards[day].get('leagues',[]) if x.get('id')==F.LEAGUE_CONFIGS[league]['league_id']),{})
                matches=[m for m in league_board.get('matches',[]) if key(m.get('home',{}).get('name'))==key(fixture['h']['title']) and key(m.get('away',{}).get('name'))==key(fixture['a']['title'])]
                if len(matches)!=1:raise ValueError('no_unique_fixture')
                match=matches[0]
                if not (match.get('status') or {}).get('finished'):raise ValueError('not_finished')
                detail=get(F.MATCH_URL,{'id':match['id']}).json()
                page_url=detail.get('pageUrl','')
                if not page_url.startswith('/') or page_url.startswith('//'):raise ValueError('invalid_page_url')
                props=F._extract_next_payload(get(F.WEB_BASE+page_url).text).get('props',{}).get('pageProps',{})
                rows=verified_rows(league,fixture,match,props,now)
                if rows is None:raise ValueError('identity_or_stat_validation_failed')
                supplement[fid]=dict(rows=rows,observed_at=now.isoformat(),understat_match_id=fixture['id'],fotmob_match_id=match['id'],source_url=F.WEB_BASE+page_url)
                report['recovered']+=1
            except (requests.RequestException,ValueError,KeyError,RuntimeError) as e:
                report['unresolved'].append({'fixture':fid,'reason':str(e) if isinstance(e,(ValueError,RuntimeError)) else type(e).__name__})
        report.update(requests=request_count,completed_missing_before=len(jobs),remaining=len(jobs)-report['recovered'])
        atomic_json(supplement_path,supplement)
    merged,added=merge_supplements(base,supplement)
    manifest_path=FORM/'team-form-manifest.json'
    manifest=json.loads(manifest_path.read_text(encoding='utf8')) if manifest_path.exists() else {}
    if merged != base or (args.refresh and not (FORM/'team-rolling-form.csv').exists()) or manifest.get('row_counts',{}).get('team_match_base')!=len(merged):
        temp=base_path.with_suffix('.tmp');B.write_csv(temp,merged,B.TEAM_MATCH_FIELDS);temp.replace(base_path)
        rolling=B.build_rolling_rows(merged)
        B.write_csv(FORM/'team-rolling-form.csv',rolling,B.rolling_fields())
        manifest.update(generated_at=now.isoformat(),date_range={'min':min(r['date'] for r in merged),'max':max(r['date'] for r in merged)})
        manifest.setdefault('row_counts',{}).update(team_match_base=len(merged),team_rolling_form=len(rolling))
        manifest['count_input_supplement']={'revision':'verified-count-inputs-20261012','matches':len(supplement),'sources':['FotMob full-time counts','Understat completed-fixture goals and xG'],'no_odds_imputed':True}
        atomic_json(manifest_path,manifest)
    report.update(applied_matches=added,base_rows=len(merged),latest_input_date=max((r['date'] for r in merged),default=None),supplement_matches=len(supplement))
    # Keep refresh coverage distinct from merely reapplying the saved supplement.
    if args.refresh:atomic_json(FORM/'count-input-refresh-status.json',report)
    atomic_json(FORM/'count-input-application-status.json',report)
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
