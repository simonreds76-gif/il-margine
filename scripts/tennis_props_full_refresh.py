"""Validated append-only source adapter for the isolated full-refresh shadow lane."""
import csv, json, re, runpy, sys, unicodedata, hashlib
from pathlib import Path
from datetime import date
from collections import defaultdict, Counter

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT/'scripts'))
B = runpy.run_path(str(ROOT/'scripts/tennis-props-baseline.py'))
BOARD = runpy.run_path(str(ROOT/'scripts/build-tennis-props-board.py'))
read = B['read_csv']

def norm(s):
    s = str(s or '')
    if ',' in s:
        a,b=s.split(',',1); s=b+' '+a
    return re.sub(r'[^a-z0-9]', '', ''.join(c for c in unicodedata.normalize('NFKD',s.lower()) if not unicodedata.combining(c)))

def score(s):
    if re.search(r'RET|W/O|DEF|ABN|\[', s, re.I): return None
    parts = re.findall(r'(\d+)-(\d+)(?:\(\d+\))?',s)
    if not parts or re.sub(r'(\d+)-(\d+)(?:\(\d+\))?|\s','',s): return None
    sets=[(int(a),int(b)) for a,b in parts]
    if any(not ((max(a,b)==6 and min(a,b)<=4) or (max(a,b)>=7 and abs(a-b)==2) or {a,b}=={6,7}) for a,b in sets): return None
    if sum(a>b for a,b in sets) not in (2,3) or sum(b>a for a,b in sets)>=sum(a>b for a,b in sets): return None
    return sets

def key(r): return tuple(r[k] for k in ('winner_id','loser_id','tour_id','round_id'))

def adapt(g,s):
    sets=score(g['result'])
    if sets is None: return None,'unfinished_or_unsupported_score'
    vals={}
    for p in ('w','l'):
        for k in ('ace','df','svpt','fs','fsof','w1s','w1sof','w2s','w2sof','rpw','rpwof','bpsaved','bpfaced','bpw'):
            x=s.get(p+'_'+k,'')
            if not str(x).isdigit(): return None,'missing_or_noninteger_stat'
            vals[p+'_'+k]=int(x)
    for p,q in (('w','l'),('l','w')):
        v=lambda k:vals[p+'_'+k]
        o=lambda k:vals[q+'_'+k]
        if not (v('svpt')>0 and v('svpt')==v('fsof')==v('fs')+v('w2sof') and v('fs')==v('w1sof') and v('rpwof')==o('svpt')): return None,'point_denominator_mismatch'
        if not (v('w1s')<=v('fs') and v('w2s')<=v('w2sof') and v('df')<=v('w2sof') and v('ace')<=v('w1s')+v('w2s') and v('bpsaved')<=v('bpfaced')): return None,'impossible_counts'
        if v('rpw')!=o('svpt')-o('w1s')-o('w2s') or v('bpw')!=o('bpfaced')-o('bpsaved'): return None,'reciprocal_stat_mismatch'
    games=[sum(x[i] for x in sets) for i in (0,1)]
    tb=[sum({a,b}=={6,7} and (a>b if i==0 else b>a) for a,b in sets) for i in (0,1)]
    broken=[vals[p+'_bpfaced']-vals[p+'_bpsaved'] for p in ('w','l')]
    sg=[games[i]-tb[i]-broken[1-i]+broken[i] for i in (0,1)]
    if min(sg)<=0 or abs(sg[0]-sg[1])>1+sum(tb) or any(vals[p+'_svpt']<4*sg[i] for i,p in enumerate(('w','l'))): return None,'invalid_reconstructed_service_games'
    out={'score':g['result'],'tourney_date':g['date'].replace('-','')}
    for i,p in enumerate(('w','l')):
        for dest,src in [('ace','ace'),('df','df'),('svpt','svpt'),('1stIn','fs'),('1stWon','w1s'),('2ndWon','w2s'),('bpSaved','bpsaved'),('bpFaced','bpfaced')]: out[p+'_'+dest]=str(vals[p+'_'+src])
        out[p+'_SvGms']=str(sg[i])
    return out,None

def build(as_of, histories, fresh=True):
    rows=[]
    for (tour,pid,name), hist in histories.items():
        buckets=defaultdict(B['empty_totals'])
        for d,r,p,src in hist:
            age=(as_of-d).days
            if age<=0 or age>1460 or (not fresh and src=='oncourt'): continue
            for w,days in B['WINDOW_DAYS'].items():
                if age<=days:
                    for surf in (r['surface'],'All'):
                        B['add_side'](buckets[(surf,w)],r,won=p=='w',prefix=p,opp_prefix='l' if p=='w' else 'w')
        for (surf,w),total in buckets.items():
            if total['matches']:
                rows.append(B['totals_row'](tour=tour,player_id=pid,player_name=name,surface=surf,window=w,totals=total))
    return rows

def write(path,rows):
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in rows for k in r)));w.writeheader();w.writerows(rows)

