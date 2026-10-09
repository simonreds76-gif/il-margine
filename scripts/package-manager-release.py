"""Compact the validated manager archive for static, client-side public research."""
import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FIELDS=['id','date','league','season','home','away','hg','ag','odds','basis','homeManager','awayManager']

def unpack(payload):
    if payload.get('format')!='manager-atlas-v1':raise ValueError('Unknown manager archive format')
    return {**{k:v for k,v in payload.items() if k not in ('format','rows','columns')},'fixtures':[dict(zip(FIELDS,row,strict=True)) for row in payload['rows']]}

def validate(data):
    ids={m['id'] for m in data['managers']}
    if len(ids)!=len(data['managers']) or not data['fixtures']:raise ValueError('Invalid manager registry/archive')
    seen=set()
    for f in data['fixtures']:
        if f['id'] in seen or f['homeManager']==f['awayManager'] or not {f['homeManager'],f['awayManager']}<=ids:raise ValueError('Duplicate fixture or invalid manager identity')
        seen.add(f['id'])
        if f['odds'] is None:
            if f['basis'] is not None:raise ValueError('Unpriced result cannot claim a price basis')
        else:
            if len(f['odds'])!=3 or any(type(p) not in (int,float) or not math.isfinite(p) or not 1<p<1001 for p in f['odds']):raise ValueError('Invalid three-way prices')
            if f['basis'] not in ('closing','last-pre-match','bet365-last-pre-match','bet365-closing','bet365-pre-match'):raise ValueError('Unknown price basis')
        if any(type(f[k]) is not int or not 0<=f[k]<=30 for k in ('hg','ag')):raise ValueError('Invalid final score')
    if data['through']!=max(f['date'] for f in data['fixtures']):raise ValueError('Wrong archive date')

def package(data, root=ROOT):
    validate(data)
    coverage={k:data.get('coverage',{}).get(k,{}) for k in ('exclusions','basis')}
    public={'format':'manager-atlas-v1','columns':FIELDS,'fromDate':data['fromDate'],'through':data['through'],'atlasVersion':data['atlasVersion'],'managers':data['managers'],'coverage':coverage,'rows':[[f[k] for k in FIELDS] for f in data['fixtures']]}
    raw=json.dumps(public,ensure_ascii=False,separators=(',',':')).encode()
    version=hashlib.sha256(raw).hexdigest()[:12]
    folder=root/'public/manager-atlas';folder.mkdir(parents=True,exist_ok=True)
    path=folder/f'index-{version}.json';path.write_bytes(raw)
    manifest={'version':version,'indexUrl':f'/manager-atlas/{path.name}','through':data['through'],'fromDate':data['fromDate'],'matches':len(data['fixtures']),'managers':len(data['managers']),'bytes':len(raw),'atlasVersion':data['atlasVersion']}
    mp=root/'src/data/manager-atlas-release.json'
    previous=json.loads(mp.read_text(encoding='utf-8')) if mp.exists() else {}
    # Repacking identical content must not manufacture a new sitemap date.
    manifest['contentUpdatedAt']=(previous.get('contentUpdatedAt') or '2026-09-27') if previous.get('version')==version else datetime.now(timezone.utc).isoformat()
    mp.parent.mkdir(parents=True,exist_ok=True);mp.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    return manifest,path.relative_to(root)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--archive',type=Path,required=True);args=parser.parse_args()
    print(json.dumps(package(json.loads(args.archive.read_text(encoding='utf-8')))[0]))
