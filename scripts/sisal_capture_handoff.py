"""Run the installed paper tracker immediately after prices; no alerts or requests."""
import json
import csv
import hashlib
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def run(root, quotes, *, runner=subprocess.run):
    root=Path(root);quotes=Path(quotes)
    folder=root/'data/tennis-props/shadow/sisal-5050-v1'
    if not (folder/'registration.json').exists():
        return {'state':'NOT_INSTALLED','reason':'No local paper registration; do not initialise on a capture-only host.'}
    required=['data/tennis-props/models/v3-atp-aces-live.txt',
              'data/tennis-props/shadow/aces-v3-projection-board.csv',
              'data/oncourt/today_atp.csv','scripts/tennis_sisal_5050.py']
    missing=[p for p in required if not (root/p).exists()]
    receipt={'checked_at':datetime.now(timezone.utc).isoformat(),'quotes':str(quotes),'no_alerts':True}
    if missing or not quotes.exists():
        receipt.update(state='MISSING_RUNTIME_INPUTS',missing=missing,quotes_exist=quotes.exists())
    else:
        try:
            history=root/'data/tennis-props/player-history-status.json'
            if history.exists():
                status=json.loads(history.read_text(encoding='utf-8'))
                board=root/'data/tennis-props/shadow/aces-v3-projection-board.csv'
                with board.open(encoding='utf-8-sig',newline='') as handle:
                    first=next(csv.DictReader(handle),{})
                stale=(first.get('history_as_of')!=status.get('as_of')
                    or first.get('history_fingerprint')!=status.get('output_hashes',{}).get('player-props-baseline.csv'))
                if stale:
                    generator=root/'scripts/tennis-props-v3-live.py'
                    registration=json.loads((folder/'registration.json').read_text(encoding='utf-8'))
                    expected=registration.get('artifacts',{}).get('scripts/tennis-props-v3-live.py')
                    if not generator.exists() or hashlib.sha256(generator.read_bytes()).hexdigest()!=expected:
                        raise ValueError('frozen_generator_mismatch')
                    refresh=runner([sys.executable,str(generator)],cwd=str(root),timeout=120)
                    if refresh.returncode!=0:raise ValueError('paper_board_refresh_failed')
                    receipt['paper_board_refreshed']=True
            result=runner([sys.executable,str(root/'scripts/tennis_sisal_5050.py'),
                           '--root',str(root),'--quotes',str(quotes)],cwd=str(root),timeout=240)
            receipt.update(state='COMPLETED' if result.returncode==0 else 'TRACKER_BLOCKED',exit_code=result.returncode)
        except subprocess.TimeoutExpired:
            receipt.update(state='TRACKER_TIMEOUT',timeout_seconds=240)
        except OSError as exc:
            receipt.update(state='TRACKER_LAUNCH_FAILED',error=type(exc).__name__)
        except (ValueError,TypeError,KeyError) as exc:
            receipt.update(state='PAPER_INPUT_REFRESH_BLOCKED',error=str(exc))
    target=folder/'handoff-status.json';temp=target.with_suffix('.tmp')
    temp.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');temp.replace(target)
    return receipt
