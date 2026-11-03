"""Offline descriptive conditions explorer v1. No pricing, selections or network.

Reconstructs date-safe same-phase edition labels, excluding BOTH target players.
Missing labels never inherit later edition information or an unverified venue.
"""
import argparse,csv,json,math,re,hashlib,gzip
from collections import defaultdict,deque,Counter
from datetime import date,timedelta
from pathlib import Path
from itertools import groupby
VERSION='conditions-asof-spw-v1'
SURF={'1':'Hard','2':'Clay','3':'I.hard','5':'Grass'}
MIN_MATCHES=5
MIN_POINTS=600
PRIOR_POINTS=1500
def read(p):
    with p.open(encoding='utf-8-sig',newline='') as f:yield from csv.DictReader(f)
def write(p,x):
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,separators=(',',':'),allow_nan=False),encoding='utf8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def num(x):
    try:
        n=int(x);return n if n>=0 else None
    except (ValueError,TypeError):return None
def phase(r):
    n=num(r)
    return 'Q' if n in (0,1,2,3) else 'M' if n in (4,5,6,7,9,10,12) else None
def score(s):
    if not re.fullmatch(r'\d+-\d+(?:\(\d+\))?(?: \d+-\d+(?:\(\d+\))?){1,4}',s or ''):return None
    sets=[(int(a),int(b)) for a,b in re.findall(r'(\d+)-(\d+)(?:\(\d+\))?',s)]
    if any(not ((max(a,b)==6 and min(a,b)<=4) or (max(a,b)>=7 and abs(a-b)==2) or {a,b}=={6,7}) for a,b in sets):return None
    wins,losses=sum(a>b for a,b in sets),sum(b>a for a,b in sets)
    if wins not in (2,3) or losses>=wins or sets[-1][0]<=sets[-1][1]:return None
    return sets
def metrics(g,s):
    """Independent per-field checks; missing point data does not erase game data."""
    sets=score(g['result']);out=[{},{}]
    for i,(a,b) in enumerate((('w','l'),('l','w'))):
        n=lambda k:num(s.get(a+'_'+k));o=lambda k:num(s.get(b+'_'+k))
        sp,w1,w2=n('svpt'),n('w1s'),n('w2s')
        sw=w1+w2 if w1 is not None and w2 is not None else None
        op,ow1,ow2=o('svpt'),o('w1s'),o('w2s')
        rw=n('rpw');rp=n('rpwof')
        if sp and sw is not None and sw<=sp and (o('rpw') is None or o('rpw')==sp-sw):out[i].update(sw=sw,sp=sp)
        if rp and rw is not None and rw<=rp and rp==op and ow1 is not None and ow2 is not None and rw==op-ow1-ow2:out[i].update(rw=rw,rp=rp)
        for k in ('ace','df'):
            v=n(k)
            if sp and v is not None and v<=sp and (k!='ace' or sw is None or v<=sw):out[i][k]=v;out[i][k+'p']=sp
    bw,bl=num(s.get('w_bpw')),num(s.get('l_bpw'))
    reciprocal=all(num(s.get(p+'_bpfaced')) is not None and num(s.get(p+'_bpsaved')) is not None and num(s.get(q+'_bpw'))==num(s.get(p+'_bpfaced'))-num(s.get(p+'_bpsaved')) for p,q in (('w','l'),('l','w')))
    if sets and bw is not None and bl is not None and reciprocal:
        games=[sum(x[i] for x in sets)-sum({a,b}=={6,7} and (a>b if i==0 else b>a) for a,b in sets) for i in (0,1)]
        holds=[games[0]-bw,games[1]-bl];sg=[holds[0]+bl,holds[1]+bw]
        if min(holds)>=0 and min(sg)>0 and abs(sg[0]-sg[1])<=1+sum({a,b}=={6,7} for a,b in sets) and all('sp' not in out[i] or out[i]['sp']>=4*sg[i] for i in (0,1)):
            for i in (0,1):out[i].update(h=holds[i],sg=sg[i],b=(bw,bl)[i],rg=sg[1-i])
    return out
def plus(a,b,sign=1):
    for i,v in enumerate(b):a[i]+=sign*v
