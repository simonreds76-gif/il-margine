"""Frozen Ace Compass research engine. Never imported by live pricing."""
import csv, math, re, unicodedata
from collections import defaultdict, deque, Counter
from datetime import date
import numpy as np
from scipy.special import expit, logit
from scipy.stats import nbinom
from ace_compass_integrity import clean_event_rows, event_phase, match_best_of, event_condition_eligible
SCALE=1.014511518127187
BETA=1.0111304913852972
ALPHA=0.2602974475474904
SURF={'1':'Hard','2':'Clay','3':'I.hard','5':'Grass','6':'Hard'}
def read(path):
    with path.open(encoding='utf-8-sig',newline='') as f: return list(csv.DictReader(f))
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

def lg(p):return math.log(p/(1-p))

def sigmoid(v):return 1/(1+math.exp(-v))

def clip(x):return max(.001,min(.999,float(x)))

def zeros8():return np.zeros(8)
def zeros2():return np.zeros(2)

class State:
    def __init__(self,tour):
        self.p=defaultdict(zeros8);self.pe=defaultdict(zeros8)
        self.g=defaultdict(zeros8);self.ge=defaultdict(zeros8)
        self.queue=deque();self.event=defaultdict(zeros8);self.last={};self.tour=tour
        self.loads=defaultdict(zeros2);self.eventloads=defaultdict(zeros2)
        self.condition_excluded=set()
        self.refs=np.array([.07,.035,.63] if tour=='ATP' else [.045,.05,.58])
        self.prior=20*75*self.refs*(1-self.refs)
    def expire(self,d):
        while self.queue and self.queue[0][0]<d-730:
            _,pid,sf,tid,rank,bo,v=self.queue.popleft();self.p[pid,sf]-=v;self.pe[pid,sf,tid]-=v;self.g[sf]-=v;self.ge[sf,tid]-=v
            self.loads[sf,rank,bo]-=[v[3],1];self.eventloads[sf,rank,bo,tid]-=[v[3],1]
    def feature(self,pid,opp,sf,tid,rank,bo):
        g=self.g[sf]-self.ge[sf,tid];a=self.p[pid,sf]-self.pe[pid,sf,tid];b=self.p[opp,sf]-self.pe[opp,sf,tid]
        ga=(g[:3]+50*self.refs)/(g[3]+50)
        aa=(a[:3]+500*ga)/(a[3]+500)
        ba=(b[4:7]+500*np.array([ga[0],ga[1],1-ga[2]]))/(b[7]+500)
        q=np.array([sigmoid(lg(clip(aa[0]))+lg(clip(ba[0]))-lg(clip(ga[0]))),aa[1],sigmoid(lg(clip(aa[2]))+lg(clip(1-ba[2]))-lg(clip(ga[2])))])
        e=self.event[tid] if tid not in self.condition_excluded else np.zeros(8);theta=np.clip(e[:3]/(e[3:6]+self.prior),-.5,.5)
        load=self.loads[sf,rank,bo]-self.eventloads[sf,rank,bo,tid]
        average_points=(load[0]+50*(115 if bo==5 else 75))/(load[1]+50)
        return dict(q_ace=q[0],q_df=q[1],q_spw=q[2],theta_ace=theta[0],theta_df=theta[1],theta_spw=theta[2],event_player_rows=e[6],event_points=e[7],event_latest=self.last.get(tid,0) if tid not in self.condition_excluded else 0,player_points=a[3],opponent_points=b[7],average_points=average_points)
    def add(self,r,f):
        pid,sf,tid=r['pid'],r['surface'],r['tid'];v=np.array(r['v'],float)
        self.p[pid,sf]+=v;self.pe[pid,sf,tid]+=v;self.g[sf]+=v;self.ge[sf,tid]+=v
        self.queue.append((r['day'],pid,sf,tid,r['rank'],r['best_of'],v));q=np.array([f['q_ace'],f['q_df'],f['q_spw']])
        self.loads[sf,r['rank'],r['best_of']]+=[v[3],1];self.eventloads[sf,r['rank'],r['best_of'],tid]+=[v[3],1]
        self.event[tid]+=np.r_[v[:3]-v[3]*q,v[3]*q*(1-q),1,v[3]];self.last[tid]=r['day']

def supported(t):
    name=' '+t['name'].lower()+' '
    return ('challenger' in name or (str(t['rank']) in ('2','3','4') and not any(x in name for x in ('junior','itf',' m15',' m25',' w15',' w25','qualifying','qualification','wild card','wildcard','play-off','playoff'))))


