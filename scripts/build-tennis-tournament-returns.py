from pathlib import Path
import csv,json,re,hashlib,unicodedata,collections,datetime

# Explicit offline inputs only. Never run from a request or install in a model pipeline.
C=W=O=None
def norm(s):return ''.join(c for c in unicodedata.normalize('NFKD',s.replace('ø','o')).lower() if c.isalnum())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return csv.DictReader(p.open(encoding='utf-8-sig',newline=''))
def complete(score,needed):
 if re.search(r'ret|w/o|walk|def|abn|cancel|\[',score,re.I):return False
 s=re.sub(r'\(\d+\)','',score).strip()
 if not re.fullmatch(r'\d+-\d+(?:\s+\d+-\d+)*',s):return False
 wins=[0,0]
 for token in s.split():
  a,b=map(int,token.split('-'));hi,lo=max(a,b),min(a,b)
  if max(wins)>=needed or not ((hi==6 and lo<=4) or (hi==7 and lo in [5,6]) or (hi>7 and hi-lo==2)):return False
  wins[a<b]+=1
 return wins[0]==needed and wins[1]<needed
def edition_completion(finals, needed):
 # Round 12 is the verified source's singles final. A year/date alone cannot
 # establish completion; ambiguous or unfinished final records stay unverified.
 if len(finals)==1:
  r=finals[0]
  terminal = re.fullmatch(r'(?:\d+-\d+(?:\(\d+\))?\s+)+ret\.?|w/o|walkover',r['result'].strip(),re.I)
  if complete(r['result'],needed) or terminal:
   return {'state':'completed','completedAt':r['date'],'evidence':{'tourId':r['tour_id'],'roundId':r['round_id'],'winnerId':r['winner_id'],'loserId':r['loser_id'],'score':r['result']}}
 return {'state':'unverified','completedAt':None}

def official_completion(evidence, edition, finals, asof):
 # An official title-award notice may establish completion when a walkover
 # final has no source match row. Never insert it into the match/ROI ledger.
 if finals or edition['completion']['state']=='completed':return edition['completion']
 matches=[e for e in evidence if e['tourId']==edition['id'] and e['year']==edition['year'] and e['event']==edition['event'] and e['surface']==edition['surface'] and e['completedAt']<=asof[:10]]
 if len(matches)!=1:return edition['completion']
 e=matches[0]
 return {'state':'completed','completedAt':e['completedAt'],'evidence':e}

def profit(rows):
 eligible=[r for r in rows if r['o1']!=r['o2']]
 def side(fav):
  wins=0;net=0
  for r in eligible:
   p=0 if (r['o1']<r['o2'])==fav else 1
   won=r['winner']==r['p'+str(p+1)]
   wins+=won;net+=(r['o'+str(p+1)]-1) if won else -1
  n=len(eligible)
  return {'wins':wins,'losses':n-wins,'stake':n,'profit':round(net,6),'roi':round(100*net/n,6) if n else None}
 return {'paired':len(rows),'pickems':len(rows)-len(eligible),'bettable':len(eligible),'favourite':side(True),'underdog':side(False),'priceMix':dict(collections.Counter(r['priceBasis'] for r in rows))}

