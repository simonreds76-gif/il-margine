"""Bounded completed-fixture check independent of Understat availability."""
from datetime import timedelta
from football_shots_inputs import identity, key, number, utc
SLUGS={'epl':'eng.1','serie-a':'ita.1','la-liga':'esp.1','bundesliga':'ger.1','ligue-1':'fra.1'}
BASE='https://site.api.espn.com/apis/site/v2/sports/soccer/'

def event_status(event):
    competitions=event.get('competitions',[])
    return (competitions[0].get('status',event.get('status',{})) if len(competitions)==1 else event.get('status',{})).get('type',{})

def day_complete(events,now):
    # Terminal does not mean usable yet: do not freeze a day while the final
    # match is still inside the conservative three-hour observation cutoff.
    for event in events:
        status=event_status(event)
        if status.get('name') in ('STATUS_CANCELED','STATUS_POSTPONED'):continue
        comps=event.get('competitions',[])
        kickoff=utc(comps[0].get('date',event.get('date'))) if len(comps)==1 else None
        if status.get('completed') is not True or kickoff is None or kickoff>now-timedelta(hours=3):return False
    return True

def canonical_team(team,league):
    # ESPN's displayName "Deportivo" is ambiguous outside this exact provider ID.
    # ID 90, Spanish league: Deportivo La Coruna. Keep the source IDs in receipts.
    if league=='la-liga' and str(team.get('id'))=='90' and team.get('displayName') in ('Deportivo','Deportivo La Coruna','Deportivo La Coruña'):
        return 'La Coruna'
    return team.get('displayName')

def completed(payload,league,now,start):
    if not isinstance(payload,dict) or not isinstance(payload.get('events'),list):
        raise ValueError('missing_events_envelope')
    # An invalid/error envelope must not certify an empty international break.
    if not any(str(x.get('slug',''))==SLUGS[league] for x in payload.get('leagues',[])):
        raise ValueError('league_identity_mismatch')
    result=[]
    for e in payload['events']:
        comps=e.get('competitions',[])
        if len(comps)!=1:raise ValueError('ambiguous_event')
        c=comps[0];status=c.get('status',e.get('status',{})).get('type',{})
        if status.get('completed') is not True:continue
        if status.get('name')!='STATUS_FULL_TIME':continue
        ko=utc(c.get('date',e.get('date')))
        if not ko or not start<=ko<=now-timedelta(hours=3):continue
        sides={s.get('homeAway'):s for s in c.get('competitors',[])}
        if set(sides)!={'home','away'}:raise ValueError('ambiguous_participants')
        row=dict(date=ko.date().isoformat(),league=league,event_id=str(e['id']),kickoff=ko.isoformat())
        for side in ('home','away'):
            s=sides[side];name=canonical_team(s.get('team',{}),league);score=number(s.get('score'))
            if not name or score is None or not score.is_integer():raise ValueError('missing_identity_or_score')
            row[side+'_team']=name;row[side+'_goals']=int(score);row[side+'_id']=str(s['team']['id'])
        result.append(row)
    if len({identity(r) for r in result})!=len(result):raise ValueError('duplicate_fixture')
    return result