def history(source, cutoff):
    names={r['id']:r['name'] for r in read(source/'players_atp.csv')}
    tours={r['id']:r for r in read(source/'tours_atp.csv') if r['date']>='2021-01-01' and r['court_id'] in SURF and supported(r)}
    games=[r for r in read(source/'games_atp.csv') if r['tour_id'] in tours and '2021-01-01'<=r['date']<cutoff.isoformat()]
    stats=[r for r in read(source/'stat_atp.csv') if r['tour_id'] in tours]
    stats,games,bad=clean_event_rows(stats,games,names);bad=Counter(bad);si={key(r):r for r in stats};rows=[]
    for g in games:
        s=si[key(g)];a,error=adapt(g,s)
        if error:bad[error]+=1;continue
        t=tours[g['tour_id']];phase=event_phase(g['round_id'])
        bo=match_best_of('ATP',t['name'],g['round_id'],slam=t['rank']=='4')
        if phase is None or bo is None or sum(a>b for a,b in score(g['result']))!=(bo+1)//2:bad['unsupported_format']+=1;continue
        for p,q in [('w','l'),('l','w')]:
            v=[int(s[p+'_ace']),int(s[p+'_df']),int(s[p+'_w1s'])+int(s[p+'_w2s']),int(s[p+'_svpt']),int(s[q+'_ace']),int(s[q+'_df']),int(s[p+'_rpw']),int(s[q+'_svpt'])]
            rows.append(dict(fixture=':'.join(key(g)),pid=g['winner_id' if p=='w' else 'loser_id'],opp=g['loser_id' if p=='w' else 'winner_id'],tid=g['tour_id'],day=date.fromisoformat(g['date']).toordinal(),surface=SURF[t['court_id']],rank=t['rank'],best_of=bo,phase=phase,v=v))
    return sorted(rows,key=lambda r:(r['day'],r['fixture'],r['pid'])),tours,dict(bad)


class FacedState(State):
    def __init__(self):
        super().__init__('ATP')
        self.faced=defaultdict(float);self.facede=defaultdict(float);self.fq=deque()

    def expire(self,d):
        super().expire(d)
        while self.fq and self.fq[0][0]<d-730:
            _,opp,sf,tid,e=self.fq.popleft();self.faced[opp,sf]-=e;self.facede[opp,sf,tid]-=e

    def feature(self,pid,opp,sf,tid,rank,bo):
        f=super().feature(pid,opp,sf,tid,rank,bo)
        g=self.g[sf]-self.ge[sf,tid];p=self.p[pid,sf]-self.pe[pid,sf,tid];o=self.p[opp,sf]-self.pe[opp,sf,tid]
        b=(g[0]+50*.07)/(g[3]+50);own=(p[0]+500*b)/(p[3]+500)
        expected=self.faced[opp,sf]-self.facede[opp,sf,tid]
        f.update(b=float(b),player_rate=float(own),opp_current=float((o[4]+500*b)/(o[7]+500)),opp_faced=clip(b*(o[4]+500*b)/(expected+500*b)),expected_conceded=float(expected))
        return f

    def add(self,r,f):
        super().add(r,f)
        e=r['v'][3]*f['player_rate'];opp,sf,tid=r['opp'],r['surface'],r['tid']
        self.faced[opp,sf]+=e;self.facede[opp,sf,tid]+=e;self.fq.append((r['day'],opp,sf,tid,e))


def build_state(rows,cutoff,audit=None,excluded=()):
    state=FacedState();state.condition_excluded=set(excluded);staged={};byday=defaultdict(list)
    limit=cutoff.toordinal()
    rows=[r for r in rows if r['day']<=limit-2]
    for r in rows:byday[r['day']].append(r)
    cursor=0
    for d in sorted(set(byday)|{d+2 for d in byday}|{limit}):
        if d>limit:break
        state.expire(d)
        while cursor<len(rows) and rows[cursor]['day']<=d-2:
            r=rows[cursor];state.add(r,staged.pop((r['fixture'],r['pid'])));cursor+=1
        for r in byday.get(d,[]):
            f=state.feature(r['pid'],r['opp'],r['surface'],r['tid'],r['rank'],r['best_of'])
            staged[r['fixture'],r['pid']]=f
            if audit:audit(r,f)
    return state


def predict(f,line,odds):
    result={}
    for arm,opp in [('control','opp_current'),('candidate','opp_faced')]:
        mu=float(f['average_points']*SCALE*expit(logit(f['player_rate'])+logit(f[opp])-logit(f['b'])+BETA*f['theta_ace']))
        p=float(nbinom.sf(math.floor(line),1/ALPHA,(1/ALPHA)/(1/ALPHA+mu)))
        result[arm]=dict(mean=mu,p_win=p,fair_odds=1/p if p>0 else None,ev=p*odds-1,selected=p*odds-1>=.08-1e-12)
    return result
