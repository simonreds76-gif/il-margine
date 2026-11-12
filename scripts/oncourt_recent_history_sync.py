"""Bounded, append-only daily ATP result/stat transfer before fair-odds pricing."""
import csv
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import requests

KEY = ('winner_id','loser_id','tour_id','round_id')
STAT = tuple(side+'_'+field for side in ('w','l') for field in ('fs','fsof','w1s','w1sof','w2s','w2sof','rpw','rpwof'))

def rows(path):
    with path.open(encoding='utf-8-sig',newline='') as f:
        yield from csv.DictReader(f)

def key(row):
    return tuple(int(row[k]) for k in KEY)

def unique(rows):
    accepted, conflicts = {}, set()
    for row in rows:
        k=key(row)
        if k in accepted and accepted[k] != row:
            conflicts.add(k)
        accepted[k]=row
    return {k:r for k,r in accepted.items() if k not in conflicts}, sorted(conflicts)

def prepare(data_dir, today=None, days=21):
    today=today or date.today();cutoff=(today-timedelta(days=days)).isoformat()
    games=[]
    for r in rows(data_dir/'games_atp.csv'):
        if not cutoff <= r.get('date','') <= today.isoformat():continue
        k=key(r)
        if min(k)<=0 or k[0]==k[1] or not r.get('result'):continue
        games.append({**dict(zip(KEY,k)), 'result':r['result'], 'date':r['date']})
    games,game_conflicts=unique(games)
    stats=[]
    for r in rows(data_dir/'stat_atp.csv'):
        if key(r) not in games:continue
        stats.append({**dict(zip(KEY,key(r))),**{f:int(float(r[f])) if r.get(f) else 0 for f in STAT}})
    stats,stat_conflicts=unique(stats)
    if not games or len(games)>15000:raise RuntimeError('Recent history scope is empty or unexpectedly large')
    return games,stats,{'cutoff':cutoff,'through':max(r['date'] for r in games.values()),'game_conflicts':game_conflicts,'stat_conflicts':stat_conflicts}

class Store:
    def __init__(self,base,headers):self.base=base.rstrip('/')+'/rest/v1';self.headers=headers
    def read(self,table,params):
        result=[]
        for offset in range(0,100000,1000):
            try:
                r=requests.get(self.base+'/'+table,headers=self.headers,params={**params,'offset':offset,'limit':1000},timeout=30)
            except requests.RequestException:raise RuntimeError(f'{table} history verification request failed') from None
            if not r.ok:raise RuntimeError(f'{table} history verification HTTP {r.status_code}')
            page=r.json();result.extend(page)
            if len(page)<1000:return result
        raise RuntimeError('History verification exceeded bounded pagination')
    def append(self,table,data,on_conflict):
        for offset in range(0,len(data),500):
            try:
                r=requests.post(self.base+'/'+table,params={'on_conflict':on_conflict},headers={**self.headers,'Prefer':'resolution=ignore-duplicates,return=minimal'},json=data[offset:offset+500],timeout=45)
            except requests.RequestException:raise RuntimeError(f'{table} history append request failed') from None
            if not r.ok:raise RuntimeError(f'{table} history append HTTP {r.status_code}; existing records retained')

def fetch_contracts(store,table,expected):
    tours=sorted({k[2] for k in expected});found={}
    columns=','.join(KEY+ (('result','date') if table=='oncourt_games' else STAT))
    for i in range(0,len(tours),40):
        for row in store.read(table,{'select':columns,'tour_id':'in.('+','.join(map(str,tours[i:i+40]))+')','order':','.join(KEY)}):
            found[key(row)]=row
    return found

def append_contracts(store,table,expected):
    prior=fetch_contracts(store,table,expected)
    missing=[row for k,row in expected.items() if k not in prior]
    conflicts=[k for k,row in expected.items() if k in prior and any(prior[k].get(f)!=v for f,v in row.items())]
    store.append(table,missing,','.join(KEY))
    after=fetch_contracts(store,table,expected) if missing else prior
    if any(key(row) not in after or any(after[key(row)].get(f)!=v for f,v in row.items()) for row in missing):
        raise RuntimeError(f'{table} recent history readback failed')
    return {'expected':len(expected),'appended':len(missing),'verified':len(expected)-len(conflicts),'existing_conflicts':conflicts}

def sync_recent_history(data_dir,base,headers,*,today=None,store=None):
    data_dir=Path(data_dir);store=store or Store(base,headers)
    games,stats,report=prepare(data_dir,today)
    # Retain existing player records. Add only missing FK parents, including
    # yesterday's opponents who are no longer on today's schedule.
    ids=sorted({pid for k in games for pid in k[:2]});existing=set()
    for i in range(0,len(ids),150):
        existing.update(int(r['id']) for r in store.read('oncourt_players',{'select':'id','id':'in.('+','.join(map(str,ids[i:i+150]))+')','order':'id'}))
    need=set(ids)-existing
    parents=[{'id':int(p['id']),'name':p['name'],'birthdate':p.get('birthdate') or None,'country':p.get('country','')} for p in rows(data_dir/'players_atp.csv') if int(p['id']) in need]
    if {p['id'] for p in parents} != need:raise RuntimeError('Missing exact recent-result player identities')
    store.append('oncourt_players',parents,'id')
    report.update(checked_at=datetime.now(timezone.utc).isoformat(),players_added=len(parents),
                  games=append_contracts(store,'oncourt_games',games),stats=append_contracts(store,'oncourt_stat',stats),
                  historical_rows_overwritten=0,mode='append_only_recent_21_days')
    report['status']='VERIFIED' if not any((report['game_conflicts'],report['stat_conflicts'],report['games']['existing_conflicts'],report['stats']['existing_conflicts'])) else 'VERIFIED_ADDITIONS_WITH_RETAINED_CONFLICTS'
    target=data_dir/'recent-history-sync-status.json';tmp=target.with_suffix('.tmp')
    tmp.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');tmp.replace(target)
    print('Daily history sync: '+json.dumps({k:report[k] for k in ('status','cutoff','through','players_added','historical_rows_overwritten')}))
    for table in ('games','stats'):print(f"  {table}: {report[table]['appended']} added; {report[table]['verified']}/{report[table]['expected']} exact; {len(report[table]['existing_conflicts'])} existing conflicts preserved")
    return report
