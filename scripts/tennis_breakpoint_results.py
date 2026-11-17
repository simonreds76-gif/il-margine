"""Settlement-only successor to the registered Break Point C evidence reader."""
import argparse,hashlib,json
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path
from oncourt_nonplayed import verified_nonplayed
from tennis_breakpoint_evidence import (
    RELATIVE,append,atomic,completed_score,digest,locked,norm,read_csv,rows,same_venue,utc,valid_counts,
)


def walkover_venue(tour, group, edition):
    if same_venue(group,edition.get('name','')):return True
    # Exact sponsor/short-title alias at the same venue. Players, native date and tour
    # must also match. Never accept a substring of an arbitrary city or tournament.
    return (tour,norm(group),norm(edition.get('name',''))) == (
        'ATP','stockholmopen','bnpparibasnordicopenstockholm')


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
        sidecar=base/f'nonplayed-results_{tour.lower()}.csv'
        if sidecar.exists():paths['nonplayed']=sidecar
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
        extras=defaultdict(list)
        for g in verified_nonplayed(sidecar):
            pair=frozenset((g['winner_id'],g['loser_id']))
            if pair in needed:extras[pair].append(g)
        keys={tuple(g[k] for k in ('winner_id','loser_id','tour_id','round_id')) for gs in (*games.values(),*extras.values()) for g in gs}
        keys.update((b,a,t,r) for a,b,t,r in list(keys))
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
                nonplayed=[g for g in extras[pair] if g['date']==start.date().isoformat()
                           and walkover_venue(tour,q['group'],tours.get(g['tour_id'],{}))]
                unique={tuple(sorted(g.items())) for g in candidates}
                if nonplayed:
                    g=nonplayed[0];a,b,edition,rnd=(g[k] for k in ('winner_id','loser_id','tour_id','round_id'))
                    conflict=any(x['tour_id']==edition and x['round_id']==rnd for x in games[pair])
                    if (len(nonplayed)!=1 or candidates or conflict or stats[(a,b,edition,rnd)] or stats[(b,a,edition,rnd)]
                            or not utc(q.get('capture_at')) or not utc(q['capture_at'])<start<=now):
                        state['status']='CONFLICTING_NONPLAYED_EVIDENCE'
                    else:
                        state.update(status='VERIFIED_WALKOVER_NO_PLAY',native_fixture=':'.join((a,b,edition,rnd)),
                            score=g['result'],result_date=g['date'],native_tournament=tours[edition]['name'],
                            result_source='verified_dated_native_walkover',source_row_sha256=digest(g))
                elif len(unique)>1:state['status']='AMBIGUOUS_FIXTURE'
                elif candidates:
                    g=candidates[0];key=tuple(g[k] for k in ('winner_id','loser_id','tour_id','round_id'))
                    state.update(native_fixture=':'.join(key),score=g['result'],result_date=g['date'],native_tournament=tours[g['tour_id']]['name'])
                    ss={tuple(sorted(s.items())) for s in stats[key]}
                    counts=valid_counts(stats[key][0],g['result']) if len(ss)==1 else None
                    if not completed_score(g['result']):state['status']='UNFINISHED_CONTRACT_REVIEW'
                    elif not counts:state['status']='MISSING_OR_CONFLICTING_STATS'
                    else:
                        state['y']=counts['w_bpfaced']+counts['l_bpfaced']
                        state['validated_counts']=counts
                        state['status']='COMPLETED_RESEARCH_OUTCOME';state['over_hit']=state['y']>q['line']
                        state['result_source']='native_exact_fixture_reciprocal_bp_counts'
                elif (now-start).total_seconds()>48*3600:state['status']='OVERDUE_EXACT_FIXTURE_UNRESOLVED'
            prior=latest.get(q['id'],{})
            if prior.get('status')=='VERIFIED_WALKOVER_NO_PLAY' and state['status'] in {
                    'PENDING_RESULT','IDENTITY_UNRESOLVED','OVERDUE_EXACT_FIXTURE_UNRESOLVED'}:
                continue
            if prior.get('status')=='COMPLETED_RESEARCH_OUTCOME' and state['status']=='VERIFIED_WALKOVER_NO_PLAY':
                state.update(status='CONFLICTING_NONPLAYED_EVIDENCE',prior_state_hash=prior.get('state_hash'))
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

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    args=p.parse_args()
    print(json.dumps(settle(args.root)))
    from tennis_nonplay_reconcile import run
    print(json.dumps(run(args.root)))
