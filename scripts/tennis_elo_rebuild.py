"""Elo Rebuild v1: isolated raw ratings; never writes the production Elo table."""
from __future__ import annotations
import argparse, csv, gzip, hashlib, json, math, os, uuid
from collections import Counter, defaultdict
from datetime import date, timedelta, datetime, timezone
from pathlib import Path

VERSION = 'elo-rebuild-v1-20261029'
K = 22.0
INITIAL = 1500.0
SURFACES = {'Hard', 'I.hard', 'Clay', 'Grass', 'Carpet'}

def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        yield from csv.DictReader(f)

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def digest(value): return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
def atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    tmp.write_text(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False), encoding='utf8')
    tmp.replace(path)

def source_manifest(root, paths):
    # Canonical portable keys; filesystem separators are not source changes.
    return {p.relative_to(root).as_posix():sha(p) for p in paths}

def source_history(root):
    from tennis_direct_history import crosswalk
    from tennis_event_integrity import completed_score, event_phase
    from tennis_source_contract import court_surfaces
    native=root/'data/oncourt'; sack=root/'data/sackmann'
    source=[native/'players_atp.csv',native/'tours_atp.csv',native/'games_atp.csv',native/'courts.csv',sack/'atp_players.csv',root/'data/tennis-props/player-name-aliases.csv']
    paths=sorted(sack.glob('atp_matches_*.csv')); source+=paths
    before=source_manifest(root, source)
    players=list(read_csv(source[0])); names={r['id']:r['name'] for r in players}
    tours={r['id']:r for r in read_csv(source[1])}; surfaces=court_surfaces(source[3],combine_hard=False)
    mapping,audit=crosswalk(players,list(read_csv(source[4])),list(read_csv(source[5])))
    inverse=defaultdict(list)
    for a,b in mapping.items(): inverse[b].append(a)
    unique={k:v[0] for k,v in inverse.items() if len(v)==1}
    excluded=Counter(); groups=defaultdict(list); keys={}; conflicts=set()
    for g in read_csv(source[2]):
        t=tours.get(g['tour_id'],{}); surface=surfaces.get(t.get('court_id'))
        if t.get('rank') not in {'1','2','3','4'} or event_phase(g['round_id']) is None:
            excluded['unsupported_level_or_round']+=1;continue
        if surface not in SURFACES: excluded['unknown_surface']+=1;continue
        if not completed_score(g['result']):excluded['unfinished_retirement_walkover']+=1;continue
        if g['winner_id']==g['loser_id'] or any(not names.get(g[s]) or '/' in names[g[s]] or '&' in names[g[s]] for s in ('winner_id','loser_id')):
            excluded['unknown_identity_or_team']+=1;continue
        try: day=date.fromisoformat(g['date']); edition=date.fromisoformat(t['date'])
        except ValueError:excluded['invalid_date']+=1;continue
        if not -14 <= (day-edition).days <= 35:excluded['date_outside_edition']+=1;continue
        key=':'.join([g['tour_id'],g['round_id'],*sorted([g['winner_id'],g['loser_id']],key=int)])
        row={'key':key,'date':day.isoformat(),'available_date':day.isoformat(),'tournament_id':int(g['tour_id']),
             'tournament':t['name'],'round':int(g['round_id']),'winner':int(g['winner_id']),'loser':int(g['loser_id']),
             'surface':surface,'rank':int(t['rank']),'score':g['result'].strip(),'source':'oncourt', 'date_policy':'native_result_date'}
        if key in keys:
            if keys[key]!=row:conflicts.add(key)
            else:excluded['duplicate_native']+=1
        else:keys[key]=row;groups[g['tour_id']].append(row)
    # Older editions sometimes stamp every round with the same edition date.
    # Hold their entire block back; never pretend these are actual match dates.
    for tid,rows in groups.items():
        if len(rows)>10 and len({r['date'] for r in rows})==1:
            safe=(date.fromisoformat(max(rows[0]['date'],tours[tid]['date']))+timedelta(days=14)).isoformat()
            for r in rows:r['available_date']=safe;r['date_policy']='edition_date_plus_14d'
            excluded['date_delayed_matches']+=len(rows)
    index=defaultdict(list)
    for r in keys.values():index[frozenset((r['winner'],r['loser']))].append(r)
    sack_audit=Counter(); used=set()
    norm=lambda s:' '.join(str(s).replace('(','').replace(')','').split())
    for path in paths:
        for s in read_csv(path):
            if not completed_score(s.get('score')):sack_audit['unfinished']+=1;continue
            if s.get('tourney_level') not in {'A','M','G','C'}:sack_audit['unsupported']+=1;continue
            w,l=unique.get(s.get('winner_id')),unique.get(s.get('loser_id'))
            if not w or not l:sack_audit['unmapped_unique_identity']+=1;continue
            try:start=datetime.strptime(s['tourney_date'],'%Y%m%d').date()
            except (KeyError,ValueError):sack_audit['invalid_date']+=1;continue
            possible=[r for r in index[frozenset((int(w),int(l)))] if -7 <= (date.fromisoformat(r['date'])-start).days <= 21]
            candidates=[r for r in possible if r['winner']==int(w) and norm(r['score'])==norm(s.get('score'))
                        and ('Hard' if r['surface']=='I.hard' else r['surface'])==s.get('surface')]
            if len(candidates)!=1:
                sack_audit['ambiguous_or_conflicting' if possible else 'no_native_result_date']+=1
                # A disputed result cannot silently prefer the secondary source.
                conflicts.update(r['key'] for r in possible)
                continue
            r=candidates[0]
            if r['key'] in used:sack_audit['duplicate_archive']+=1;continue
            used.add(r['key']);r['source']='sackmann_with_native_date';r['archive_id']=s.get('tourney_id')
            sack_audit['primary_reconciled']+=1
    rows=sorted((r for k,r in keys.items() if k not in conflicts),key=lambda r:(r['available_date'],r['tournament_id'],r['round'],r['key']))
    excluded['conflicting_fixture']=len(conflicts)
    if before!=source_manifest(root, source):raise ValueError('Source changed during rebuild')
    return rows,{'source_hashes':before,'native_exclusions':dict(excluded),
                 'archive_reconciliation':dict(sack_audit),'unique_crosswalk':len(unique),'ambiguous_crosswalk':sum(len(v)>1 for v in inverse.values()),
                 'sources':dict(Counter(r['source'] for r in rows)),
                 'limitations':['Current corrected source snapshot, not historically archived knowledge.',
                   'Archive primary only where unique native identity, completed score and result date reconcile; remaining validated native history retained.',
                   'Unmatched archive matches withheld; no guessed actual match dates. ATP and Challenger only.']}

