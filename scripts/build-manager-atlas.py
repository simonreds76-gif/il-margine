"""Build a private manager research preview from fixture-level labels and Atlas prices.

No network, current-coach inference, approximate name matching or invented odds.
Unmatched/conflicting fixtures are excluded and listed in the private audit.
"""
import argparse
import csv
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODES = {'GB1':'premier-league','ES1':'la-liga','IT1':'serie-a','L1':'bundesliga','FR1':'ligue-1'}
NAME_ALIASES = {'Zdenek Zeman':'Zdeněk Zeman','Bruno Genesio':'Bruno Génésio','Ivan Juric':'Ivan Jurić'}
def norm(text):
    return re.sub('[^a-z0-9]', '', unicodedata.normalize('NFKD',text).encode('ascii','ignore').decode().lower())

def join(atlas, source, aliases):
    lookup=defaultdict(list)
    for m in atlas['fixtures']:
        lookup[(atlas['leagues'][m[2]],m[1],atlas['teams'][m[4]],atlas['teams'][m[5]])].append(m)
    known={norm(t):t for t in atlas['teams']}
    def team(name,league):
        return known.get(norm(name)) or aliases.get(league,{}).get(norm(name))
    result=[]; rejected=[]; seen=set(); manager_names={}; counts=Counter()
    grouped=defaultdict(list)
    for r in source:
        if r['competition_id'] not in CODES:continue
        league=CODES[r['competition_id']]
        key=(league,r['date'][:10],team(r['home_club_name'],league),team(r['away_club_name'],league))
        grouped[key].append(r)
    for key,rows in grouped.items():
        reason=None;r=rows[0];matches=lookup.get(key,[])
        if len(rows)!=1:reason='ambiguous_manager_fixture'
        elif None in key:reason='unmapped_team'
        elif len(matches)!=1:reason='missing_or_ambiguous_atlas_fixture'
        elif not all(r[k].strip() and r[k].strip() not in ['Unknown','-','?'] for k in ['home_club_manager_name','away_club_manager_name']):reason='missing_manager'
        elif any(norm(r[k])=='michel' for k in ['home_club_manager_name','away_club_manager_name']):reason='ambiguous_manager_identity'
        else:
            m=matches[0]
            if (m[6],m[7])!=(int(r['home_club_goals']),int(r['away_club_goals'])):reason='score_conflict'
            elif not all(isinstance(p,(int,float)) and 1<p<1001 for p in m[8:11]):reason='missing_prices'
            elif m[11] not in (1,2):reason='unknown_price_basis'
            elif m[0] in seen:reason='duplicate_fixture'
        if reason:
            counts[reason]+=len(rows);rejected.append({'game':r['game_id'],'reason':reason,'teams':[r['home_club_name'],r['away_club_name']]});continue
        names=[NAME_ALIASES.get(r[k].strip(),r[k].strip()) for k in ['home_club_manager_name','away_club_manager_name']]
        ids=[]
        for name in names:
            ident=norm(name)
            if ident in manager_names and manager_names[ident]!=name:
                raise ValueError(f'Manager name collision requires review: {name}')
            manager_names[ident]=name;ids.append(ident)
        if ids[0]==ids[1]:raise ValueError('Same manager on both teams')
        seen.add(m[0]);counts['joined']+=1
        result.append({'id':m[0],'date':m[1],'league':key[0],'season':atlas['seasons'][m[3]],
                       'home':key[2],'away':key[3],'hg':m[6],'ag':m[7],'odds':m[8:11],
                       'basis':'closing' if m[11]==1 else 'last-pre-match',
                       'homeManager':ids[0],'awayManager':ids[1]})
    return {'schema':1,'managers':[{'id':k,'name':v} for k,v in sorted(manager_names.items(),key=lambda item:item[1])],
            'fixtures':sorted(result,key=lambda r:(r['date'],r['id']))}, {'counts':dict(counts),'excluded':rejected}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    output=args.output.resolve()
    if 'public' in output.parts:raise ValueError('Research preview must stay outside public/')
    release=json.loads((ROOT/'src/data/football-atlas-release.json').read_text())
    path=ROOT/'public'/release['indexUrl'].lstrip('/')
    aliases=json.loads((ROOT/'scripts/config/football-atlas-clubs.json').read_text(encoding='utf-8'))
    extra=json.loads((ROOT/'scripts/config/manager-atlas-clubs.json').read_text(encoding='utf-8'))
    for league,mapping in extra.items():aliases.setdefault(league,{}).update({norm(k):v for k,v in mapping.items()})
    with args.source.open(encoding='utf-8-sig',newline='') as handle:data,audit=join(json.loads(path.read_text(encoding='utf-8')),list(csv.DictReader(handle)),aliases)
    data.update(atlasVersion=release['version'],through=max(m['date'] for m in data['fixtures']),fromDate=min(m['date'] for m in data['fixtures']))
    audit.update(sourceSha256=hashlib.sha256(args.source.read_bytes()).hexdigest(),atlasVersion=release['version'],publicationReady=False)
    output.mkdir(parents=True,exist_ok=True)
    (output/'data.json').write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    (output/'audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'matches':len(data['fixtures']),'managers':len(data['managers']),'through':data['through'],'counts':audit['counts']}))
if __name__=='__main__':main()
