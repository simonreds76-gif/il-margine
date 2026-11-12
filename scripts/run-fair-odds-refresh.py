"""Run the unchanged pricing engine and stamp its verified current-table refresh."""
import json,os,re,runpy,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
import requests

ROOT=Path(__file__).resolve().parents[1]

def refresh_count(output):
    computed=re.findall(r'Computed (\d+) fair odds rows',output)
    synced=re.findall(r'Synced daily_fair_odds: (\d+) current',output)
    if not computed or not synced or computed[-1]!=synced[-1]:
        raise RuntimeError('Cannot verify completed fair-odds sync; refresh timestamps retained')
    return int(synced[-1])

def stamp_current(base,headers,expected,stamp):
    url=base.rstrip('/')+'/rest/v1/daily_fair_odds'
    try:
        r=requests.get(url,headers=headers,params={'select':'*','limit':1000},timeout=30)
        if not r.ok:raise RuntimeError('Cannot verify current forecasts')
        rows=r.json()
        if len(rows)!=expected or len(rows)>=1000:raise RuntimeError('Current forecast count changed; timestamps retained')
        ids=[str(row['id']) for row in rows]
        if not ids:return
        # Only the ephemeral current forecast table. Issued ledgers and pricing
        # values never enter this PATCH; the pricing source remains byte-identical.
        for i in range(0,len(ids),100):
            r=requests.patch(url,headers={**headers,'Content-Type':'application/json'},params={'id':'in.('+','.join(ids[i:i+100])+')'},json={'computed_at':stamp},timeout=30)
            if not r.ok:raise RuntimeError('Forecast refresh timestamp write failed')
        r=requests.get(url,headers=headers,params={'select':'*','limit':1000},timeout=30)
        if not r.ok:raise RuntimeError('Forecast refresh timestamp verification failed')
        after={str(row['id']):row for row in r.json()}
        for row in rows:
            updated=after.get(str(row['id']),{})
            if any(updated.get(k)!=v for k,v in row.items() if k!='computed_at'):
                raise RuntimeError('Forecast values changed during timestamp verification')
            if datetime.fromisoformat(updated.get('computed_at','').replace('Z','+00:00'))!=datetime.fromisoformat(stamp):
                raise RuntimeError('Forecast timestamp readback mismatch')
    except requests.RequestException:
        raise RuntimeError('Forecast freshness verification request failed; credential details withheld') from None

def main():
    result=subprocess.run([sys.executable,str(ROOT/'scripts/oncourt-compute-fair-odds.py'),*sys.argv[1:]],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace')
    print(result.stdout,end='',flush=True)
    if result.stderr:print(result.stderr,end='',file=sys.stderr,flush=True)
    if result.returncode:return result.returncode
    if '--dry-run' in sys.argv:return 0
    expected=refresh_count(result.stdout)
    loader=runpy.run_path(str(ROOT/'scripts/oncourt-load-supabase.py'),run_name='freshness_access')
    stamp=datetime.now(timezone.utc).isoformat()
    stamp_current(loader['SUPABASE_URL'],loader['_headers'](),expected,stamp)
    print(f'Verified current forecast timestamps: {expected} rows at {stamp}; pricing values unchanged')
    return 0

if __name__=='__main__':raise SystemExit(main())
