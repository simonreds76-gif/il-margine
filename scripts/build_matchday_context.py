"""Generate one dated website projection from existing saved inputs only.

No installation, network calls, pricing, alerts or source-file edits. The existing
publisher can call this after its validated source extraction; do not run it per
website visitor. Preview validation does not establish scheduled publication.
"""
import argparse,json,hashlib
from pathlib import Path
from build_matchday_supplement import build,validate_supplement,read_csv
from build_matchday_recent import build_recent
from build_matchday_results import build_results
from build_matchday_supplement import normal, ALIASES
from collections import defaultdict

def generate(source,history,schedule,as_of,previous=None):
    old=(previous or {}).get('supplement',history.get('matchdaySupplement'))
    names=[] # Recent form is needed for the captured schedule, not all 600 priced profiles.
    supplement,audit=build(source,schedule,history['players'],as_of,old)
    validate_supplement(old,supplement)

    names += [r[k] for r in schedule for k in ('player1_name','player2_name') if r.get(k)]
    recent,ra=build_recent(source,names,as_of)
    receipt=json.loads((source/'extraction-status.json').read_text(encoding='utf-8'))
    if receipt.get('state')!='VERIFIED' or receipt.get('completed_at','')[:10]!=as_of:raise ValueError('Verified source date does not match projection date')
    hashes={}
    for name in ('players_atp.csv','tours_atp.csv','games_atp.csv','today_atp.csv'):
        value=hashlib.sha256((source/name).read_bytes()).hexdigest()
        if receipt.get('exports',{}).get(name,{}).get('sha256')!=value:raise ValueError('Source changed since its verified export: '+name)
        hashes[name]=value
    results,results_audit=build_results(source,as_of)
    # Project the newly validated archive for current named pairs. Keep exact
    # archived prices/identities; never reconstruct or reprice old meetings.
    people=defaultdict(list)
    for i,p in enumerate(history['players']): people[normal(p['name'])].append(i)
    app_aliases={'jaume munar':'vbt-10698','pedro martinez':'vbt-12525','taylor fritz':'vbt-9023','yunchaokete bu':'vbt-25003','igor marcondes':'vbt-5490','felipe meligeni rodrigues alves':'vbt-16420'}
    by_id={p['id']:normal(p['name']) for p in history['players']}
    def key(name):
        raw=normal(name)
        if raw in app_aliases and app_aliases[raw] in by_id:return by_id[app_aliases[raw]]
        return normal(ALIASES.get(raw,(None,name))[1])
    for m in history.get('matches',[])+history.get('results',[]):
        if not all(type(m.get(k)) is int and 0<=m[k]<len(history['players']) for k in ('p1','p2')):
            raise ValueError('Unverified archive player index contract')
    pairs={}
    for row in schedule:
        names=[key(row.get(f'player{i}_name','')) for i in (1,2)]
        ids=[people[n] for n in names]
        if len(set(names))!=2 or any(len(v)!=1 for v in ids):continue
        ids=[v[0] for v in ids]; names=sorted(names)
        ids=[people[n][0] for n in names]
        matches=[]
        for m in history.get('matches',[])+history.get('results',[]):
            if {m['p1'],m['p2']} != set(ids) or m['date'] >= as_of:continue
            side=m['p1']==ids[0]
            matches.append({'date':m['date'],'winner':m['winner'] if side else 1-m['winner'],
              'odds':[m.get('o1'),m.get('o2')] if side else [m.get('o2'),m.get('o1')],
              'surface':m['surface'],'score':m['score'],'event':m['event'],
              'competition':m.get('competition'),'priceBasis':m.get('priceBasis')})
        pairs['|'.join(names)]={'names':names,'checkedThrough':as_of,'matches':matches}
    data={'schema':1,'asOf':as_of,'sourceUpdatedAt':receipt['completed_at'],'historyVersion':history.get('version',history.get('atlasVersion')),
          'supplement':supplement,'recent':recent,'results':results,'pairHistory':pairs}
    # Sliding-window projection: retain previously published observations in
    # the overlapping window, quarantine corrections rather than rewrite them.
    preserved=[]
    before={m['id']:m for m in (previous or {}).get('results',{}).get('matches',[])}
    after={m['id']:m for m in results['matches']}
    for mid,record in before.items():
        clean={k:v for k,v in record.items() if k!='verification'}
        if results['from'] <= record['date'] < results['before'] and after.get(mid)!=clean:
            preserved.append(mid);after[mid]={**clean,'verification':'retained_pending_review'}
    results['matches']=sorted(after.values(),key=lambda m:(m['date'],m['event'],m['id']),reverse=True)
    results['through']=max((m['date'] for m in results['matches']),default=None)
    results['omitted']=sum(results_audit['excluded'].values())+results_audit['conflicts']
    results['retained']=len(preserved)
    for name,player in recent['players'].items():
        before_recent={m['id']:m for m in (previous or {}).get('recent',{}).get('players',{}).get(name,{}).get('matches',[])}
        player['matches']=[{**before_recent[m['id']],'verification':'retained_pending_review'} if m['id'] in before_recent and {k:v for k,v in before_recent[m['id']].items() if k!='verification'}!=m else m for m in player['matches']]
    data['version']=hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest()[:24]
    if len(json.dumps(data,separators=(',',':')).encode())>1_800_000:raise ValueError('Matchday cache snapshot exceeds 1.8MB budget; prior snapshot retained')
    return data,{'retainedResults':preserved,'h2h':audit,'recent':ra,'results':results_audit,'sourceHashes':hashes,'version':data['version'],'pairedHistories':len(pairs)}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--oncourt',type=Path,required=True);p.add_argument('--history',type=Path,required=True);p.add_argument('--schedule',type=Path,required=True);p.add_argument('--previous',type=Path);p.add_argument('--as-of',required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--audit',type=Path,required=True);a=p.parse_args()
    schedule=json.loads(a.schedule.read_text(encoding='utf-8')) if a.schedule.suffix=='.json' else read_csv(a.schedule)
    data,audit=generate(a.oncourt,json.loads(a.history.read_text(encoding='utf-8')),schedule,a.as_of,json.loads(a.previous.read_text(encoding='utf-8')) if a.previous else None)
    for path,body in ((a.output,data),(a.audit,audit)):
        if a.oncourt.resolve() in path.resolve().parents:raise ValueError('Refusing to write into source directory')
        path.parent.mkdir(parents=True,exist_ok=True);temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(body,separators=(',',':'))+'\n',encoding='utf-8');temporary.replace(path)
    print(json.dumps({'players':len(data['recent']['players']),'pairs':len(data['supplement']['pairs']),'resultsThrough':data['recent']['through']}))
