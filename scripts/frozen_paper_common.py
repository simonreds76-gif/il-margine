"""Private forward-only comparisons. No network, alerts or live-model writes."""
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from statistics import mean, stdev

def utc(value):
    try:
        dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except (TypeError, ValueError):
        return None

def read(path, default=None):
    return json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else ({} if default is None else default)

def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()

def atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False)+'\n', encoding='utf-8')
    tmp.replace(path)

def immutable(path, value):
    if path.exists():
        if read(path) != value:
            raise ValueError('immutable evidence conflict: '+path.name)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as f:
        json.dump(value, f, sort_keys=True, allow_nan=False)

def hashes(root, files):
    # Canonical newline hashing gives identical registrations on Windows/Linux.
    return {p: sha256((root/p).read_text(encoding='utf-8-sig').encode()).hexdigest() for p in files}

def register(root, folder, protocol, files, clock):
    if not clock.tzinfo:
        raise ValueError('registration requires UTC time')
    path = folder/'registration.json'
    if path.exists():
        return verify(root, folder, files)
    cfg = read(root/protocol)
    assert cfg['actual_stake'] == 0 and cfg['alerts'] is False and cfg['automatic_promotion'] is False
    value = dict(registered_at=clock.isoformat(), protocol=cfg, fingerprints=hashes(root, files),
                 actual_stake=0, historical_replay_included=False)
    immutable(path, value)
    atomic(folder/'capture-status.json', dict(state='CONNECTED_AWAITING_FIRST_RUN', checked_at=clock.isoformat()))
    return value

def verify(root, folder, files):
    reg = read(folder/'registration.json')
    if not reg or reg['fingerprints'] != hashes(root, files):
        raise ValueError('frozen comparison changed; manual review required')
    return reg

def preserve_outcomes(folder, proposed, clock):
    """Final grades never silently change. Conflicts are retained separately."""
    old = read(folder/'outcomes.json'); result = dict(old)
    for key, value in proposed.items():
        previous = old.get(key, {})
        if previous.get('status') in ('settled', 'excluded'):
            # Repeated observations can have a later observation time/provenance.
            fields = ('status', 'side1_outcome', 'actual', 'score', 'reason')
            if value.get('status') != 'pending' and any(previous.get(k) != value.get(k) for k in fields):
                evidence = dict(id=key, retained=previous, proposed=value)
                p = folder/'conflicts'/(digest(evidence)+'.json')
                if not p.exists():
                    immutable(p, dict(first_observed_at=clock.isoformat(), **evidence))
            continue
        result[key] = value
    if old and old != result:
        immutable(folder/'outcome-history'/(digest(old)+'.json'), old)
    atomic(folder/'outcomes.json', result)
    return result

def interval(values):
    n = len(values)
    if n < 2:
        return dict(n=n, mean=mean(values) if n else None, ci95=None)
    # Descriptive fixture-cluster normal interval, not a sequential significance test.
    center = mean(values); half = 1.96*stdev(values)/math.sqrt(n)
    return dict(n=n, mean=center, ci95=[center-half, center+half])

