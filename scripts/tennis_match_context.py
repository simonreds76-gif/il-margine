"""Descriptive recent schedules, independent of priced/H2H history filters."""
import csv
import json
import re
import unicodedata
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

def fold(value):
    return ''.join(c for c in unicodedata.normalize('NFKD',value).casefold() if c.isalnum())

def read(path):
    with path.open(encoding='utf-8-sig',newline='') as handle:
        return list(csv.DictReader(handle))

def build_context(oncourt, players, as_of, registry=()):
    end=date.fromisoformat(as_of); start=(end-timedelta(days=180)).isoformat()
    people=read(oncourt/'players_atp.csv'); tours={r['id']:r for r in read(oncourt/'tours_atp.csv')}
    names={p['id']:p['name'] for p in people}
    identities=defaultdict(list)
    for p in people:
        if '/' not in p['name']:identities[fold(p['name'])].append(p['id'])
    lookup={}; schedules={}; mapped={}
    for i,p in enumerate(players):
        ids=identities[fold(p['name'])]
        mapped[str(i)]=len(ids)==1
        schedules[str(i)]=[]
        if len(ids)==1:lookup[ids[0]]=str(i)
    seen=set(); excluded=0; through=''
    for g in read(oncourt/'games_atp.csv'):
        if not start<=g['date']<as_of:continue
        if not (g['winner_id'] in lookup or g['loser_id'] in lookup):continue
        t=tours.get(g['tour_id']); score=g['result'].strip()
        if not t or g['winner_id']==g['loser_id']:continue
        if re.search(r'w\s*/?\s*o|walkover|bye',score,re.I):continue
        sets=[tuple(map(int,p)) for p in re.findall(r'(\d+)-(\d+)',re.sub(r'\(\d+\)','',score))]
        if not sets:excluded+=1;continue
        key=(g['date'],g['tour_id'],g['round_id'],*sorted([g['winner_id'],g['loser_id']]))
        if key in seen:continue
        seen.add(key);through=max(through,g['date'])
        row={'date':g['date'],'event':t['name'],'score':score,
             'sets':sum((max(a,b)==6 and min(a,b)<=4) or (max(a,b)==7 and min(a,b) in (5,6)) or (max(a,b)>7 and abs(a-b)==2) for a,b in sets),
             'games':sum(a+b for a,b in sets),'retired':bool(re.search(r'ret',score,re.I)),
             'court':t['court_id'],'country':t['country']}
        # Exact event/country/court and date-valid venue only. No city centroid.
        venues=[v for v in registry if fold(v['event'])==fold(t['name']) and v['country']==t['country'] and str(v['court_id'])==t['court_id'] and v['valid_from']<=g['date']<=v['valid_to'] and v.get('location_status')=='mapped_venue' and v.get('altitude_m') is not None]
        if len(venues)==1:
            v=venues[0];row['venue']={'elevation':v['altitude_m'],'source':v['coordinate_source'],'reviewed':v['reviewed_on'],'basis':'Terrain estimate at mapped venue'}
        for pid in (g['winner_id'],g['loser_id']):
            if pid in lookup:
                other=g['loser_id'] if pid==g['winner_id'] else g['winner_id']
                schedules[lookup[pid]].append({**row,'opponent':names.get(other,'Opponent unavailable'),'won':pid==g['winner_id']})
    for rows in schedules.values():rows.sort(key=lambda r:(r['date'],r['event'],r['score']))
    return {'asOf':as_of,'from':start,'through':through,'scope':'Recorded men’s singles across ATP, Challenger and ITF, including qualifying. Exhibitions and missing source results may not be covered.',
            'durationAvailable':False,'excludedScores':excluded,'mapped':mapped,'players':schedules}
