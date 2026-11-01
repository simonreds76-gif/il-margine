"""Price/outcome evidence only. No model predictions, selections, stakes or alerts.

Consumes the existing Grosvenor raw capture without another odds request.
Quotes are immutable; result observations are appended, preserving revisions.
Only exact completed fixture/date/edition mappings with valid reciprocal counts
are graded for research. Unfinished/ambiguous contracts remain ungraded.
"""
from __future__ import annotations
import argparse,csv,gzip,hashlib,json,re,unicodedata,math,os
from contextlib import contextmanager
from functools import wraps
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path
from tennis_grosvenor import utc,scaled
from tennis_event_integrity import completed_score

RELATIVE=Path('data/tennis-break-points/evidence-v1')
CRITERION=2100114880
MAX_FILE=32*1024*1024

@contextmanager
def process_lock(out):
    out.mkdir(parents=True,exist_ok=True)
    with (out/'.lock').open('a+b') as f:
        if os.name=='nt':
            import msvcrt
            f.seek(0)
            if not f.read(1):f.write(b'0');f.flush()
            f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl;fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        yield

def valid_counts(stat,score):
    vals={}
    try:
        for p in ('w','l'):
            for k in ('bpof','bpw','bpfaced','bpsaved'):
                n=float(stat.get(f'{p}_{k}'))
                if not math.isfinite(n) or n<0 or not n.is_integer():return None
                vals[f'{p}_{k}']=int(n)
    except (TypeError,ValueError):return None
    for p,o in (('w','l'),('l','w')):
        if not(vals[f'{p}_bpof']==vals[f'{o}_bpfaced'] and vals[f'{p}_bpw']<=vals[f'{p}_bpof']
               and vals[f'{p}_bpsaved']<=vals[f'{p}_bpfaced']
               and vals[f'{p}_bpw']==vals[f'{o}_bpfaced']-vals[f'{o}_bpsaved']):return None
    if not completed_score(score):return None
    # Remove tie-break games. Holds + breaks must yield feasible alternating service counts.
    sets=[(int(a),int(b)) for a,b in re.findall(r'(\d+)-(\d+)',score)]
    wg=sum(a-(a==7 and b==6) for a,b in sets);lg=sum(b-(b==7 and a==6) for a,b in sets)
    wb,lb=vals['w_bpw'],vals['l_bpw']
    if wb>wg or lb>lg:return None
    ws=wg-wb+lb;ls=lg-lb+wb
    if min(ws,ls)<0 or abs(ws-ls)>len(sets):return None
    return vals

def locked(fn):
    @wraps(fn)
    def run(root,*args,output=None,**kwargs):
        with process_lock(output or root/RELATIVE):return fn(root,*args,output=output,**kwargs)
    return run

def norm(s):
    if ',' in s:a,b=s.split(',',1);s=b+' '+a
    return re.sub('[^a-z0-9]','',unicodedata.normalize('NFKD',str(s).lower()).encode('ascii','ignore').decode())

def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def rows(path):
    if not path.exists():return []
    if path.stat().st_size>MAX_FILE:raise ValueError('evidence_capacity_reached')
    return [json.loads(s) for s in path.read_text(encoding='utf8').splitlines() if s]
def atomic(path,x):
    path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(x,sort_keys=True,separators=(',',':')),encoding='utf8');tmp.replace(path)
def append(path,data):
    raw=''.join(json.dumps(x,sort_keys=True,separators=(',',':'))+'\n' for x in data)
    if (path.stat().st_size if path.exists() else 0)+len(raw.encode())>MAX_FILE:raise ValueError('evidence_capacity_reached')
    if raw:
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('a',encoding='utf8') as f:f.write(raw)