def summary(records, outcomes, arms, clock):
    display=[]
    for r in records:
        o=outcomes.get(r['id'], dict(status='pending')); selections={}
        for arm, s in r['selections'].items():
            profit=None; y=o.get('side1_outcome')
            if o['status']=='settled' and s['selected']:
                profit=0.0 if y==0 else s['odds']-1 if y==(1 if s['side']==1 else -1) else -1.0
            selections[arm]={**s, 'profit':profit}
        display.append({**r['display'], 'id':r['id'], 'fixture_key':r['fixture_key'],
                        'captured_at':r['captured_at'], 'arms':selections, **o})
    stats={}; samples={}
    for arm in arms:
        stats[arm]={}
        markets={'total_games','game_handicap'} if 'MJ1_S' in arms else {'team_shots'}
        for market in ['all']+sorted(markets|{r['market'] for r in display}):
            rows=[r for r in display if market=='all' or r['market']==market]
            bets=[r for r in rows if r['arms'][arm]['selected']]
            settled=[r for r in bets if r['status']=='settled']; counts=Counter(r['status'] for r in bets)
            clusters=defaultdict(list); pnl=defaultdict(float)
            for r in rows:
                if r['status']!='settled' or r['side1_outcome']==0: continue
                s=r['arms'][arm]; p=s['probability'] if s['side']==1 else 1-s['probability']
                y=int(r['side1_outcome']==1); mp=(1/r['odds'][0])/(1/r['odds'][0]+1/r['odds'][1])
                ll=lambda p:-math.log(max(1e-12, p if y else 1-p))
                clusters[r['fixture_key']].append(dict(brier=(p-y)**2,log_loss=ll(p),
                    market_brier=(mp-y)**2,market_log_loss=ll(mp),mean_probability=p,observed_rate=y))
            cal={k:mean(mean(x[k] for x in items) for items in clusters.values()) if clusters else None
                 for k in ('brier','log_loss','market_brier','market_log_loss','mean_probability','observed_rate')}
            cal.update(n=len(clusters),contracts=sum(map(len,clusters.values())),weighting='equal fixture, then equal contract')
            deltas={fx:mean(x['log_loss']-x['market_log_loss'] for x in items) for fx,items in clusters.items()}
            cal['paired_minus_market']=interval(list(deltas.values()))
            if 'MJ1_S' in arms:
                editions=defaultdict(list)
                for fx,v in deltas.items():editions[fx.split('|')[0]].append(v)
                cal['edition_cluster_minus_market']=interval([mean(v) for v in editions.values()])
            for r in settled: pnl[r['fixture_key']]+=r['arms'][arm]['profit']
            profits=[r['arms'][arm]['profit'] for r in settled]; profit=math.fsum(profits)
            stakes=Counter(r['fixture_key'] for r in settled)
            roi=profit/len(settled) if settled else None
            deviations=[pnl[fx]-roi*stakes[fx] for fx in stakes] if roi is not None else []
            roi_half=1.96*math.sqrt(len(deviations)/(len(deviations)-1)*sum(d*d for d in deviations))/len(settled) if len(deviations)>1 else None
            stats[arm][market]=dict(settled=len(settled),wins=sum(p>0 for p in profits),losses=sum(p<0 for p in profits),
                pushes=sum(p==0 for p in profits),stake=len(settled),profit=profit,roi_pct=100*profit/len(settled) if settled else None,
                pending=counts['pending'],excluded=counts['excluded'],quarantined=counts['quarantined'],
                overdue=sum(r['status']=='pending' and clock-utc(r['start'])>timedelta(hours=48) for r in bets),
                calibration=cal,roi_ci95_pct=[100*(roi-roi_half),100*(roi+roi_half)] if roi_half is not None else None,
                fixture_profit_interval=interval(list(pnl.values())))
            samples[arm,market]={fx:mean(x['log_loss'] for x in items) for fx,items in clusters.items()}
    baseline=arms[0]; differences={}
    for arm in arms[1:]:
        a,b=samples.get((arm,'all'),{}),samples.get((baseline,'all'),{})
        differences[arm+'_minus_'+baseline]=interval([a[k]-b[k] for k in a.keys() & b.keys()])
    return dict(contracts=len(display),fixtures=len({r['fixture_key'] for r in display}),
        settled_fixtures=len({r['fixture_key'] for r in display if r['status']=='settled'}),arms=stats,
        paired_log_loss_differences=differences,
        uncertainty='Descriptive 95% normal intervals across independent fixtures; small samples are inconclusive.',
        records=sorted(display,key=lambda r:(r['start'],r['id']),reverse=True))

def weekly_text(report):
    if not report:return ''
    lines=[report['name']+' | frozen forward comparison | zero real stake, no alerts',
           f"Started {report['registered_at'][:10]}; {report['fixtures']} fixtures / {report['contracts']} contracts; {report['settled_fixtures']} settled fixtures."]
    for arm, groups in report['arms'].items():
        s=groups['all'];c=s['calibration'];roi=f"{s['roi_pct']:+.2f}%" if s['roi_pct'] is not None else 'pending'
        cal=f"Brier {c['brier']:.4f}, log loss {c['log_loss']:.4f} ({c['n']} fixtures)" if c['n'] else 'calibration pending'
        lines.append(f"{report['protocol']['labels'][arm]}: {s['wins']}W/{s['losses']}L/{s['pushes']}P; {s['profit']:+.2f}u/{s['stake']}u; ROI {roi}; {s['pending']} pending, {s['overdue']} overdue. {cal}.")
    lines.append('Capture: '+report.get('capture',{}).get('state','unknown')+'. Exploratory; no automatic promotion.')
    lines.append(report['protocol'].get('historical_status',''))
    return '\n'.join(lines)

def read_report(root,relative):
    """Overlay current health even if the last valid report had to be retained."""
    folder=root/relative
    try:r=read(folder/'report.json')
    except (ValueError,OSError):return {}
    if not r:return {}
    try:health=read(folder/'capture-status.json',r.get('capture',{}))
    except (ValueError,OSError):health=dict(state='UNREADABLE',reason='comparison health needs review')
    return {**r,'capture':health}
