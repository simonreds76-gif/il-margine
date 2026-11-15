"""Generate one dated website projection from existing saved inputs only.

No installation, network calls, pricing, alerts or source-file edits. The existing
publisher can call this after its validated source extraction; do not run it per
website visitor. Preview validation does not establish scheduled publication.
"""
import argparse,json,hashlib
from pathlib import Path
from build_matchday_supplement import build,validate_supplement,read_csv
from build_matchday_recent import build_recent

def generate(source,history,schedule,as_of,previous=None):
    old=(previous or {}).get('supplement',history.get('matchdaySupplement'))
    names=[p['name'] for p in history['players']]
    supplement,audit=build(source,schedule,history['players'],as_of,old)
    validate_supplement(old,supplement)
    names += [p['name'] for v in supplement['pairs'].values() for p in v['players']]
    names += [r[k] for r in schedule for k in ('player1_name','player2_name') if r.get(k)]
    recent,ra=build_recent(source,names,as_of)
    receipt=json.loads((source/'extraction-status.json').read_text(encoding='utf-8'))
    if receipt.get('state')!='VERIFIED' or receipt.get('completed_at','')[:10]!=as_of:raise ValueError('Verified source date does not match projection date')
    hashes={}
    for name in ('players_atp.csv','tours_atp.csv','games_atp.csv','today_atp.csv'):
        value=hashlib.sha256((source/name).read_bytes()).hexdigest()
        if receipt.get('exports',{}).get(name,{}).get('sha256')!=value:raise ValueError('Source changed since its verified export: '+name)
        hashes[name]=value
    return {'schema':1,'asOf':as_of,'sourceUpdatedAt':receipt['completed_at'],'supplement':supplement,'recent':recent},{'h2h':audit,'recent':ra,'sourceHashes':hashes}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--oncourt',type=Path,required=True);p.add_argument('--history',type=Path,required=True);p.add_argument('--schedule',type=Path,required=True);p.add_argument('--previous',type=Path);p.add_argument('--as-of',required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--audit',type=Path,required=True);a=p.parse_args()
    schedule=json.loads(a.schedule.read_text(encoding='utf-8')) if a.schedule.suffix=='.json' else read_csv(a.schedule)
    data,audit=generate(a.oncourt,json.loads(a.history.read_text(encoding='utf-8')),schedule,a.as_of,json.loads(a.previous.read_text(encoding='utf-8')) if a.previous else None)
    for path,body in ((a.output,data),(a.audit,audit)):
        if a.oncourt.resolve() in path.resolve().parents:raise ValueError('Refusing to write into source directory')
        path.parent.mkdir(parents=True,exist_ok=True);temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(body,separators=(',',':'))+'\n',encoding='utf-8');temporary.replace(path)
    print(json.dumps({'players':len(data['recent']['players']),'pairs':len(data['supplement']['pairs']),'resultsThrough':data['recent']['through']}))
