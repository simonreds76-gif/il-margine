"""Reproducible adult ATP/Challenger/ITF research source. No live DB or pricing writes.

The frozen v1 comparison keeps its old population. This separate source restores
adult ITF history already tested in the 29 October audit, with the SAME K22/K22
arithmetic. No synthetic indoor observations, new coefficients, bets or alerts.
"""
from __future__ import annotations
import argparse,gzip,hashlib,json,os,sys
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from tennis_elo_rebuild import source_history,advance,empty_state,rating_rows,atomic,sha

VERSION='native-adult-elo-source-v1-20261101'
RELATIVE=Path('data/tennis-elo-source/native-adult-v1')

def stream_hash(rows):
    h=hashlib.sha256()
    for row in rows:h.update(json.dumps(row,sort_keys=True,separators=(',',':')).encode()+b'\n')
    return h.hexdigest()

def build(root,output,cutoff):
    if output.resolve()==(root/'data/tennis-elo-rebuild').resolve():
        raise ValueError('Frozen comparison output forbidden')
    validator=Path(__file__).with_name('tennis_elo_rebuild.py')
    # Repeated Admin refreshes do not recompute an unchanged million-match source.
    try:
        prior=json.loads((output/'status.json').read_text())
        if (prior['as_of_exclusive']==cutoff and prior['builder_sha256']==sha(Path(__file__))
            and prior['validation_sha256']==sha(validator)
            and {p.relative_to(root).as_posix() for p in (root/'data/sackmann').glob('atp_matches_*.csv')}
                =={p for p in prior['source_hashes'] if p.startswith('data/sackmann/atp_matches_')}
            and prior['candidate_sha256']==sha(output/'candidate.json')
            and prior['history_file_sha256']==sha(output/'history.json.gz')
            and all(sha(root/p)==v for p,v in prior['source_hashes'].items())):
            prior['checked_at']=datetime.now(timezone.utc).isoformat();atomic(output/'status.json',prior)
            return prior
    except (OSError,ValueError,KeyError):pass
    rows,audit=source_history(root,include_adult_itf=True)
    eligible=[r for r in rows if r['available_date']<cutoff]
    if not eligible:raise ValueError('No completed results before cutoff')
    if len(rows)>2_000_000:raise ValueError('History exceeds reviewed bound')
    state=advance(empty_state(),eligible,cutoff)
    ratings=rating_rows(state)
    manifest={'version':VERSION,'as_of_exclusive':cutoff,'latest_available_result':state['through'],
              'history_matches':len(eligible),'history_hash':stream_hash(eligible),
              'source_hashes':audit['source_hashes'],
              'builder_sha256':sha(Path(__file__)),'validation_sha256':sha(validator),
              'method':{'initial':1500,'overall_k':22,'surface_k':22,'within_day':'same_pre_day_ratings',
                        'population':'adult ATP/Challenger/ITF; no juniors, doubles, Davis Cup or unfinished matches',
                        'surface_policy':'separate observed indoor; no hard-to-indoor substitution'},
              'by_rank':dict(Counter(str(r['rank']) for r in eligible)),
              'by_surface':dict(Counter(r['surface'] for r in eligible)),
              'audit':audit,'role':'research_source_only','live_writes':False,
              'historical_availability':'current corrected export; not original historical vintages'}
    if any(sha(root/p)!=v for p,v in audit['source_hashes'].items()):
        raise ValueError('Source changed during rating calculation')
    candidate={**manifest,'ratings':ratings};candidate['rating_hash']=stream_hash(ratings)
    candidate['generated_at']=datetime.now(timezone.utc).isoformat()
    output.mkdir(parents=True,exist_ok=True)
    # Fixed replaceable source files, not daily copies of a million-match archive.
    tmp=output/'history.json.gz.tmp'
    with gzip.open(tmp,'wt',encoding='utf8',compresslevel=1) as f:
        f.write('[')
        for i in range(0,len(eligible),1000):
            if i:f.write(',')
            f.write(json.dumps(eligible[i:i+1000],separators=(',',':'))[1:-1])
        f.write(']')
    tmp.replace(output/'history.json.gz')
    atomic(output/'candidate.json',candidate)
    focus={35804,65267,121190,128723}
    names={int(r['id']):r['name'] for r in __import__('tennis_elo_rebuild').read_csv(root/'data/oncourt/players_atp.csv') if r['id'].isdigit()}
    lookup={(r['player_id'],r['surface']):r for r in ratings}
    gaps=[{'player_id':p,'name':names.get(p,str(p)),
           'Overall':lookup.get((p,'Overall')),'I.hard':lookup.get((p,'I.hard'))} for p in sorted(focus)]
    for gap in gaps:
        gap['history_quality']={s:'NO_VALIDATED_HISTORY' if gap[s] is None else
            'THIN_HISTORY' if gap[s]['match_count']<10 else 'OBSERVED_HISTORY'
            for s in ('Overall','I.hard')}
    status={k:v for k,v in candidate.items() if k not in ('ratings','audit')}
    status.update(state='VALIDATED_RESEARCH_SOURCE',checked_at=candidate['generated_at'],
                  source_export_observed_at=datetime.fromtimestamp((root/'data/oncourt/games_atp.csv').stat().st_mtime,timezone.utc).isoformat(),
                  rating_rows=len(ratings),missing_player_followup=gaps,
                  live_source_state='PROVENANCE_UNVERIFIED',
                  thin_history_note='Fewer than 10 completed matches is a display warning, not a pricing or selection rule.',
                  promotion='never automatic; revised population is not the frozen v1 or a live refresh')
    if (datetime.now(timezone.utc).date()-datetime.fromisoformat(state['through']).date()).days>3:
        status['state']='STALE_RESULT_CUTOFF'
    status['candidate_sha256']=sha(output/'candidate.json');status['history_file_sha256']=sha(output/'history.json.gz')
    atomic(output/'status.json',status)
    return status

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--output',type=Path)
    a=p.parse_args();out=a.output or a.root/RELATIVE;out.mkdir(parents=True,exist_ok=True)
    # OS lock is released on exit/termination. Never remove another process's lock.
    handle=(out/'.lock').open('a+b')
    try:
        if os.name=='nt':
            import msvcrt
            handle.seek(0)
            if not handle.read(1):handle.write(b'0');handle.flush()
            handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl;fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        s=build(a.root,out,datetime.now(timezone.utc).date().isoformat())
        print(json.dumps({k:s[k] for k in ('state','history_matches','latest_available_result','rating_rows','missing_player_followup')}))
    except BlockingIOError:print('Native Elo source already running; skipped.')
    except Exception as e:
        atomic(out/'attempt.json',{'state':'FAILED','at':datetime.now(timezone.utc).isoformat(),'error_type':type(e).__name__,'live_writes':False})
        raise
    finally:handle.close()
if __name__=='__main__':main()