def sub(a,b):return [x-y for x,y in zip(a,b)]
def lg(x):return math.log(max(.01,min(.99,x))/(1-max(.01,min(.99,x))))
def sig(x):return 1/(1+math.exp(-x))
class History:
    def __init__(self):
        self.p=defaultdict(lambda:[0]*4);self.pe=defaultdict(lambda:[0]*4);self.g=defaultdict(lambda:[0]*4);self.ge=defaultdict(lambda:[0]*4);self.q=deque()
    def expire(self,day):
        while self.q and self.q[0][0]<day-730:
            _,p,s,e,v=self.q.popleft()
            for a in (self.p[p,s],self.pe[p,s,e],self.g[s],self.ge[s,e]):plus(a,v,-1)
    def prior(self,p,s,e):
        g=sub(self.g[s],self.ge[s,e]);a=sub(self.p[p,s],self.pe[p,s,e]);base=(g[0]+630)/(g[1]+1000)
        return ((a[0]+500*base)/(a[1]+500),(a[2]+500*(1-base))/(a[3]+500),base,a[1]+a[3])
    def add(self,day,p,s,e,m):
        if 'sw' not in m or 'rw' not in m:return
        v=[m['sw'],m['sp'],m['rw'],m['rp']]
        for a in (self.p[p,s],self.pe[p,s,e],self.g[s],self.ge[s,e]):plus(a,v)
        self.q.append((day,p,s,e,v))
class Edition:
    def __init__(self):self.total=[0.,0.,0.];self.player=defaultdict(lambda:[0.,0.,0.]);self.pair=defaultdict(lambda:[0.,0.,0.]);self.latest=None
    def label(self,a,b):
        v=sub(sub(self.total,self.player[a]),self.player[b]);plus(v,self.pair[tuple(sorted((a,b)))])
        return (100+100*v[0]/(v[1]+PRIOR_POINTS) if v[2]>=MIN_MATCHES and v[1]>=MIN_POINTS else None,int(v[2]),int(v[1]))
    def add(self,a,b,m,q,day):
        if not all('sw' in r for r in m):return
        v=[sum(m[i]['sw']-m[i]['sp']*q[i] for i in (0,1)),sum(r['sp'] for r in m),1]
        for r in (self.total,self.player[a],self.player[b],self.pair[tuple(sorted((a,b)))]):plus(r,v)
        self.latest=day
def quantile(xs,q):
    x=sorted(xs);pos=(len(x)-1)*q;i=int(pos);return x[i]+(x[min(i+1,len(x)-1)]-x[i])*(pos-i)
