"""Read only the latest saved Pinnacle schedule; never request bookmaker prices."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

def validate_rows(rows, stamp, now):
    captured = datetime.fromisoformat(stamp.replace('Z','+00:00'))
    age = (now-captured).total_seconds()
    if not -300 <= age < 86400 or not rows or len(rows) >= 250:
        raise ValueError('Stale or incomplete saved schedule')
    fields=('league','league_name','player1_name','player2_name','match_date','kickoff_iso','captured_at')
    for row in rows:
        if row.get('captured_at') != stamp or any(not isinstance(row.get(k),str) for k in fields):
            raise ValueError('Mixed or invalid saved schedule')
        if row['league'] not in ('ATP','Challenger'):
            raise ValueError('Unexpected competition')
    return rows

def latest_saved_schedule(runtime_root, now=None):
    now=now or datetime.now(timezone.utc)
    wanted=('NEXT_PUBLIC_SUPABASE_URL','SUPABASE_SERVICE_ROLE_KEY')
    settings={k:os.environ[k] for k in wanted if os.environ.get(k)}
    for name in ('.env.local','env.local'):
        path=Path(runtime_root)/name
        if path.exists():
            for line in path.read_text(encoding='utf-8').splitlines():
                key,sep,value=line.partition('=')
                if sep and key.strip() in wanted:
                    settings.setdefault(key.strip(),value.strip().strip('"').strip("'"))
    base=settings.get(wanted[0],'').rstrip('/')
    key=settings.get(wanted[1],'')
    parsed=urlparse(base)
    if parsed.scheme!='https' or not (parsed.hostname or '').endswith('.supabase.co') or not key:
        return [],{'status':'unavailable','reason':'configuration_unavailable'}
    def read(params):
        request=Request(base+'/rest/v1/bookmaker_odds_history?'+urlencode(params),
            headers={'apikey':key,'Authorization':'Bearer '+key})
        with urlopen(request,timeout=15) as response:
            raw=response.read(500001)
        if len(raw)>500000:raise ValueError('Saved schedule exceeds bound')
        return json.loads(raw)
    common={'bookmaker':'eq.Pinnacle','league':'in.(ATP,Challenger)'}
    try:
        latest=read({**common,'select':'captured_at','order':'captured_at.desc','limit':'1'})
        stamp=latest[0]['captured_at']
        rows=read({**common,'captured_at':'eq.'+stamp,
            'select':'captured_at,league,league_name,player1_name,player2_name,match_date,kickoff_iso','limit':'250'})
        validate_rows(rows,stamp,now)
        return rows,{'status':'loaded','rows':len(rows),'capturedAt':stamp}
    except Exception as exc:
        # No exception URLs, request headers, environment values or credential data.
        return [],{'status':'unavailable','reason':type(exc).__name__}
