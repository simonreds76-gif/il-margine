"""Build a private, static preview from the audited fixture acquisition. No provider calls."""
import argparse, hashlib, json, unicodedata, re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DISPLAY={'Man City':'Manchester City','Man United':'Manchester United',"Nott'm Forest":'Nottingham Forest','Wolves':'Wolverhampton Wanderers','Newcastle':'Newcastle United','Tottenham':'Tottenham Hotspur','West Ham':'West Ham United','Brighton':'Brighton & Hove Albion','Leeds':'Leeds United','Paris SG':'Paris Saint-Germain','St Etienne':'Saint-Étienne','Ath Madrid':'Atlético Madrid','Ath Bilbao':'Athletic Club','Betis':'Real Betis','Sociedad':'Real Sociedad','La Coruna':'Deportivo La Coruña','Sp Gijon':'Sporting Gijón','Celta':'Celta Vigo','Espanol':'Espanyol',"M'gladbach":'Borussia Mönchengladbach','Dortmund':'Borussia Dortmund','Leverkusen':'Bayer Leverkusen','Ein Frankfurt':'Eintracht Frankfurt','Hamburg':'Hamburger SV','FC Koln':'FC Köln','Mainz':'Mainz 05','Stuttgart':'VfB Stuttgart','Vallecano':'Rayo Vallecano','Santander':'Racing Santander','Inter':'Inter Milan','Milan':'AC Milan','Spal':'SPAL','QPR':'Queens Park Rangers','Ajaccio GFCO':'Gazélec Ajaccio','Hull':'Hull City','Cardiff':'Cardiff City','Coventry':'Coventry City','Huddersfield':'Huddersfield Town','Luton':'Luton Town','Stoke':'Stoke City','Swansea':'Swansea City','West Brom':'West Bromwich Albion','Wigan':'Wigan Athletic','Leicester':'Leicester City','Norwich':'Norwich City'}
def norm(s): return re.sub(r'[^a-z0-9]', '', unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode().lower())
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,required=True);args=parser.parse_args()
    fixtures=json.loads(args.source.read_text(encoding='utf-8'))
    status=json.loads(args.source.with_name('acquisition-status.json').read_text())
    ids=set()
    for m in fixtures:
        assert m['id'] not in ids, 'Duplicate fixture';ids.add(m['id'])
        assert m['home']!=m['away'] and m['hg']>=0 and m['ag']>=0
        if m['odds']: assert len(m['odds'])==3 and all(1<float(p)<1001 for p in m['odds'])
    teams=sorted({m[k] for m in fixtures for k in ['home','away']});ti={s:i for i,s in enumerate(teams)}
    leagues=['premier-league','serie-a','la-liga','bundesliga','ligue-1']
    seasons=sorted({m['season'] for m in fixtures})
    logos={}
    manifest=json.loads((ROOT/'data/goalscorer/team-logo-map.json').read_text())
    for league in manifest['leagues'].values():
        for name,club in league['teams'].items():
            for alias in [name,club.get('fotmob_name',''),club.get('fotmob_short_name',''),club.get('team_key','')]:
                if alias and club.get('logo_path') and (ROOT/'public'/club['logo_path'].lstrip('/')).is_file():logos[norm(alias)]=club['logo_path']
    for club in json.loads((ROOT/'data/team-logos/europe.json').read_text())['teams']:
        for alias in club['aliases']:
            if (ROOT/'public'/club['logo_path'].lstrip('/')).is_file():logos[norm(alias)]=club['logo_path']
    for path in (ROOT/'public/team-logos').rglob('*.png'):logos.setdefault(norm(path.stem),'/'+path.relative_to(ROOT/'public').as_posix())
    aliases={'Man City':'Manchester City','Man United':'Manchester United','Nott\'m Forest':'Nottingham Forest','Wolves':'Wolverhampton Wanderers','Newcastle':'Newcastle United','Tottenham':'Tottenham Hotspur','West Ham':'West Ham United','Paris SG':'Paris Saint-Germain','St Etienne':'Saint-Etienne','Ath Madrid':'Atletico Madrid','Ath Bilbao':'Athletic Club','Betis':'Real Betis','Sociedad':'Real Sociedad','La Coruna':'Deportivo La Coruna','Sp Gijon':'Sporting Gijon','Celta':'Celta Vigo','Espanol':'Espanyol','Bayern Munich':'Bayern Munich','M\'gladbach':'Borussia Monchengladbach','Dortmund':'Borussia Dortmund','Leverkusen':'Bayer Leverkusen','Ein Frankfurt':'Eintracht Frankfurt','Hamburg':'Hamburger SV','FC Koln':'FC Cologne','Mainz':'Mainz 05','Inter':'Inter Milan','Milan':'AC Milan','Spal':'SPAL'}
    aliases.update({'Stuttgart':'VfB Stuttgart','Vallecano':'Rayo Vallecano','St Etienne':'Saint Etienne','Santander':'Racing Santander','Heidenheim':'Heidenheimer'})
    crests={team:logos.get(norm(aliases.get(team,team))) or logos.get(norm(team)) for team in teams}
    extra=ROOT/'src/data/football-atlas-crests.json'
    if extra.exists():
        for team,entry in json.loads(extra.read_text()).items():
            if (ROOT/'public'/entry['path'].lstrip('/')).is_file():crests[team]=entry['path']
    compact={'teams':teams,'crests':crests,'leagues':leagues,'seasons':seasons,'fixtures':[[m['id'],m['date'],leagues.index(m['league']),seasons.index(m['season']),ti[m['home']],ti[m['away']],m['hg'],m['ag'],*(m['odds'] or [None,None,None]),1 if m['basis']=='closing' else 2 if m['basis']=='last-pre-match' else 0] for m in fixtures]}
    compact['teams']=[DISPLAY.get(t,t) for t in teams]
    assert len(set(compact['teams']))==len(teams),'Display-name collision'
    compact['crests']={DISPLAY.get(t,t):url for t,url in crests.items()}
    payload=json.dumps(compact,separators=(',',':'),ensure_ascii=False).encode();version=hashlib.sha256(payload).hexdigest()[:12]
    dest=ROOT/'public/football-atlas';dest.mkdir(exist_ok=True)
    (dest/f'index-{version}.json').write_bytes(payload)
    priced=[m for m in fixtures if m['odds']]
    coverage={}
    for league in leagues:
        coverage[league]={s:{'eligible':sum(m['league']==league and m['season']==s for m in fixtures),'priced':sum(m['league']==league and m['season']==s for m in priced)} for s in seasons}
    release={'version':version,'indexUrl':f'/football-atlas/index-{version}.json','checkedAt':status['checkedAt'],'through':max(m['date'] for m in priced),'from':min(m['date'] for m in priced),'fixtures':len(fixtures),'matches':len(priced),'teams':len(teams),'seasons':seasons,'coverage':coverage,'acquisitionComplete':status['complete'],'bytes':len(payload),'previewOnly':True}
    (ROOT/'src/data/football-atlas-release.json').write_text(json.dumps(release,indent=2)+'\n',encoding='utf-8')
    missing=[t for t,p in crests.items() if not p]
    args.source.with_name('missing-crests.json').write_text(json.dumps(missing,indent=2))
    print(json.dumps({k:v for k,v in release.items() if k!='coverage'}));print('Missing crests:',missing)
if __name__=='__main__':main()