def build(root,out,asof):
    src=root/'data/oncourt';paths={x:src/(x+'_atp.csv') for x in ('players','games','stat','tours')}
    names={r['id']:r for r in read(paths['players'])};tours={};excluded=Counter();cutoff=(asof-timedelta(days=1095)).isoformat()
    for t in read(paths['tours']):
        name=t['name'].lower();s=SURF.get(t['court_id'])
        if not s or t['date']<'2019-01-01' or t['date']>=asof.isoformat():continue
        if any(w in name for w in ('juniors','next gen','nextgen','davis cup','laver cup','united cup','atp cup','exhibition','olympic')):excluded['unsupported_event']+=1;continue
        tier='CH' if 'challenger' in name else 'ITF' if re.search(r'\bm\d{1,3}\b|futures|itf',name) else 'ATP' if t['rank'] in ('2','3','4') or 'masters cup' in name or 'atp finals' in name else None
        if tier:tours[t['id']]={**t,'surface':s,'tier':tier}
    gg=defaultdict(list)
    for g in read(paths['games']):
        if g['tour_id'] not in tours or not '2019-01-01'<=g['date']<asof.isoformat():continue
        a,b=g['winner_id'],g['loser_id'];k=(g['tour_id'],g['round_id'],*sorted((a,b)))
        gg[k].append(g)
    games=[]
    for group in gg.values():
        g=group[0];a,b=g['winner_id'],g['loser_id'];tier=tours[g['tour_id']]['tier']
        why='conflicting_results' if len({(r['date'],r['result'],r['winner_id']) for r in group})>1 else 'invalid_score' if not score(g['result']) else 'unsupported_round' if not phase(g['round_id']) else 'unknown_or_doubles' if a==b or any(p not in names or '/' in names[p]['name'] for p in (a,b)) else None
        if why:excluded[tier+':'+why]+=1;continue
        games.append(g)
    del gg
    wanted={tuple(g[k] for k in ('winner_id','loser_id','tour_id','round_id')) for g in games};stats={};bad=set()
    for s in read(paths['stat']):
        k=tuple(s[x] for x in ('winner_id','loser_id','tour_id','round_id'))
        if k not in wanted:continue
        if k in stats and stats[k]!=s:bad.add(k)
        else:stats[k]=s
    hist=History();editions=defaultdict(Edition);calibration=defaultdict(list);rows=[];coverage=Counter();recon=Counter()
    for day,group in groupby(sorted(games,key=lambda r:(r['date'],r['tour_id'],r['round_id'],r['winner_id'])),key=lambda r:r['date']):
        ordinal=date.fromisoformat(day).toordinal();hist.expire(ordinal);updates=[]
        for g in group:
            a,b=g['winner_id'],g['loser_id'];t=tours[g['tour_id']];s=t['surface'];ph=phase(g['round_id']);e=(t['id'],ph)
            k=tuple(g[x] for x in ('winner_id','loser_id','tour_id','round_id'));m=metrics(g,stats.get(k,{}) if k not in bad else {})
            pa,pb=hist.prior(a,s,t['id']),hist.prior(b,s,t['id']);q=[sig(lg(pa[0])+lg(1-pb[1])-lg(pa[2])),sig(lg(pb[0])+lg(1-pa[1])-lg(pb[2]))]
            label,n,pts=editions[e].label(a,b)
            assert editions[e].latest is None or editions[e].latest<day
            if '2021-01-01'<=day<'2023-01-01' and label is not None:calibration[s].append(label)
            if day>=cutoff:
                coverage['|'.join((t['tier'],s,ph,g['round_id'],'labelled' if label is not None else 'unknown'))]+=1
                recon[t['tier']+':'+('game_stats_valid' if 'h' in m[0] else 'game_stats_missing_or_invalid')]+=1
                common={'d':day,'t':t['id'],'s':s,'l':t['tier'],'ph':ph,'r':g['round_id'],'score':g['result'],'pace':round(label,4) if label is not None else None,'pn':n,'pp':pts,'pd':editions[e].latest}
                for i,(p,o,op) in enumerate(((a,b,pb),(b,a,pa))):
                    rows.append((p,{**common,'o':o,'w':i==0,'m':m[i],'opp':[round(op[0],5),round(op[1],5),int(op[3])],'exp':round(q[i],6)}))
            updates.append((a,b,s,t['id'],e,m,q))
        # Date-only source: no within-day ordering is invented.
        for a,b,s,tid,e,m,q in updates:
            editions[e].add(a,b,m,q,day);hist.add(ordinal,a,s,tid,m[0]);hist.add(ordinal,b,s,tid,m[1])
    thresholds={s:{'low':round(quantile(v,1/3),6),'high':round(quantile(v,2/3),6),'n':len(v)} for s,v in calibration.items() if len(v)>=30}
    byplayer=defaultdict(list)
    for p,r in rows:
        th=thresholds.get(r['s']);v=r['pace'];r['band']='unknown' if v is None or th is None else 'slow' if v<th['low'] else 'fast' if v>th['high'] else 'medium'
        byplayer[p].append(r)
    used={r['t'] for _,r in rows};playerindex=[];shards=defaultdict(dict)
    for p,rs in byplayer.items():
        playerindex.append({'id':p,'name':names[p]['name'],'country':names[p]['country'],'matches':len(rs)})
        opponents={r['o']:names[r['o']]['name'] for r in rs};shards[int(p)%128][p]={'id':p,'rows':sorted(rs,key=lambda r:r['d'],reverse=True),'opponents':opponents}
    (out/'shards').mkdir(parents=True,exist_ok=True)
    for bucket,content in shards.items():
        (out/'shards'/f'{bucket}.json.gz').write_bytes(gzip.compress(json.dumps(content,separators=(',',':'),allow_nan=False).encode(),compresslevel=9,mtime=0))
    info={'version':VERSION,'asOf':asof.isoformat(),'from':cutoff,'scope':'Men’s completed singles: ATP, Challenger and ITF; main draw and qualifying separately identified. No WTA, juniors or team events.','minimumMatches':MIN_MATCHES,'minimumPoints':MIN_POINTS,'priorPoints':PRIOR_POINTS,'thresholds':thresholds,'thresholdPeriod':['2021-01-01','2022-12-31'],'knownVenueRegimes':0,'sourceTiming':'Reconstructed by match date, not verified historical publication timestamps. Earlier days only; both players excluded; main and qualifying evidence kept separate.','players':sorted(playerindex,key=lambda p:p['name']),'editions':{p:{'name':tours[p]['name'],'date':tours[p]['date'],'country':tours[p]['country'],'venue':'Not independently verified'} for p in used},'coverage':dict(coverage),'reconciliation':dict(recon),'exclusions':dict(excluded),'matches':len(rows)//2,'labelled':sum(r['band']!='unknown' for _,r in rows)//2}
    write(out/'index.json',info)
    write(out.parent.parent/'outputs/court-speed-profiles/conditions-build-audit.json',{'version':VERSION,'inputs':{str(p):sha(p) for p in paths.values()},'script_sha256':sha(Path(__file__)),'matches':info['matches'],'labelled':info['labelled'],'reconciliation':dict(recon),'exclusions':dict(excluded),'thresholds':thresholds,'live_models_changed':False})
    print(json.dumps({k:info[k] for k in ('matches','labelled','thresholds','reconciliation')}))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--as-of',type=date.fromisoformat,required=True);a=p.parse_args();build(a.root,a.out,a.as_of)