# Reviewed name-only aliases within the same city/surface. No ATP/Challenger merge.
GROUPS=[
 ('atp-finals','ATP Finals',['Nitto ATP Finals - Turin'],['Finals','ATP Finals','Turin']),
 ('queens',"Queen’s",['cinch Championships - London','HSBC Championships - London'],['London','Queens','Queen’s','Queens Club']),
 ('paris-masters','Paris Masters',['Rolex Paris Masters - Paris'],['Paris','Paris Masters']),
 ('dallas','Dallas',['Dallas Open - Dallas'],['Dallas']),
 ('rotterdam','Rotterdam',['ABN AMRO Open - Rotterdam','ABN AMRO World Tennis Tournament - Rotterdam'],['Rotterdam']),
 ('stockholm','Stockholm',['Stockholm Open - Stockholm','BNP Paribas Nordic Open - Stockholm'],['Stockholm']),
 ('stuttgart','Stuttgart',['Mercedes Cup - Stuttgart','Boss Open - Stuttgart'],['Stuttgart']),
 ('halle','Halle',['Noventi Open - Halle','Terra Wortmann Open - Halle'],['Halle']),
 ('montpellier','Montpellier',['Open Sud de France - Montpellier','Open Occitanie - Montpellier'],['Montpellier']),
 ('eastbourne','Eastbourne',['Nature Valley International - Eastbourne','Viking International - Eastbourne','Rothesay International - Eastbourne','Lexus Eastbourne Open - Eastbourne'],['Eastbourne']),
 ('tokyo','Tokyo',['Rakuten Japan Open - Tokyo','Japan Open Tennis Championships - Tokyo'],['Tokyo']),
 ('santiago','Santiago',['Chile Dove Men+Care Open - Santiago','Movistar Chile Open - Santiago','BCI Seguros Chile Open - Santiago'],['Santiago']),
 ('los-cabos','Los Cabos',['Abierto Mexicano de Tenis Mifel - Los Cabos','Abierto de Tenis Mifel - Los Cabos','Mifel Tennis Open - Los Cabos'],['Los Cabos']),
 ('hamburg','Hamburg',['Hamburg European Open - Hamburg','Hamburg Open - Hamburg'],['Hamburg']),
 ('gstaad','Gstaad',['Swiss Open - Gstaad','EFG Swiss Open - Gstaad'],['Gstaad']),
 ('cincinnati','Cincinnati',['Western & Southern Open - Cincinnati','Cincinnati Open - Cincinnati'],['Cincinnati']),
 ('toronto','Toronto',['Rogers Cup - Toronto','National Bank Open - Toronto'],['Toronto']),
 ('atlanta','Atlanta',['Truist Atlanta Open - Atlanta','Atlanta Open - Atlanta'],['Atlanta']),
 ('bucharest','Bucharest',['Bucharest Open - Bucharest','Tiriac Open - Bucharest'],['Bucharest'])]
BREAKS={'paris-masters':{'year':2025,'note':'Paris changed venue in 2025. Earlier Bercy editions are shown separately.','source':'https://www.atptour.com/en/news/rolex-paris-masters-venue-move'},'dallas':{'year':2025,'note':'Dallas moved to Frisco in 2025. Earlier editions are shown separately.','source':'https://www.atptour.com/en/news/dallas-open-venue-change-november-2023'}}