def check(get,now,previous=None):
    start=(now-timedelta(days=21)).replace(hour=0,minute=0,second=0,microsecond=0)
    out=dict(observed_at=now.isoformat(),window_start=start.isoformat(),leagues={})
    for league,slug in SLUGS.items():
        url=BASE+slug+'/scoreboard'
        try:
            import hashlib
            response=get(url);payload=response.json()
            info=next(x for x in payload.get('leagues',[]) if x.get('slug')==slug)
            if info.get('calendarType')!='day' or not isinstance(info.get('calendar'),list):raise ValueError('unverified_calendar')
            days=sorted({utc(d).strftime('%Y%m%d') for d in info['calendar'] if utc(d) and start<=utc(d)<now})
            cache=(previous or {}).get('leagues',{}).get(league,{}).get('days',{})
            saved={};rows=[]
            for day in days:
                if day in cache and cache[day].get('complete_day') is True and day<(now-timedelta(days=2)).strftime('%Y%m%d'):
                    saved[day]=cache[day]
                else:
                    r=get(url,{'dates':day,'limit':1000});daily=r.json()
                    events=daily.get('events',[])
                    parsed=completed(daily,league,now,start)
                    # A valid dated empty envelope is coverage evidence, but
                    # never cache it permanently: rescheduling may change it.
                    saved[day]=dict(observed_at=now.isoformat(),url=r.url,sha256=hashlib.sha256(r.content).hexdigest(),complete_day=bool(events) and day_complete(events,now),empty_calendar_day=not events,completed=parsed)
                rows.extend(saved[day]['completed'])
            # Keep unresolved older expectations; a sliding window must not erase holes.
            older=(previous or {}).get('leagues',{}).get(league,{}).get('completed',[])
            for row in older+rows:
                for side in ('home','away'):
                    row[side+'_team']=canonical_team({'id':row[side+'_id'],'displayName':row[side+'_team']},league)
            merged={identity(r):r for r in older+rows}
            out['leagues'][league]=dict(status='VERIFIED',url=response.url,sha256=hashlib.sha256(response.content).hexdigest(),days=saved,completed=list(merged.values()))
        except Exception as exc:
            out['leagues'][league]={**(previous or {}).get('leagues',{}).get(league,{}),'status':'UNVERIFIED','reason':type(exc).__name__+': '+str(exc)[:160]}
    return out

def recovery_rows(payload, fixture, observed, known_teams=None):
    """Only exact full-time identity, score and explicit totalShots fields."""
    # A provider's unknown display name cannot create a second history for a
    # known club. Resolve both names against this league's existing identity set.
    if known_teams is None or any((fixture['league'],key(fixture[side+'_team'])) not in known_teams for side in ('home','away')):return None
    competitions=payload.get('header',{}).get('competitions',[])
    if len(competitions)!=1:return None
    c=competitions[0];status=c.get('status',{}).get('type',{})
    if status.get('name')!='STATUS_FULL_TIME' or status.get('completed') is not True:return None
    ko=utc(c.get('date'))
    if ko!=utc(fixture['kickoff']) or observed<ko+timedelta(hours=3):return None
    competitors={r.get('homeAway'):r for r in c.get('competitors',[])}
    stats={str(r.get('team',{}).get('id')):r for r in payload.get('boxscore',{}).get('players',[])}
    if not stats: stats={str(r.get('team',{}).get('id')):r for r in payload.get('boxscore',{}).get('teams',[])}
    sides=[]
    for side in ('home','away'):
        r=competitors.get(side,{});team=r.get('team',{})
        if str(team.get('id'))!=fixture[side+'_id'] or key(canonical_team(team,fixture['league']))!=key(fixture[side+'_team']) or number(r.get('score'))!=fixture[side+'_goals']:return None
        values={s.get('name'):number(s.get('displayValue')) for s in stats.get(fixture[side+'_id'],{}).get('statistics',[])}
        picked={k:values.get(v) for k,v in [('shots','totalShots'),('sot','shotsOnTarget'),('corners','wonCorners')]}
        if any(v is None or not v.is_integer() for v in picked.values()) or picked['sot']>picked['shots']:return None
        sides.append(picked)
    year=int(fixture['date'][:4])-(int(fixture['date'][5:7])<8)
    common=dict(date=fixture['date'],league=fixture['league'],season=f'{year}-{year+1}',home_team=fixture['home_team'],away_team=fixture['away_team'],
        b365h='',b365d='',b365a='',market_team_win_prob='',market_opp_win_prob='',xg_for='',xg_against='',xg_source='',match_source='espn_verified_fulltime')
    result=[]
    for i,(side,other) in enumerate([('home','away'),('away','home')]):
        r=dict(common,team=fixture[side+'_team'],opponent=fixture[other+'_team'],team_key=key(fixture[side+'_team']),opponent_key=key(fixture[other+'_team']),venue=side,
            goals_for=fixture[side+'_goals'],goals_against=fixture[other+'_goals'])
        for metric in ('shots','sot','corners'):r.update({metric+'_for':int(sides[i][metric]),metric+'_against':int(sides[1-i][metric])})
        result.append(r)
    return result
