"""One-off read-only hosting check: two endpoints, no retries or credentials."""
import json
from pathlib import Path
import requests

cfg=json.loads(Path('config/paddy-public-client-probe.json').read_text())
rows=[]
for label,url,params in [
    ('website','https://www.paddypower.com/football',{}),
    ('public_competition_endpoint',cfg['endpoints']['competitionPage'],
     {'_ak':cfg['appKey'],'eventTypeId':1,'competitionId':81,'includeLayout':'true',
      'includePrices':'false','exchangeLocale':'en_GB','currencyCode':'GBP','betexRegion':'GBR',
      'capiJurisdiction':'intl','language':'en','regionCode':'UK','countryCode':'GB','loggedIn':'false'})]:
    try:
        r=requests.get(url,params=params,timeout=15)
        item={'endpoint':label,'status':r.status_code,'content_type':r.headers.get('content-type'),
              'content_bytes':len(r.content),'server':r.headers.get('server')}
        try:
            body=r.json();item['json_keys']=list(body)[:8]
            item['events']=len(body.get('attachments',{}).get('events',{}))
        except (ValueError,AttributeError,TypeError):
            text=r.text.lower()
            item['markers']=[s for s in ('access denied','forbidden','temporarily unavailable','country','cloudflare','captcha','request blocked') if s in text]
        rows.append(item)
    except requests.RequestException as e:
        rows.append({'endpoint':label,'error':type(e).__name__})
print(json.dumps(rows,indent=2))
Path('paddy-cloud-probe.json').write_text(json.dumps(rows,indent=2))
