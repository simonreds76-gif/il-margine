"""Current props inputs from retained history plus verified OnCourt results.

No network, parameter fitting or stake changes. Coverage dates and file hashes,
not output timestamps, determine whether an input is usable.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

VERSION = 'oncourt-current-history-20261007-v1'
ROOT = Path(__file__).resolve().parents[1]
MAX_RESULT_AGE_DAYS = 14
MAX_EXPORT_AGE_HOURS = 48


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    with path.open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def write(path, rows):
    if not rows:
        raise ValueError('Empty current player history')
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer=csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader();writer.writerows(rows)


def activity(root, as_of, baseline, adapter):
    """Activity includes completed main, qualifying and Challenger singles.

    Count rates retain their existing main-tour scope. Activity does not infer
    inactivity from absent point statistics or a stopped archival feed.
    """
    names=defaultdict(set)
    for row in baseline:
        names[(row['tour'].lower(),adapter.norm(row['player_name']))].add((row['player_id'],row['player_name']))
    excluded=Counter();buckets={};latest_by_scope={}
    for tour in ('atp','wta'):
        source=root/'data/oncourt'
        players={r['id']:r['name'] for r in read(source/f'players_{tour}.csv')}
        tours={r['id']:r for r in read(source/f'tours_{tour}.csv')}
        stats=defaultdict(list)
        for row in read(source/f'stat_{tour}.csv'):stats[adapter.key(row)].append(row)
        games=defaultdict(list)
        for row in read(source/f'games_{tour}.csv'):games[adapter.key(row)].append(row)
        for identity, group in games.items():
            g=group[0];played=adapter.B['parse_date'](g['date'])
            if not played or not 0<(as_of-played).days<=1460:continue
            if len({(r['date'],r['result']) for r in group})!=1:
                excluded['conflicting_results']+=1;continue
            if not adapter.score(g['result']):continue
            tournament=tours.get(g['tour_id'],{})
            main=adapter.BOARD['is_supported_main_tour'](tournament)
            challenger=tour=='atp' and tournament.get('rank')=='1'
            if not(main or challenger):continue
            phase='main' if main and int(g['round_id'])>=4 else 'qual_chall'
            scope=tour+'_'+phase
            latest_by_scope[scope]=max(latest_by_scope.get(scope,played),played)
            for prefix,side in (('w','winner'),('l','loser')):
                oid=g[side+'_id'];name=players.get(oid,'')
                if not name or '/' in name or '&' in name:
                    excluded['doubles_or_unknown_player']+=1;continue
                options=names.get((tour,adapter.norm(name)),set())
                if len(options)>1:
                    excluded['ambiguous_player_name']+=1;continue
                pid,canonical=next(iter(options)) if options else ('oc:'+oid,name)
                candidates=stats.get(identity,[]);points=0
                if len(candidates)==1:
                    try:points=max(0,int(candidates[0].get(prefix+'_svpt') or candidates[0].get(prefix+'_fsof') or 0))
                    except (ValueError,TypeError):pass
                for window,days in adapter.B['WINDOW_DAYS'].items():
                    if (as_of-played).days>days:continue
                    key=(tour,pid,window)
                    if key not in buckets:
                        buckets[key]=dict(tour=tour.upper(),player_id=pid,player_name=canonical,window=window,
                            matches=0,svpt=0,main_matches=0,main_svpt=0,qual_chall_matches=0,qual_chall_svpt=0,
                            last_match_date=played.isoformat(),days_since_last_match=0)
                    row=buckets[key];row['matches']+=1;row['svpt']+=points
                    row[phase+'_matches']+=1;row[phase+'_svpt']+=points
                    row['last_match_date']=max(row['last_match_date'],played.isoformat())
                    row['days_since_last_match']=(as_of-date.fromisoformat(row['last_match_date'])).days
    return list(buckets.values()),dict(excluded),{k:v.isoformat() for k,v in latest_by_scope.items()}


def validate_source_audit(audit, as_of):
    for tour in ('atp','wta'):
        group=audit[tour]
        if group['overlap_matches']<100:raise ValueError('Insufficient source overlap: '+tour)
        for field in ('w_ace','l_ace','w_df','l_df'):
            evidence=group['parity'].get(field,{})
            if not evidence.get('n') or evidence['exact']/evidence['n']<.98:
                raise ValueError('Source count parity failed: '+tour+':'+field)
        latest=date.fromisoformat(group['latest_appended'])
        if not 0<(as_of-latest).days<=MAX_RESULT_AGE_DAYS:
            raise ValueError('Player-history result coverage stale: '+tour)


def prepare(root, as_of, output):
    import tennis_props_full_refresh as adapter
    from tennis_source_contract import court_surfaces
    adapter.ROOT=root
    output.mkdir(parents=True,exist_ok=True)
    source=root/'data/oncourt';now=datetime.now(timezone.utc)
    authoritative=court_surfaces(source/'courts.csv',combine_hard=True)
    for identifier,surface in {'1':'Hard','2':'Clay','3':'Hard','4':'Carpet','5':'Grass','6':'Hard'}.items():
        if authoritative.get(identifier)!=surface:raise ValueError('Source-adapter court reference changed')
    for tour in ('atp','wta'):
        for kind in ('players','tours','games','stat'):
            path=source/f'{kind}_{tour}.csv'
            age=(now.timestamp()-path.stat().st_mtime)/3600
            if not -.1<=age<=MAX_EXPORT_AGE_HOURS:raise ValueError('OnCourt export not current: '+path.name)
    histories,fixtures,audit=adapter.sources(as_of,output)
    validate_source_audit(audit,as_of)
    baseline=adapter.build(as_of,histories,True)
    if len(baseline)<100:raise ValueError('Incomplete current baseline')
    activities,excluded,activity_dates=activity(root,as_of,baseline,adapter)
    write(output/'player-props-baseline.csv',baseline)
    write(output/'player-props-activity.csv',activities)
    source_audit=json.loads((output/'source-audit.json').read_text(encoding='utf-8'))
    source_audit['hashes']['data/oncourt/courts.csv']=sha(source/'courts.csv')
    for name,digest in source_audit['hashes'].items():
        if sha(root/name)!=digest:raise ValueError('Input changed during history rebuild: '+name)
    status=dict(state='CURRENT',version=VERSION,as_of=as_of.isoformat(),generated_at=now.isoformat(),
        feature_cutoff='Completed results strictly before '+as_of.isoformat(),
        baseline_rows=len(baseline),activity_rows=len(activities),sources=audit,
        activity_latest_results=activity_dates,activity_exclusions=excluded,
        source_hashes=source_audit['hashes'],
        output_hashes={name:sha(output/name) for name in ('player-props-baseline.csv','player-props-activity.csv')},
        max_result_age_days=MAX_RESULT_AGE_DAYS,max_export_age_hours=MAX_EXPORT_AGE_HOURS,
        models_changed=False,stake_changed=False,
        note='Current OnCourt main-tour count history; qualifying and Challenger included in activity. Historical archive retained.')
    (output/'player-history-status.json').write_text(json.dumps(status,indent=2),encoding='utf-8')
    return status


def history_health(props, as_of, check_hash=True):
    path=props/'player-history-status.json'
    try:
        status=json.loads(path.read_text(encoding='utf-8'))
        if status.get('state')!='CURRENT' or status.get('version')!=VERSION:raise ValueError('Unsupported history version')
        if status.get('as_of')!=str(as_of):raise ValueError('Player history has not been rebuilt for this day')
        validate_source_audit(status['sources'],date.fromisoformat(str(as_of)))
        if check_hash:
            for name,digest in status['output_hashes'].items():
                if sha(props/name)!=digest:raise ValueError('Generated history changed: '+name)
        return status
    except (OSError,ValueError,KeyError,TypeError) as exc:
        return dict(state='PLAYER_HISTORY_BLOCKED',reason=str(exc))


def publish(root, prepared):
    props=root/'data/tennis-props';status=json.loads((prepared/'player-history-status.json').read_text(encoding='utf-8'))
    if history_health(prepared,status['as_of'])['state']!='CURRENT':
        raise ValueError('Prepared history failed validation')
    # A morning export may have changed while this build awaited publication.
    # Validate everything before replacing even the first live input.
    for name,digest in status['source_hashes'].items():
        if sha(root/name)!=digest:
            raise ValueError('Source changed since preparation: '+name)
    # Preserve the previous baseline for the existing paired source comparison.
    reference=props/'history-reference';reference.mkdir(exist_ok=True)
    for name in status['output_hashes']:
        previous=props/name
        if previous.exists() and not (reference/name).exists():shutil.copy2(previous,reference/name)
    (reference/'README.txt').write_text('Retained pre-current-history inputs. Historical comparison only; never the default live source.\n',encoding='utf-8')
    for name in (*status['output_hashes'],'player-history-status.json'):
        temp=props/(name+'.current-tmp');shutil.copy2(prepared/name,temp);temp.replace(props/name)
    if history_health(props,status['as_of'])['state']!='CURRENT':raise ValueError('Published history readback failed')


def ensure_current(root, as_of):
    props=root/'data/tennis-props'
    existing=history_health(props,str(as_of))
    if existing['state']=='CURRENT' and all(sha(root/name)==digest for name,digest in existing['source_hashes'].items()):
        return existing
    with tempfile.TemporaryDirectory(prefix='current-history-',dir=props) as directory:
        folder=Path(directory)
        status=prepare(root,date.fromisoformat(str(as_of)),folder)
        publish(root,folder)
    return status


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--as-of',default=date.today().isoformat());parser.add_argument('--out',type=Path)
    parser.add_argument('--publish',action='store_true');args=parser.parse_args()
    props=args.root/'data/tennis-props';props.mkdir(parents=True,exist_ok=True)
    if args.publish and not args.out:
        status=ensure_current(args.root,args.as_of)
    elif args.out:
        status=prepare(args.root,date.fromisoformat(args.as_of),args.out)
        if args.publish:publish(args.root,args.out)
    else:
        with tempfile.TemporaryDirectory(prefix='current-history-',dir=props) as directory:
            folder=Path(directory);status=prepare(args.root,date.fromisoformat(args.as_of),folder)
            if args.publish:publish(args.root,folder)
    print(json.dumps({k:status[k] for k in ('state','version','as_of','baseline_rows','activity_rows','activity_latest_results')}))


if __name__=='__main__':main()
