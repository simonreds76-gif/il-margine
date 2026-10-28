"""One bounded Bet365 count-market read shared across the existing league scan."""
import copy
import gzip
import json
from datetime import datetime, timezone
from pathlib import Path
import requests
import moviodds_prices as source

GROUPS = {'50532':('Team Shots','Total Shots'), '10235':('Corners 2-Way','Corners Totals')}
RAW = Path(__file__).resolve().parents[1]/'data/team-shots/moviodds/latest.json.gz'
_board = None
_attempted = False


def capture_and_merge(payload, targets, *, now=None, get=None, raw_path=RAW):
    global _board, _attempted
    receipt = dict(source='moviodds_bet365',requests=0,errors=[],team_shots_quotes=0,corners_quotes=0)
    if not targets or not source.enabled('soccer'):
        receipt['status']='NO_TARGETS' if not targets else 'DISABLED'
        return payload, receipt
    try:
        if not _attempted:
            _attempted=True
            receipt['requests']=1
            _board=source.download('soccer',get,groups=GROUPS)
            raw_path=Path(raw_path);raw_path.parent.mkdir(parents=True,exist_ok=True)
            temp=raw_path.with_suffix('.tmp')
            temp.write_bytes(gzip.compress(json.dumps(_board).encode()))
            temp.replace(raw_path)
        if _board is None: raise ValueError('Unavailable source board')
        events,excluded=source.normalize(_board,'soccer',now or datetime.now(timezone.utc),
                                         targets=targets,days_ahead=7,groups=GROUPS)
        merged={str(e['id']):copy.deepcopy(e) for e in payload}
        for event in events:
            current=merged.setdefault(str(event['id']),{**event,'bookmakers':{}})
            # Replace only these exact Bet365 contracts; preserve GK/scorer data.
            existing=current.setdefault('bookmakers',{}).get('Bet365',[])
            names={'Total Shots Home','Total Shots Away','Corners Totals'}
            verified=event['bookmakers']['Bet365']
            current['bookmakers']['Bet365']=[m for m in existing if m.get('name') not in names]+verified
            current.setdefault('urls',{}).update(event.get('urls',{}))
            for market in verified:
                key='team_shots_quotes' if market['name'].startswith('Total Shots') else 'corners_quotes'
                receipt[key]+=2*len(market['odds'])
        receipt.update(status='OK' if events else 'NO_FRESH_MARKETS',excluded=excluded)
        return list(merged.values()),receipt
    except (requests.RequestException,OSError,ValueError,TypeError,KeyError) as exc:
        receipt.update(status='SOURCE_FAILED',errors=[type(exc).__name__])
        return payload,receipt