def empty_state():return {'version':VERSION,'ratings':{},'counts':{},'last_played':{},'through':None,'matches':0}
def advance(state, rows, cutoff):
    """All updates within a date use the same pre-day ratings; sums are order invariant."""
    by=defaultdict(list)
    for r in rows:
        if r['available_date']<cutoff and (state['through'] is None or r['available_date']>state['through']):by[r['available_date']].append(r)
    ratings=state['ratings'];counts=state['counts'];last=state['last_played']
    for day,block in sorted(by.items()):
        delta=defaultdict(list)
        for r in sorted(block,key=lambda x:x['key']):
            for surf in ('Overall',r['surface']):
                w,l=f"{r['winner']}|{surf}",f"{r['loser']}|{surf}"
                a,b=ratings.get(w,INITIAL),ratings.get(l,INITIAL)
                change=K*(1-1/(1+10**((b-a)/400)))
                delta[w].append(change);delta[l].append(-change)
                for key in (w,l):counts[key]=counts.get(key,0)+1;last[key]=max(last.get(key,''),r['date'])
        for key,values in sorted(delta.items()):ratings[key]=ratings.get(key,INITIAL)+math.fsum(values)
        state['through']=day;state['matches']+=len(block)
    return state

def rating_rows(state):
    return [{'player_id':int(k.split('|')[0]),'surface':k.split('|')[1],'elo':v,'match_count':state['counts'][k],
             'latest_result':state['last_played'][k]} for k,v in sorted(state['ratings'].items())]

def rebuild(root, output, cutoff):
    rows,audit=source_history(root);eligible=[r for r in rows if r['available_date']<cutoff]
    previous=output/'state.json';state=json.loads(previous.read_text()) if previous.exists() else empty_state()
    prefix=[r for r in eligible if state['through'] and r['available_date']<=state['through']]
    mode='incremental'
    if state.get('version')!=VERSION or state.get('prefix_hash')!=digest(prefix) or (state['through'] and state['through']>=cutoff):
        state=empty_state();mode='full_rebuild'
    state=advance(state,eligible,cutoff);state['prefix_hash']=digest(eligible)
    if not eligible:raise ValueError('No eligible completed history')
    output.mkdir(parents=True,exist_ok=True)
    candidate={'version':VERSION,'as_of_exclusive':cutoff,'latest_available_result':state['through'],
        'history_matches':state['matches'],'ratings':rating_rows(state),'history_hash':digest(eligible),'audit':audit}
    candidate['rating_hash']=digest(candidate['ratings'])
    candidate['generated_at']=datetime.now(timezone.utc).isoformat();candidate['build_mode']=mode
    atomic(output/'state.json',state);atomic(output/'candidate.json',candidate)
    # One replaceable canonical history, no daily duplication of the full archive.
    temp=output/'history.json.gz.tmp'
    temp.write_bytes(gzip.compress(json.dumps(rows,separators=(',',':')).encode(),mtime=0));temp.replace(output/'history.json.gz')
    return candidate,rows

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--output',type=Path);p.add_argument('--as-of',default=date.today().isoformat())
    a=p.parse_args();c,_=rebuild(a.root,a.output or a.root/'data/tennis-elo-rebuild',a.as_of)
    print(json.dumps({k:c[k] for k in ('version','history_matches','rating_hash','build_mode','latest_available_result')}))
if __name__=='__main__':main()