def main():
 lines=(C/'preview/real-data.mjs').read_text(encoding='utf-8').splitlines()
 data={k:json.loads(next(x[len('export const '+k+'='):-1] for x in lines if x.startswith('export const '+k+'='))) for k in ['metadata','players','matches']}
 receipt=json.loads((C/'oncourt/extraction-status.json').read_text(encoding='utf-8'))
 assert receipt['state']=='VERIFIED'
 for f in ['games_atp.csv','players_atp.csv','tours_atp.csv']:assert sha(C/'oncourt'/f)==receipt['exports'][f]['sha256'],f
 rel=json.loads((W/'src/data/return-atlas-release.json').read_text(encoding='utf-8'))
 public=json.loads((W/'public'/rel['indexUrl'].lstrip('/')).read_text(encoding='utf-8'))
 published={r[0]:(r[1],public['players'][r[2]]['id'],public['players'][r[3]]['id'],r[4],r[5],r[6]) for r in public['matches']}
 assert len(published)==len(data['matches']) and len(published)>0
 for m in data['matches']:assert published[m['id']]==(m['date'],m['p1'],m['p2'],m['o1'],m['o2'],0 if m['winner']==m['p1'] else 1),m['id']
 completion_evidence=json.loads((W/'src/data/tennis-tournament-completion-evidence.json').read_text(encoding='utf-8'))['editions']
 asof=rel['checkedAt']; year=int(asof[:4]);surfaces={'1':'outdoor-hard','2':'clay','3':'indoor-hard','5':'grass'}
 tours={r['id']:r for r in read(C/'oncourt/tours_atp.csv') if r['date']>='2020-12-15' and r['rank'] in ['2','3','4'] and not re.search(r'united cup|atp cup|davis|laver|next.?gen|olympic|exhibition|juniors',r['name'],re.I)}
 all_players={r['id']:r['name'] for r in read(C/'oncourt/players_atp.csv')}
 players={i:n for i,n in all_players.items() if '/' not in n}
 canonical={p['id']:p['name'] for p in data['players']}
 finals=collections.defaultdict(list)
 games={};lookup=collections.defaultdict(list);bad=collections.Counter();excluded=collections.defaultdict(collections.Counter)
 for r in read(C/'oncourt/games_atp.csv'):
  if not ('2021-01-01'<=r['date']<asof) or r['tour_id'] not in tours or int(r['round_id'])<4:continue
  t=tours[r['tour_id']]
  if any('/' in all_players.get(r[k],'') for k in ['winner_id','loser_id']):excluded[r['tour_id']]['doubles']+=1;continue
  if r['winner_id'] not in players or r['loser_id'] not in players:excluded[r['tour_id']]['unresolvedIdentity']+=1;continue
  if r['round_id']=='12':finals[r['tour_id']].append(r)
  if not complete(r['result'],3 if t['rank']=='4' else 2):excluded[r['tour_id']]['incompleteOrRetired']+=1;continue
  key=(r['date'],r['tour_id'],r['round_id'],r['winner_id'],r['loser_id'])
  if key in games:raise ValueError('Duplicate source fixture')
  games[key]=r
  lookup[(norm(t['name']),r['round_id'],tuple(sorted([norm(players[r['winner_id']]),norm(players[r['loser_id']])])) )].append((key,r))
 prices={};unmatched=[]
 for m in data['matches']:
  k=(norm(m['event']),str(m['round']),tuple(sorted([norm(canonical[m['p1']]),norm(canonical[m['p2']])])) )
  matches=[(key,r) for key,r in lookup.get(k,[]) if abs((datetime.date.fromisoformat(r['date'])-datetime.date.fromisoformat(m['date'])).days)<=1 and norm(players[r['winner_id']])==norm(canonical[m['winner']]) and r['result']==m['score'] and surfaces.get(tours[r['tour_id']]['court_id'])==m['surface']]
  if len(matches)!=1:unmatched.append({'id':m['id'],'count':len(matches)});continue
  key,r=matches[0]
  if key in prices:raise ValueError('Duplicate accepted priced fixture')
  prices[key]=m
 if unmatched:raise ValueError('Accepted-record parity join failed: '+str(unmatched[:5]))
 ids=collections.defaultdict(list)
 for key,r in games.items():ids[r['tour_id']].append(key)
 mapping={alias:(ident,name,aliases,feed) for ident,name,aliases,feed in GROUPS for alias in aliases}
 families={}
 for tid,keys in ids.items():
  t=tours[tid];surf=surfaces.get(t['court_id']);yr=int(t['date'][:4]);ev=t['name'];city=ev.rsplit(' - ',1)[-1]
  ident,name,aliases,feed=mapping.get(ev,(re.sub(r'[^a-z0-9]+','-',norm(ev)),ev,[ev],[]))
  identity=ident+'--'+surf
  fam=families.setdefault(identity,{'id':identity,'familyId':ident,'name':name,'city':city,'surface':surf,'tour':'ATP','aliases':aliases,'feedLabels':feed,'notes':[], 'editions':[]})
  relevant=[prices[k] for k in keys if k in prices]
  counts=profit(relevant);n=len(keys)
  edition={'id':tid,'year':yr,'event':ev,'fromDate':min(games[k]['date'] for k in keys),'throughDate':max(games[k]['date'] for k in keys),'completed':n,'noPrice':n-len(relevant),'coveragePct':100*len(relevant)/n, 'excluded':dict(excluded[tid]),'surface':surf,**counts}
  # Hold ambiguous year-boundary source editions; never guess a season with a date shift.
  if t['date'][5:]>='12-25' or edition['throughDate'][:4]!=str(yr):
   edition['seasonReviewRequired']=True
  edition['completion']=edition_completion(finals[tid],3 if t['rank']=='4' else 2)
  edition['completion']=official_completion(completion_evidence,edition,finals[tid],asof)
  edition['_rows']=relevant
  fam['editions'].append(edition)
 for fam in families.values():
  fam['editions'].sort(key=lambda r:(r['year'],r['fromDate']))
  counts=collections.Counter(e['year'] for e in fam['editions'])
  for e in fam['editions']:
   e['status']='current' if e['year']==year else 'included';e['excludedReason']=None
   if e['coveragePct']<80:e.update(status='excluded',excludedReason='Paired-price coverage below 80%')
   if counts[e['year']]>1:e.update(status='excluded',excludedReason='Multiple editions in the same year; identity requires review')
   if e['year']==2021 or any('opening' in label.lower() for label in e['priceMix']):e.update(status='opening',excludedReason='Opening odds, shown separately')
   if fam['familyId'] in BREAKS and e['year']<BREAKS[fam['familyId']]['year']:e.update(status='previous-venue',excludedReason='Earlier venue, shown separately')
   if e.get('seasonReviewRequired'):e.update(status='review',excludedReason='Year-boundary edition needs verified season and completion')
   if e['excluded'].get('unresolvedIdentity'):e.update(status='review',excludedReason='Unresolved identities prevent verified coverage')
  if fam['familyId'] in BREAKS:fam['notes'].append(BREAKS[fam['familyId']]['note']);fam['venueEvidence']=BREAKS[fam['familyId']]['source']
  fam['notes'].append('Ball choice and court pace are not verified across editions.')
  fam['windows']={}
  old=[e for e in fam['editions'] if e['year']<year]
  current=[e for e in fam['editions'] if e['year']==year]
  for window in (3,5):
   chosen=old[-window:];included=[e for e in chosen if e['status']=='included'];rows=[r for e in included for r in e['_rows']]
   assert not any('opening' in r['priceBasis'].lower() for r in rows), 'Opening price in pooled history'
   pool=profit(rows);pool['completed']=sum(e['completed'] for e in included);pool['noPrice']=sum(e['noPrice'] for e in included);pool['coveragePct']=100*pool['paired']/pool['completed'] if pool['completed'] else None
   pool['excluded']=dict(sum((collections.Counter(e['excluded']) for e in included),collections.Counter()))
   bands=[]
   for label,lo,hi in [('Heavy favourite',1,1.3),('Clear favourite',1.3,1.6),('Close match',1.6,1001)]:
    band=profit([r for r in rows if lo<=min(r['o1'],r['o2'])<hi]);band.update(label=label,lower=lo,upper=hi,showRoi=band['bettable']>=30);bands.append(band)
   fam['windows'][str(window)]={'requested':window,'years':[e['year'] for e in included],'selectedYears':[e['year'] for e in chosen],'pool':pool,'editions':[{k:v for k,v in e.items() if k!='_rows'} for e in chosen],'current':[{k:v for k,v in e.items() if k!='_rows'} for e in current],'bands':bands}
  for e in fam['editions']:e.pop('_rows')
 out={'schema':1,'asOf':asof,'coverageUpdatedAt':receipt['completed_at'],'through':rel['through'],'priceBookmaker':'Pinnacle','scope':'ATP main draw only','archiveVersion':rel['version'],'families':sorted(families.values(),key=lambda f:f['name'])}
 target=W/'src/data/tennis-tournament-returns.json';target.write_text(json.dumps(out,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
 audit={'sourceHashes':{str(p):sha(p) for p in [C/'preview/real-data.mjs',C/'oncourt/extraction-status.json',C/'oncourt/games_atp.csv',C/'oncourt/players_atp.csv',C/'oncourt/tours_atp.csv',W/'src/data/return-atlas-release.json']},'outputSha256':sha(target),'acceptedPrices':len(prices),'completedDenominator':len(games),'families':len(families),'joinFailures':unmatched,'data':out}
 (O/'audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({'acceptedPrices':len(prices),'completedDenominator':len(games),'families':len(families),'bytes':target.stat().st_size,'examples':[{ 'name':f['name'],'window3':{k:f['windows']['3']['pool'][k] for k in ['paired','completed','bettable','favourite','underdog']}} for f in families.values() if f['familyId'] in ['atp-finals','queens','paris-masters']]}))

if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser(description='Build a descriptive tournament ROI snapshot from a verified accepted archive; no model changes.')
 p.add_argument('--candidate',required=True);p.add_argument('--site-root',required=True);p.add_argument('--audit-dir',required=True)
 a=p.parse_args();C=Path(a.candidate);W=Path(a.site_root);O=Path(a.audit_dir);O.mkdir(parents=True,exist_ok=True);main()