def parse(receipt,source_file,source_hash):
    good=[];bad=Counter()
    for packet in receipt.get('events',[]):
        payload=packet.get('payload',{});eid=packet.get('requested_id');stamp=packet.get('captured_at');now=utc(stamp)
        events=[e for e in payload.get('events',[]) if str(e.get('id'))==str(eid)]
        if len(events)!=1:bad['event_identity']+=1;continue
        e=events[0];start=utc(e.get('start'));tour=next((t.upper() for t in ('atp','wta') if any(x.get('termKey')==t for x in e.get('path',[]))),None)
        if not(now and start and now<start and e.get('state')=='NOT_STARTED' and tour and e.get('sport')=='TENNIS'):
            bad['not_verified_prematch_singles']+=1;continue
        if any(not e.get(k) or '/' in e[k] or ' & ' in e[k] for k in ('homeName','awayName')):
            bad['team_or_missing_identity']+=1;continue
        for offer in payload.get('betOffers',[]):
            if offer.get('criterion',{}).get('id')!=CRITERION:continue
            oo=offer.get('outcomes',[]);by={x.get('type'):x for x in oo}
            if (str(offer.get('eventId'))!=str(eid) or offer.get('criterion',{}).get('englishLabel')!='Total Break Points'
                or offer.get('betOfferType',{}).get('id')!=6 or 'OFFERED_PREMATCH' not in offer.get('tags',[])
                or len(oo)!=2 or set(by)!={'OT_OVER','OT_UNDER'}):bad['contract_shape']+=1;continue
            over,under=by['OT_OVER'],by['OT_UNDER'];line=scaled(over.get('line'))
            if (line is None or line!=scaled(under.get('line')) or line%1!=.5
                or any(x.get('status')!='OPEN' or scaled(x.get('odds'),price=True) is None
                       or str(x.get('betOfferId'))!=str(offer.get('id')) or not utc(x.get('changedDate'))
                       or utc(x['changedDate'])>now for x in oo)):
                bad['unpaired_closed_invalid_or_future_price']+=1;continue
            item={'event_id':str(eid),'offer_id':str(offer['id']),'criterion_id':CRITERION,'tour':tour,
                  'capture_at':stamp,'scheduled_start':e['start'],'event_state':e['state'],
                  'home':e['homeName'],'away':e['awayName'],'group':e.get('group',''),'group_id':str(e.get('groupId','')),
                  'line':line,'over':scaled(over['odds'],price=True),'under':scaled(under['odds'],price=True),
                  'over_updated_at':over['changedDate'],'under_updated_at':under['changedDate'],
                  'source_url':f"https://www.grosvenorcasinos.com/sport#event/{eid}",
                  'raw_file':str(source_file),'raw_sha256':source_hash,
                  'quote_semantics':'full_match_total_break_point_chances; completed_only_research',
                  'retirement_contract':'unverified; do_not_grade',
                  'predictions_present':False}
            # Schedule changes are separate observations under the same event ID.
            item['id']=digest({k:v for k,v in item.items() if k not in ('raw_file','raw_sha256')})
            good.append(item)
    return good,dict(bad)

@locked
def ingest(root,receipt,raw_path,output=None):
    out=output or root/RELATIVE;out.mkdir(parents=True,exist_ok=True)
    old=rows(out/'quotes.jsonl');seen={r['id'] for r in old}
    parsed,rejected=parse(receipt,raw_path,hashlib.sha256(raw_path.read_bytes()).hexdigest())
    new=[]
    for q in parsed:
        if q['id'] not in seen:new.append(q);seen.add(q['id'])
    append(out/'quotes.jsonl',new)
    atomic(out/'capture-status.json',{'checked_at':datetime.now(timezone.utc).isoformat(),'raw_capture_at':receipt.get('captured_at'),
           'new_quotes':len(new),'total_quotes':len(old)+len(new),'accepted_in_capture':len(parsed),'rejected':rejected,
           'source_errors':receipt.get('errors',[]),'raw_file':str(raw_path),'source_requests_added':0,'paper_bets':0})
    return len(new)

def read_csv(path):
    with path.open(encoding='utf-8-sig',newline='') as f:yield from csv.DictReader(f)

def same_venue(group,name):
    # Exact normalized venue phrase; refuse weak short labels and ambiguous cities.
    g=norm(group);return len(g)>=4 and g in norm(name)