def sources(as_of, output):
    global HERE
    HERE = output
    histories=defaultdict(list); fixtures=[]; report={}; hashes={}
    aliases=read(ROOT/'data/tennis-props/player-name-aliases.csv')
    for tour in ('atp','wta'):
        legacy=[]; names=defaultdict(set); canonical={}
        for y in range(max(2022,as_of.year-4),as_of.year+1):
            path=ROOT/f'data/sackmann/{tour}_matches_{y}.csv'
            if not path.exists(): continue
            hashes[str(path.relative_to(ROOT))]=hashlib.sha256(path.read_bytes()).hexdigest()
            for r in read(path):
                d=B['parse_date'](r['tourney_date'])
                if d is None: continue
                r['surface']=B['norm_surface'](r['surface'])
                legacy.append((d,r))
                for p,side in [('w','winner'),('l','loser')]:
                    pid=r[side+'_id'].strip(); name=r[side+'_name'].strip()
                    names[norm(name)].add(pid);canonical[pid]=name
        for a in aliases:
            if a['tour'].lower()==tour and norm(a['player_name']) in names:
                names[norm(a['alias'])].update(names[norm(a['player_name'])])
        def identity(name, oid):
            ids=names.get(norm(name),set())
            if len(ids)==1:
                pid=next(iter(ids));return pid,canonical[pid]
            if len(ids)>1: return None
            return 'oc:'+oid,name
        # Preserve the exact original player buckets and rows.
        for d,r in legacy:
            for p,side in [('w','winner'),('l','loser')]:
                histories[(tour,r[side+'_id'],canonical[r[side+'_id']])].append((d,r,p,'sackmann'))
        legacy_idx=defaultdict(list)
        for d,r in legacy:
            sets=score(r['score'])
            if sets: legacy_idx[(r['winner_id'],r['loser_id'],tuple(sets))].append((d,r))
        base=ROOT/'data/oncourt'
        for kind in ('players','tours','games','stat'):
            path=base/f'{kind}_{tour}.csv';hashes[str(path.relative_to(ROOT))]=hashlib.sha256(path.read_bytes()).hexdigest()
        players={r['id']:r['name'] for r in read(base/f'players_{tour}.csv')}
        tours={r['id']:r for r in read(base/f'tours_{tour}.csv')}
        stats=defaultdict(list)
        for s in read(base/f'stat_{tour}.csv'): stats[key(s)].append(s)
        exclusions=Counter();accepted=[];overlap=[];latest=[]; seen=set()
        courts={'1':'Hard','2':'Clay','3':'Hard','4':'Carpet','5':'Grass','6':'Hard'}
        for g in read(base/f'games_{tour}.csv'):
            d=B['parse_date'](g['date'])
            if not d or d<date(as_of.year-1,1,1) or d>=as_of: continue
            t=tours.get(g['tour_id'],{})
            if not BOARD['is_supported_main_tour'](t) or int(g['round_id'])<4: continue
            if key(g) in seen: exclusions['duplicate_game_key']+=1;continue
            seen.add(key(g))
            identities=[identity(players.get(g[s+'_id'],''),g[s+'_id']) for s in ('winner','loser')]
            if not all(identities) or any(not i[1] for i in identities): exclusions['ambiguous_identity']+=1;continue
            sets=score(g['result'])
            if not sets: exclusions['unfinished_or_unsupported_score']+=1;continue
            candidates=[(ld,lr) for ld,lr in legacy_idx.get((identities[0][0],identities[1][0],tuple(sets)),[]) if 0<=(d-ld).days<=21]
            if len(candidates)==1: latest.append(d)
            ss=stats.get(key(g),[])
            if len(ss)!=1: exclusions['missing_or_ambiguous_stats']+=1;continue
            r,err=adapt(g,ss[0])
            if err: exclusions[err]+=1;continue
            if t.get('court_id') not in courts: exclusions['unknown_surface']+=1;continue
            r.update(surface=courts[t['court_id']],tour=tour,tournament=t['name'],tour_id=g['tour_id'],round_id=g['round_id'],fixture_id=tour+':'+':'.join(key(g)))
            for i,side in enumerate(('winner','loser')): r[side+'_id'],r[side+'_name']=identities[i]
            if len(candidates)==1:
                lr=candidates[0][1]
                diffs={k:int(r[k])-int(float(lr[k])) for k in r if k.startswith(('w_','l_')) and lr.get(k,'').strip() and re.fullmatch(r'\d+(\.0)?',lr[k])}
                overlap.append(dict(date=d.isoformat(),fixture=r['fixture_id'],diffs=diffs,old=lr,new=r))
            accepted.append((d,r,len(candidates)>0))
        cutoff=max(latest)
        appended=[(d,r) for d,r,matched in accepted if d>cutoff and not matched]
        for d,r in appended:
            fixtures.append((d,r))
            for p,side in [('w','winner'),('l','loser')]: histories[(tour,r[side+'_id'],r[side+'_name'])].append((d,r,p,'oncourt'))
        fields=sorted({k for x in overlap for k in x['diffs']})
        parity={k:dict(n=sum(k in x['diffs'] for x in overlap),exact=sum(x['diffs'].get(k)==0 for x in overlap),mismatches=sum(k in x['diffs'] and x['diffs'][k]!=0 for x in overlap)) for k in fields}
        report[tour]=dict(append_after=cutoff.isoformat(),appended_matches=len(appended),latest_appended=max(d for d,r in appended).isoformat(),overlap_matches=len(overlap),parity=parity,exclusions=dict(exclusions))
        # Detailed overlap was validated before registration; keep only compact audit here.
        print(tour,report[tour],flush=True)
    (HERE/'source-audit.json').write_text(json.dumps(dict(report=report,hashes=hashes),indent=2))
    return histories,sorted(fixtures,key=lambda x:(x[0],x[1]['fixture_id'])),report

