"""Read-only recent-results projection, independent of priced profile membership.

Use a stable completed export. Never overwrites sources, results, odds or model
ledgers. Date-only records on the capture day are held out: ordering within that
day cannot be proven. Unknown result tokens are quarantined per row, not per run.
"""
import csv,importlib.util,re,json,hashlib
from pathlib import Path
from collections import defaultdict,Counter
from datetime import date,timedelta
from build_matchday_supplement import normal,ALIASES

def build_recent(source, names, as_of):
    def read(name):
        with (source/name).open(encoding='utf-8-sig',newline='') as f: return list(csv.DictReader(f))
    people={p['id']:p for p in read('players_atp.csv')}
    index=defaultdict(list)
    for pid,p in people.items():
        if '/' not in p['name']: index[normal(p['name'])].append(pid)
    tours={t['id']:t for t in read('tours_atp.csv')}
    wanted=set();aliases={};unlinked=[]
    for name in names:
        key=normal(name);choices=index[key]
        if key in ALIASES:
            pid,canonical=ALIASES[key]
            choices=[pid] if people.get(pid,{}).get('name')==canonical and index[normal(canonical)]==[pid] else []
            if choices:aliases[key]=normal(canonical)
        if len(choices)==1:wanted.add(choices[0])
        else:unlinked.append(name)
    spec=importlib.util.spec_from_file_location('result_rules',Path(__file__).with_name('build-tennis-matchup.py'))
    rules=importlib.util.module_from_spec(spec);spec.loader.exec_module(rules)
    cutoff=(date.fromisoformat(as_of)-timedelta(days=3*366)).isoformat()
    records=defaultdict(dict);conflicts=set();excluded=Counter();tokens=Counter();omitted=defaultdict(list)
    surfaces={**rules.SURFACES,'4':'carpet','6':'acrylic','10':'unknown'}
    for row in read('games_atp.csv'):
        ids=[row['winner_id'],row['loser_id']]
        if not wanted.intersection(ids):continue
        if not cutoff <= row['date'] < as_of:continue
        t=tours.get(row['tour_id'],{});score=row['result'].strip()
        if any(pid not in people or '/' in people[pid]['name'] for pid in ids):excluded['invalid_identity']+=1;continue
        if t.get('rank') not in ('0','1','2','3','4','5') or re.search(r'junior|exhibition|next.?gen|laver|hopman|diriyah',t.get('name',''),re.I):excluded['unsupported_event']+=1;continue
        status='completed' if rules.completed(score) else 'retired' if re.fullmatch(r'(?:\d+-\d+(?:\(\d+\))?\s*)+ret\.?',score,re.I) else 'walkover' if re.fullmatch(r'w\s*/?\s*o\.?',score,re.I) else 'unclassified'
        tokens[re.sub(r'\d+|[()\s-]','',score) or 'numeric']+=1
        if status=='unclassified':
            excluded['unclassified_result']+=1
            for pid in wanted.intersection(ids):omitted[pid].append(row['date'])
            continue
        mid=hashlib.sha256('|'.join(sorted([row['winner_id'],row['loser_id']])+[row['tour_id'],row['round_id']]).encode()).hexdigest()[:20]
        try: rd=int(row['round_id'])
        except (ValueError,TypeError):
            excluded['invalid_round']+=1;continue
        # Use only the established qualifying distinction: native main-draw
        # round codes vary with draw size, so do not invent R32/R64 labels.
        rnd='Qualifying' if rd<4 else {9:'Quarter-final',10:'Semi-final',12:'Final'}.get(rd,'Main draw')
        for side,pid in enumerate(ids):
            if pid not in wanted:continue
            m={'id':mid,'sortRound':rd,'sortEvent':row['tour_id'],'date':row['date'],'event':t.get('name','Tournament unrecorded'),'surface':surfaces.get(t.get('court_id'),'unknown'),'round':rnd,'opponent':people[ids[1-side]]['name'],'score':score,'winner':side==0,'status':status,'competition':'Qualifying' if rd<4 else {'0':'ITF','1':'Challenger','5':'Team'}.get(t.get('rank'),'ATP')}
            if mid in records[pid] and records[pid][mid]!=m:conflicts.add((pid,mid))
            records[pid][mid]=m
    players={}
    for pid in wanted:
        vals=[m for mid,m in records[pid].items() if (pid,mid) not in conflicts]
        vals.sort(key=lambda m:(m['date'],m['sortEvent'],m['sortRound']),reverse=True)
        for m in vals:m.pop('sortEvent');m.pop('sortRound')
        players[normal(people[pid]['name'])]={'name':people[pid]['name'],'matches':vals[:10],'omitted':sum(d >= (vals[9]['date'] if len(vals)>=10 else cutoff) for d in omitted[pid])}
    through=max((m['date'] for p in players.values() for m in p['matches']),default=None)
    return {'schema':1,'asOf':as_of,'through':through,'aliases':aliases,'players':players}, {'unlinked':sorted(set(unlinked)),'players':len(players),'matches':sum(len(p['matches']) for p in players.values()),'excluded':dict(excluded),'conflicts':len(conflicts),'scoreTokens':dict(tokens),'latestAcceptedResult':through}