@locked
def settle(root,output=None):
    out=output or root/RELATIVE;out.mkdir(parents=True,exist_ok=True);quotes=rows(out/'quotes.jsonl')
    previous=rows(out/'results.jsonl');latest={r['quote_id']:r for r in previous}
    states=[];sources={};now=datetime.now(timezone.utc)
    for tour in ('ATP','WTA'):
        qq=[q for q in quotes if q['tour']==tour]
        if not qq:continue
        base=root/'data/oncourt';paths={x:base/f'{x}_{tour.lower()}.csv' for x in ('players','tours','games','stat')}
        paths['aliases']=root/'data/tennis-props/player-name-aliases.csv'
        extra_path=root/'config/tennis-breakpoint-evidence-aliases.json'
        if extra_path.exists():paths['research_aliases']=extra_path
        before={x:hashlib.sha256(p.read_bytes()).hexdigest() for x,p in paths.items()}
        aliases={}
        for a in read_csv(paths['aliases']):
            if a.get('tour','').upper()==tour:aliases[norm(a['alias'])]=norm(a['player_name'])
        player_names=defaultdict(list)
        # The alias table names the canonical identity, not necessarily the native spelling.
        # Apply it to BOTH sides of the join; never infer identity from a surname.
        player_rows=list(read_csv(paths['players']))
        extras=json.loads(extra_path.read_text()).get('aliases',[]) if extra_path.exists() else []
        byid={p['id']:p for p in player_rows}
        for a in extras:
            p=byid.get(a.get('native_id'),{})
            if a.get('tour')==tour and all(p.get(k)==a.get(ak) for k,ak in [('name','native_name'),('birthdate','birthdate'),('country','country')]):
                aliases[norm(a['alias'])]=norm(a['native_name'])
        for p in player_rows:
            n=norm(p['name']);player_names[aliases.get(n,n)].append(p['id'])
        tours={r['id']:r for r in read_csv(paths['tours'])}
        needed=set();identities={}
        for q in qq:
            ids=[player_names.get(aliases.get(norm(q[s]),norm(q[s])),[]) for s in ('home','away')]
            if all(len(x)==1 for x in ids) and ids[0]!=ids[1]:
                pair=frozenset([ids[0][0],ids[1][0]]);needed.add(pair);identities[q['id']]=pair
        games=defaultdict(list)
        for g in read_csv(paths['games']):
            pair=frozenset((g['winner_id'],g['loser_id']))
            if pair in needed:games[pair].append(g)
        keys={tuple(g[k] for k in ('winner_id','loser_id','tour_id','round_id')) for gs in games.values() for g in gs}
        stats=defaultdict(list)
        for s in read_csv(paths['stat']):
            key=tuple(s[k] for k in ('winner_id','loser_id','tour_id','round_id'))
            if key in keys:stats[key].append(s)
        sources[tour]=before
        for q in qq:
            state={'quote_id':q['id'],'event_id':q['event_id'],'tour':tour,'status':'PENDING_RESULT','y':None}
            if q['id'] not in identities:state['status']='IDENTITY_UNRESOLVED'
            else:
                start=utc(q['scheduled_start']);pair=identities[q['id']]
                # Exact UTC date only. A local-date mismatch is quarantined, never silently shifted.
                candidates=[g for g in games[pair] if g.get('date')==start.date().isoformat() and same_venue(q['group'],tours.get(g['tour_id'],{}).get('name',''))]
                unique={tuple(sorted(g.items())) for g in candidates}
                if len(unique)>1:state['status']='AMBIGUOUS_FIXTURE'
                elif candidates:
                    g=candidates[0];key=tuple(g[k] for k in ('winner_id','loser_id','tour_id','round_id'))
                    state.update(native_fixture=':'.join(key),score=g['result'],result_date=g['date'],native_tournament=tours[g['tour_id']]['name'])
                    ss={tuple(sorted(s.items())) for s in stats[key]}
                    counts=valid_counts(stats[key][0],g['result']) if len(ss)==1 else None
                    if not completed_score(g['result']):state['status']='UNFINISHED_CONTRACT_REVIEW'
                    elif not counts:state['status']='MISSING_OR_CONFLICTING_STATS'
                    else:
                        state['y']=counts['w_bpfaced']+counts['l_bpfaced']
                        state['status']='COMPLETED_RESEARCH_OUTCOME';state['over_hit']=state['y']>q['line']
                        state['result_source']='native_exact_fixture_reciprocal_bp_counts'
                elif (now-start).total_seconds()>48*3600:state['status']='OVERDUE_EXACT_FIXTURE_UNRESOLVED'
            state['state_hash']=digest(state)
            state['source_hashes']=before
            if latest.get(q['id'],{}).get('state_hash')!=state['state_hash']:
                state['observed_at']=now.isoformat();states.append(state)
            latest[q['id']]=state
        if any(hashlib.sha256(p.read_bytes()).hexdigest()!=before[x] for x,p in paths.items()):raise ValueError('Native source changed during results scan')
    append(out/'results.jsonl',states)
    statuses=Counter(r['status'] for r in latest.values())
    report={'checked_at':now.isoformat(),'quotes':len(quotes),'events':len({q['event_id'] for q in quotes}),
            'statuses':dict(statuses),'events_with_completed_results':len({r['event_id'] for r in latest.values() if r['status']=='COMPLETED_RESEARCH_OUTCOME'}),
            'source_hashes':sources,'new_result_observations':len(states),'paper_bets':0,'roi':None,
            'note':'Price/outcome evidence only; no pre-match model forecast or betting ROI. Date/identity/stat gaps remain explicit.'}
    atomic(out/'report.json',report);return report

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--output',type=Path);p.add_argument('--import-raw',type=Path,action='append',default=[])
    a=p.parse_args()
    for path in a.import_raw:
        b=path.read_bytes();d=json.loads(gzip.decompress(b) if path.suffix=='.gz' else b)
        ingest(a.root,d.get('grosvenor_receipt',d),path,output=a.output)
    print(json.dumps(settle(a.root,output=a.output)))
if __name__=='__main__':main()
