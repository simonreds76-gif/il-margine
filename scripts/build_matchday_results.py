"""Dated ATP/Challenger results from verified exports, independent of odds."""
import hashlib, importlib.util, re
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from build_matchday_supplement import read_csv

def build_results(source, as_of):
    people={p['id']:p for p in read_csv(source/'players_atp.csv')}
    tours={t['id']:t for t in read_csv(source/'tours_atp.csv')}
    spec=importlib.util.spec_from_file_location('result_rules',Path(__file__).with_name('build-tennis-matchup.py'))
    rules=importlib.util.module_from_spec(spec);spec.loader.exec_module(rules)
    start=(date.fromisoformat(as_of)-timedelta(days=7)).isoformat()
    records={}; conflicts=set(); excluded=Counter()
    for r in read_csv(source/'games_atp.csv'):
        if not start <= r['date'] < as_of: continue
        t=tours.get(r['tour_id'],{});ids=[r['winner_id'],r['loser_id']]
        if t.get('rank') not in ('1','2','3','4') or re.search(r'junior|exhibition|next.?gen|laver|hopman|diriyah',t.get('name',''),re.I): continue
        # Doubles are outside this singles view, not a missing-player warning.
        if any('/' in people.get(pid,{}).get('name','') for pid in ids):continue
        if len(set(ids))!=2 or any(pid not in people for pid in ids):
            excluded['invalid_identity']+=1;continue
        score=r['result'].strip()
        status='completed' if rules.completed(score) else 'retired' if re.fullmatch(r'(?:\d+-\d+(?:\(\d+\))?\s*)+ret\.?',score,re.I) else 'walkover' if re.fullmatch(r'w\s*/?\s*o\.?',score,re.I) else None
        if status is None: excluded['unrecognised_score']+=1;continue
        try: rd=int(r['round_id'])
        except (ValueError,TypeError): excluded['invalid_round']+=1;continue
        mid=hashlib.sha256('|'.join(sorted([r['winner_id'],r['loser_id']])+[r['tour_id'],r['round_id']]).encode()).hexdigest()[:20]
        m={'id':mid,'date':r['date'],'event':t['name'],'tour':'Challenger' if t['rank']=='1' else 'ATP',
           'surface':rules.SURFACES.get(t.get('court_id'),'unknown'),'qualifying':rd<4,
           'round':'Qualifying' if rd<4 else {9:'Quarter-final',10:'Semi-final',12:'Final'}.get(rd,'Main draw'),
           'players':[people[pid]['name'] for pid in ids], 'winner':0,'score':score,'status':status}
        if mid in records and records[mid]!=m:conflicts.add(mid)
        records[mid]=m
    rows=sorted((r for k,r in records.items() if k not in conflicts),key=lambda m:(m['date'],m['event'],m['id']),reverse=True)
    return {'from':start,'before':as_of,'through':max((r['date'] for r in rows),default=None),'matches':rows}, {'rows':len(rows),'excluded':dict(excluded),'conflicts':len(conflicts)}
