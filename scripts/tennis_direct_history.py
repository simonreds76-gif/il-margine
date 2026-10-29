"""Fresh Direct-only input history. Never rewrites source files or old forecasts.

Frozen feature algebra/weights remain unchanged. OnCourt rows extend the stopped
archive after its last tournament date; overlapping matches are reconciled by
verified player IDs, completed score and a bounded edition date window.
"""
from __future__ import annotations
from collections import Counter, defaultdict
import csv
from datetime import date, datetime, timezone, timedelta
import hashlib
from pathlib import Path
from tennis_props_names import norm_name
from tennis_event_integrity import clean_event_rows, event_phase
from tennis_source_contract import court_surfaces

COHORT = 'most_aces_direct_1x2_v1_oncourt_20261029'

def read(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        yield from csv.DictReader(f)

def crosswalk(players, archive_players, aliases):
    """Only unique exact/explicit-alias name AND equal known DOB joins IDs."""
    names=defaultdict(set); components=defaultdict(set); details={}
    for p in archive_players:
        name=norm_name(p.get('name_first','')+' '+p.get('name_last',''))
        names[name].add(p['player_id']); details[p['player_id']]=p
        tokens=name.split()
        if len(tokens)>=2:components[(tokens[0],tokens[-1],p.get('dob',''))].add(p['player_id'])
    for a in aliases:
        if a.get('tour','').upper()=='ATP':
            names[norm_name(a.get('alias'))].update(names.get(norm_name(a.get('player_name')),set()))
    mapping={}; audit=[]
    for p in players:
        candidates=names.get(norm_name(p.get('name')),set())
        dob=p.get('birthdate','').replace('-','')
        exact=[pid for pid in candidates if dob and details[pid].get('dob')==dob]
        method='unique_name_and_dob'
        tokens=norm_name(p.get('name')).split()
        if not candidates and dob and len(tokens)>=2:
            exact=list(components.get((tokens[0],tokens[-1],dob),set()))
            method='unique_first_last_and_dob'
        if len(exact)==1:
            mapping[p['id']]=exact[0]
            audit.append({'oncourt_id':p['id'],'archive_id':exact[0],'name':p['name'],'method':method})
        # Unknown players keep a separate namespace; never guess an archive ID.
    return mapping,audit

def overlap_candidates(row, index):
    return [r for r in index.get((row['winner_id'],row['loser_id'],row['score']),[])
            if 0 <= (date.fromisoformat(row['_date'])-date.fromisoformat(r['_date'])).days <= 21]

def player_gap(player_id, latest_included, report):
    seen=report.get('latest_completed_by_player',{}).get(player_id,'')
    return bool(seen and seen > latest_included)

def load(root: Path, legacy, as_of: date, factors, *, require_fresh=True):
    # Import the already validated point-stat adapter, with no source mutation.
    from tennis_props_full_refresh import adapt, score, BOARD
    source=root/'data/oncourt'
    paths=[source/f'{kind}_atp.csv' for kind in ('players','tours','games','stat')]+[source/'courts.csv',root/'data/sackmann/atp_players.csv']
    now=datetime.now(timezone.utc)
    if require_fresh:
        for p in paths[:4]:
            age=(now.timestamp()-p.stat().st_mtime)/3600
            if not -.1 <= age <= 48: raise ValueError('Direct OnCourt export stale: '+p.name)
    report={'cohort':COHORT,'source_hashes':{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
            'source_exported_at':{p.name:datetime.fromtimestamp(p.stat().st_mtime,timezone.utc).isoformat() for p in paths[:4]},
            'cutoff_exclusive':as_of.isoformat(),'retrospective_vintage':'current source snapshot; not historical availability'}
    players=list(read(source/'players_atp.csv')); names={p['id']:p['name'] for p in players}
    tours={p['id']:p for p in read(source/'tours_atp.csv')}
    surfaces=court_surfaces(source/'courts.csv',combine_hard=True)
    mapping,identities=crosswalk(players,list(read(root/'data/sackmann/atp_players.csv')),list(read(root/'data/tennis-props/player-name-aliases.csv')))
    report['identity_crosswalk']=identities
    archive=[r for r in legacy if r['_tour']=='ATP']
    cutoff=max(r['_date'] for r in archive)
    report['archive_latest_tournament_date']=cutoff
    # The overlap year is retained for parity; only rows beyond the archive end
    # can extend state. Historical archive contents remain exactly as supplied.
    start=cutoff[:4]+'-01-01'
    games=[r for r in read(source/'games_atp.csv') if start <= r.get('date','') < as_of.isoformat()]
    keys={tuple(r[k] for k in ('winner_id','loser_id','tour_id','round_id')) for r in games}
    stats=[r for r in read(source/'stat_atp.csv') if tuple(r[k] for k in ('winner_id','loser_id','tour_id','round_id')) in keys]
    good_stats,good_games,excluded=clean_event_rows(stats,games,names)
    excluded=Counter(excluded); index=defaultdict(list); pair_index=defaultdict(list)
    for r in archive:
        index[(r['winner_id'],r['loser_id'],r.get('score',''))].append(r)
        pair_index[(r['winner_id'],r['loser_id'])].append(r)
    latest_activity={}; appended=[]; parity=defaultdict(Counter); conflicts=[]; overlap=0
    from tennis_event_integrity import completed_score
    for g in games:
        t=tours.get(g['tour_id'],{})
        if t.get('rank') not in {'1','2','3','4'} or not completed_score(g['result']) or event_phase(g['round_id']) is None:continue
        for key in ('winner_id','loser_id'):
            oid=g[key]; pid=mapping.get(oid,'oc:'+oid)
            if '/' not in names.get(oid,'') and '&' not in names.get(oid,''):
                latest_activity[pid]=max(latest_activity.get(pid,''),g['date'])
    for g,s in zip(good_games,good_stats):
        t=tours.get(g['tour_id'],{}); rank=t.get('rank'); phase=event_phase(g['round_id'])
        if rank not in {'1','2','3','4'} or phase is None:
            excluded['unsupported_level_or_round']+=1;continue
        surface=surfaces.get(t.get('court_id'))
        if surface not in {'Hard','Clay','Grass','Carpet'}:excluded['unknown_surface']+=1;continue
        r,error=adapt(g,s)
        if error:excluded[error]+=1;continue
        main=rank in {'2','3','4'} and phase=='main_draw'
        level={'1':'C','2':'A','3':'M','4':'G'}[rank]
        r.update(_tour='ATP',_date=g['date'],_surface=surface,surface=surface,
                 _source='main' if main else 'qual_chall',_target='yes' if main else 'no',
                 _ace_factor=str(1.0 if main else factors.get(surface,factors.get('global',1.0))),
                 tourney_level=level,tourney_name=BOARD['scheduled_tournament_name'](t['name']) or t['name'],tourney_id='oc:'+g['tour_id'],
                 round=g['round_id'],best_of='5' if sum(a>b for a,b in score(g['result']))==3 else '3',
                 match_num=g['round_id']+':'+g['winner_id']+':'+g['loser_id'],
                 _oncourt_fixture=':'.join(g[k] for k in ('tour_id','round_id','winner_id','loser_id')))
        for side in ('winner','loser'):
            oid=g[side+'_id'];r[side+'_id']=mapping.get(oid,'oc:'+oid);r[side+'_name']=names[oid]
        candidates=overlap_candidates(r,index)
        if len(candidates)>1:excluded['ambiguous_overlap']+=1;continue
        if candidates:
            overlap+=1;old=candidates[0]; different=[]
            for field in ('w_ace','l_ace','w_df','l_df','w_svpt','l_svpt','w_1stIn','l_1stIn','w_1stWon','l_1stWon','w_2ndWon','l_2ndWon'):
                try:equal=float(old[field])==float(r[field])
                except (KeyError,ValueError):continue
                parity[field]['n']+=1;parity[field]['exact']+=int(equal)
                if not equal:different.append(field)
            if different:conflicts.append({'fixture':r['_oncourt_fixture'],'fields':different})
            # Preserve frozen legacy observations, irrespective of later revisions.
            continue
        if r['_date'] <= cutoff:continue
        # Do not append a possible overlap where the score was corrected.
        possible=[old for old in pair_index.get((r['winner_id'],r['loser_id']),[]) if 0 <= (date.fromisoformat(r['_date'])-date.fromisoformat(old['_date'])).days <= 21] if r['_date'] <= (date.fromisoformat(cutoff)+timedelta(days=21)).isoformat() else []
        if possible:excluded['overlap_score_conflict']+=1;continue
        appended.append(r)
    report.update(appended_matches=len(appended),latest_appended=max((r['_date'] for r in appended),default=''),
                  overlap_matches=overlap,parity=dict(parity),conflicts=conflicts,exclusions=dict(excluded),
                  latest_completed_by_player=latest_activity)
    if require_fresh:
        if not appended or (as_of-date.fromisoformat(report['latest_appended'])).days>14:raise ValueError('Direct completed result coverage stale')
        for field in ('w_ace','l_ace','w_svpt','l_svpt'):
            p=parity[field]
            if p['n']<100 or p['exact']/p['n']<.98:raise ValueError('Direct source parity failed: '+field)
    return sorted([*legacy,*appended],key=lambda r:(r['_date'],r['_tour'],r.get('tourney_id',''),r.get('match_num',''))),report
