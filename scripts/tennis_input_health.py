"""Read-only tennis input observer. Never prices, selects, settles or sends alerts.

The main runner brackets pricing with this independent observer. These are
observed input vintages, not an atomic trace of the model's database reads.
An absent Elo refresh contract stays UNVERIFIED; timestamps are never repaired.
"""
from __future__ import annotations
import argparse, csv, gzip, hashlib, json, math, os, uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlencode

RELATIVE = Path('data/tennis-input-health')
MAX_CAPTURE_BYTES = 128 * 1024 * 1024
MAX_CAPTURE_FILES = 10000

class CaptureCapacityError(ValueError):
    pass
MODEL_FILES = ('scripts/oncourt-compute-fair-odds.py', 'scripts/live_model_v2.py',
               'scripts/matchup_model.py', 'scripts/tennis_source_contract.py',
               'scripts/tennis_pricing_context.py', 'src/lib/tennis_prob.py')
SOURCE_FILES = ('data/oncourt/player-profile-contract.json',
                'data/tennis-context-live/status.json',
                'data/tennis-props/player-history-status.json',
                'data/tennis-props/player-props-baseline.csv',
                'data/oncourt/today_atp.csv','data/oncourt/tours_atp.csv','data/oncourt/courts.csv')

def read(path, default=None):
    try:
        return json.loads(path.read_text(encoding='utf-8-sig'))
    except FileNotFoundError:
        return {} if default is None else default

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False,
                                    separators=(',', ':')).encode()).hexdigest()

def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None

def utc(value):
    try:
        stamp = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return stamp.astimezone(timezone.utc) if stamp.tzinfo else None
    except (TypeError, ValueError):
        return None

def atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    temp.write_text(json.dumps(value, sort_keys=True, allow_nan=False), encoding='utf-8')
    temp.replace(path)

def immutable(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open('x', encoding='utf-8') as handle:
            json.dump(value, handle, sort_keys=True, allow_nan=False)
    except FileExistsError:
        if read(path) != value:
            raise ValueError('immutable_capture_conflict')

def read_capture(folder, phase):
    path=folder/(phase+'.json.gz')
    if path.exists():
        with gzip.open(path,'rt',encoding='utf-8') as handle:return json.load(handle)
    return read(folder/(phase+'.json'))

def immutable_capture(output, run_id, phase, value):
    folder=output/'runs';path=folder/run_id/(phase+'.json.gz')
    if path.exists():
        if read_capture(path.parent,phase)!=value: raise ValueError('immutable_capture_conflict')
        return
    raw=gzip.compress(json.dumps(value,sort_keys=True,allow_nan=False).encode(),mtime=0)
    files=list(folder.glob('*/*.json*')) if folder.exists() else []
    if len(files)>=MAX_CAPTURE_FILES or sum(p.stat().st_size for p in files)+len(raw)>MAX_CAPTURE_BYTES:
        raise CaptureCapacityError('Observer evidence budget reached; compact or archive manually without deleting records')
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as handle:handle.write(raw)

def fingerprint(rows):
    values = sorted((int(r['player_id']), str(r['surface']), float(r['elo'])) for r in rows)
    if len({(p,s) for p,s,e in values}) != len(values):
        raise ValueError('duplicate_elo_keys')
    if any(not math.isfinite(e) or e <= 0 for p,s,e in values):
        raise ValueError('invalid_elo')
    return digest(values)

def age_state(stamp, now, maximum_days):
    value = utc(stamp)
    if value is None:
        return 'MISSING'
    if value > now + timedelta(minutes=5):
        return 'INVALID_FUTURE'
    return 'CURRENT' if now-value <= timedelta(days=maximum_days) else 'STALE'

def fixture_key(row):
    return ':'.join(str(row.get(k, '')) for k in ('tour_id','round_id','player1_id','player2_id'))

def evaluate(fixtures, elo, profiles, metadata, now):
    """Per-fixture coverage. Elo presence is explicitly not proof of freshness."""
    lookup = {(int(r['player_id']), str(r['surface'])):r for r in elo}
    fp = fingerprint(elo)
    profile_keys = {(int(r['player_id']),str(r['surface'])) for r in profiles}
    rows = []
    for f in fixtures:
        missing, profile_missing, selected = [], [], []
        for side in ('player1_id','player2_id'):
            for surface in ('Overall',f['surface']):
                key = (int(f[side]),surface)
                if key not in lookup: missing.append([*key])
                else: selected.append(lookup[key])
            if (int(f[side]),f['surface']) not in profile_keys:
                profile_missing.append(int(f[side]))
        rows.append({'fixture_key':fixture_key(f), 'surface':f['surface'],
                     'elo_state':'MISSING' if missing else 'UNVERIFIED',
                     'missing_elo_keys':missing, 'missing_v2_profile_ids':profile_missing,
                     'elo_content_sha256':fingerprint(selected),
                     'forecast_computed_at':f.get('computed_at'),
                     'forecast_age_state':age_state(f.get('computed_at'),now,1) if f.get('computed_at') else 'NOT_PRICED',
                     'note':'Missing rows expose existing fallbacks; no selection policy changed.'})
    timestamps = sorted(str(r.get('updated_at')) for r in elo if r.get('updated_at'))
    checks = {'weekly_profiles':age_state(metadata.get('profile_completed_at'),now,9),
              'context':age_state(metadata.get('context_generated_at'),now,1),
              'player_count_history':age_state(metadata.get('history_generated_at'),now,2)}
    if metadata.get('context_status') != 'READY': checks['context']='INVALID'
    if metadata.get('history_status') != 'CURRENT': checks['player_count_history']='INVALID'
    gaps = sum(bool(r['missing_elo_keys']) for r in rows)
    return {'version':'tennis-input-health-v1', 'checked_at':now.isoformat(),
            'status':'MISSING' if gaps or not fixtures else 'ELO_LINEAGE_UNVERIFIED',
            'reason':'elo_refresh_writer_and_cutoff_not_verified',
            'fixture_count':len(fixtures), 'elo_rows':len(elo), 'fixtures_with_missing_elo':gaps,
            'fixtures_with_missing_v2_profile':sum(bool(r['missing_v2_profile_ids']) for r in rows),
            'elo_content_sha256':fp, 'elo_oldest_row_timestamp':timestamps[0] if timestamps else None,
            'elo_newest_row_timestamp':timestamps[-1] if timestamps else None,
            'zero_match_count_rows':sum(r.get('match_count')==0 for r in elo),
            'timestamp_is_verified_refresh_cutoff':False, 'elo_coverage':'MISSING' if gaps else 'COMPLETE', 'elo_lineage':'UNVERIFIED', 'checks':checks,
            'pricing_and_stakes_changed':False, 'fixtures':rows,
            'capture_note':'Bracketing observations, not an atomic trace of engine reads. No historical vintage reconstructed.',
            'retention':'Lossless gzip; at most 128 MiB / 10000 captures. On capacity limit health warns; pricing continues. No automatic deletion.',
            'affected_paths':['ATP match odds','derived handicaps','expected games','general aces/DF','V3/Count opportunities','Hardcourt Scout'],
            'interpretation':'Fresh quotes do not certify rating freshness. Old timestamps alone do not prove unchanged values.'}

def make_getter(root):
    env = dict(os.environ)
    for name in ('.env.local','env.local'):
        path=root/name
        if path.exists():
            for line in path.read_text(encoding='utf-8-sig').splitlines():
                if '=' in line and not line.lstrip().startswith('#'):
                    k,v=line.split('=',1)
                    if k.strip() in ('NEXT_PUBLIC_SUPABASE_URL','SUPABASE_SERVICE_ROLE_KEY'):
                        env.setdefault(k.strip(),v.strip().strip('"').strip("'"))
    base=env['NEXT_PUBLIC_SUPABASE_URL'].rstrip('/')+'/rest/v1/'
    key=env['SUPABASE_SERVICE_ROLE_KEY']
    def get(table, params):
        request=Request(base+table+'?'+urlencode(params),
                        headers={'apikey':key,'Authorization':'Bearer '+key}, method='GET')
        with urlopen(request,timeout=8) as response: result=json.load(response)
        if not isinstance(result,list) or len(result)>=1000:
            raise ValueError('observer_query_bound_exceeded_or_invalid')
        return result
    return get

def observe(root, get, now):
    fixtures=get('daily_fair_odds',{'select':'*','order':'tour_id.asc,round_id.asc,player1_id.asc,player2_id.asc','limit':1000})
    # Also inspect upcoming export candidates which do not yet have a price row.
    # This is coverage observation, not a second eligibility/selection engine.
    required={fixture_key(f):f for f in fixtures}
    scheduled, ignored = scheduled_candidates(root)
    for row in scheduled: required.setdefault(fixture_key(row),row)
    ids=sorted({int(f[k]) for f in required.values() for k in ('player1_id','player2_id')})
    if len(ids)>300: raise ValueError('observer_player_bound_exceeded')
    elo, profiles=[],[]
    for i in range(0,len(ids),100):
        filt={'player_id':'in.('+','.join(map(str,ids[i:i+100]))+')','limit':1000}
        elo+=get('player_elo',{'select':'player_id,surface,elo,match_count,updated_at',**filt})
        profiles+=get('player_surface_stats_v2',{'select':'player_id,surface,match_count,updated_at',**filt})
    context=read(root/'data/tennis-context-live/status.json')
    history=read(root/'data/tennis-props/player-history-status.json')
    contract=root/'data/oncourt/player-profile-contract.json'
    metadata={'profile_completed_at':datetime.fromtimestamp(contract.stat().st_mtime,timezone.utc).isoformat() if contract.exists() else None,
              'context_generated_at':context.get('generated_at'),'context_status':context.get('status'),
              'history_generated_at':history.get('generated_at'),'history_status':history.get('state'),
              'history_feature_cutoff':history.get('feature_cutoff')}
    status=evaluate(list(required.values()),elo,profiles,metadata,now)
    status['stored_forecast_count']=len(fixtures)
    status['unpriced_export_candidates']=len(required)-len(fixtures)
    stored_keys={fixture_key(f) for f in fixtures}
    status['stored_forecasts_missing_elo']=sum(bool(f['missing_elo_keys']) for f in status['fixtures'] if f['fixture_key'] in stored_keys)
    status['unpriced_candidates_missing_elo']=sum(bool(f['missing_elo_keys']) for f in status['fixtures'] if f['fixture_key'] not in stored_keys)
    status['scheduled_export_exclusions']=ignored
    return {'observed_at':now.isoformat(), 'status':status, 'forecasts':fixtures,
            'elo_rows':elo, 'profile_rows':profiles, 'metadata':metadata,
            'file_hashes':{p:file_hash(root/p) for p in MODEL_FILES+SOURCE_FILES},
            'capture_semantics':'Observed tables, not an atomic trace of model reads; never retroactively labelled prospective.',
            'raw_expected_games':None, 'raw_expected_games_status':'NOT_READ_BY_BRACKETING_OBSERVER_SEE_VERSIONED_ML_COMPONENTS'}

def scheduled_candidates(root):
    import re
    folder=root/'data/oncourt'
    if not all((folder/n).exists() for n in ('today_atp.csv','tours_atp.csv','courts.csv','players_atp.csv')): return [],{'export_missing':1}
    def csv_rows(n):
        with (folder/n).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
    tours={r['id']:r for r in csv_rows('tours_atp.csv')}
    # Import the same canonical court mapping already used by the pricing engine.
    from tennis_source_contract import court_surfaces
    courts=court_surfaces(folder/'courts.csv')
    names={r['id']:str(r.get('name','')).strip() for r in csv_rows('players_atp.csv')}
    result=[]; ignored={'self_pair_draw_placeholder':0,'invalid_player_id':0,
                        'identified_doubles':0,'named_draw_placeholder':0}
    placeholders={'unknown player','bye','qualifier','lucky loser','tbd','tba'}
    for f in csv_rows('today_atp.csv'):
        if str(f.get('result','')).strip(): continue
        if any(not str(f.get(k,'')).isdigit() or int(f[k])<=0 for k in ('player1_id','player2_id')):
            ignored['invalid_player_id']+=1;continue
        if f['player1_id']==f['player2_id']:
            ignored['self_pair_draw_placeholder']+=1;continue
        t=tours.get(f.get('tour_id'),{}); name=str(t.get('name','')).upper()
        if re.search(r'\b[MW]\d{1,2}\b',name) or 'ITF' in name or 'FUTURES' in name: continue
        rank=int(t['rank']) if str(t.get('rank','')).isdigit() else 99
        eligible=rank<=3 or any(n in name for n in ('CHALLENGER','ATP','MASTERS','GRAND SLAM','WIMBLEDON','AUSTRALIAN OPEN','FRENCH OPEN','US OPEN'))
        if not eligible: continue
        participants=[names.get(f[k],'') for k in ('player1_id','player2_id')]
        if any('/' in n or '&' in n for n in participants):
            ignored['identified_doubles']+=1;continue
        if any(n.casefold() in placeholders for n in participants):
            ignored['named_draw_placeholder']+=1;continue
        # An absent identity remains an auditable gap; never silently discard it.
        if eligible: result.append({**f,'surface':courts.get(t.get('court_id'),'N/A')})
    return result,ignored

def summary(status):
    return {k:v for k,v in status.items() if k!='fixtures'}

def load_status(root):
    try:
        value=read(root/RELATIVE/'status.json')
        if not isinstance(value,dict): raise ValueError('invalid_status')
        return value
    except (OSError,ValueError):
        return {'status':'CHECK_FAILED'}

def text(status):
    state=status.get('status','UNAVAILABLE')
    freshness=age_state(status.get('checked_at'),datetime.now(timezone.utc),2)
    if freshness!='CURRENT': state=f'{state}; health check {freshness.lower()}'
    bad = ', '.join(k+': '+v for k,v in status.get('checks',{}).items() if v!='CURRENT')
    return (f"Tennis input health: {state}. Elo refresh lineage unverified; "
            f"Stored forecasts missing Elo: {status.get('stored_forecasts_missing_elo','?')}/{status.get('stored_forecast_count','?')}; "
            f"eligible unpriced singles missing Elo: {status.get('unpriced_candidates_missing_elo','?')}/{status.get('unpriced_export_candidates','?')}. "
            f"Excluded doubles/draw placeholders: {status.get('scheduled_export_exclusions',{}).get('identified_doubles',0)}/{status.get('scheduled_export_exclusions',{}).get('named_draw_placeholder',0)}. "
            +(f'Other checks: {bad}. ' if bad else '')+
            'Fresh odds do not certify input freshness. Existing pricing unchanged.')

def unchanged_after_results(root, previous, data):
    """Conservative cross-day check on exact native IDs in the local fixture export.

    Does not infer fresh ratings from a changed set of players, a file mtime or
    a new table timestamp. Same-day results cannot be timed here and are omitted.
    """
    start=utc(previous.get('observed_at')); end=utc(data['observed_at'])
    if not start or not end or start.date()>=end.date(): return []
    old={(int(r['player_id']),r['surface']):float(r['elo']) for r in previous.get('elo_rows',[])}
    new={(int(r['player_id']),r['surface']):float(r['elo']) for r in data['elo_rows']}
    path=root/'data/oncourt/today_atp.csv'
    if not path.exists(): return []
    import re
    played={}
    with path.open(encoding='utf-8-sig',newline='') as handle:
        for row in csv.DictReader(handle):
            day=str(row.get('date',''))[:10]; score=str(row.get('result','')).strip()
            if not start.date().isoformat()<day<end.date().isoformat(): continue
            # Completed normal sets only; retirement, walkover and unclear scores excluded.
            if not re.fullmatch(r'\d+-\d+(?:\(\d+\))?(?: \d+-\d+(?:\(\d+\))?){1,4}',score): continue
            for key in ('player1_id','player2_id'):
                if str(row.get(key,'')).isdigit(): played.setdefault(int(row[key]),[]).append(fixture_key(row))
    return [{'player_id':p,'surface':s,'result_fixtures':sorted(set(played[p]))}
            for p,s in sorted(set(old)&set(new)) if p in played and old[p,s]==new[p,s]]

def record(root, output, phase, run_id, get=None, now=None):
    now=now or datetime.now(timezone.utc)
    if not run_id or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in run_id):
        raise ValueError('invalid_run_id')
    data=observe(root,get or make_getter(root),now)
    status=data['status']; status['run_id']=run_id; status['phase']=phase
    pointer=read(output/'previous-observation.json')
    previous_id=pointer.get('run_id',''); previous_phase=pointer.get('phase','')
    previous={}
    if previous_id and all(c in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in previous_id) and previous_phase in ('after','standalone'):
        previous=read_capture(output/'runs'/previous_id,previous_phase)
    unchanged=unchanged_after_results(root,previous,data)
    status['unchanged_ratings_after_completed_results']=unchanged
    status['unchanged_content_interpretation']='Observation only; original Elo writer schedule is unknown. No automatic policy action.'
    if phase=='after':
        before=read_capture(output/'runs'/run_id,'before')
        same=bool(before) and (before.get('file_hashes')==data['file_hashes']) and before['status']['elo_content_sha256']==status['elo_content_sha256']
        data['bracket_inputs_unchanged']=same
        start=utc(before.get('observed_at'))
        data['new_forecast_keys']=[fixture_key(f) for f in data['forecasts']
            if start and utc(f.get('computed_at')) and start<=utc(f['computed_at'])<=now]
        data['forecast_linkage']='bracket_observed_not_atomic' if same else 'unverified_or_input_change'
        status['new_forecasts_in_run']=len(data['new_forecast_keys'])
        status['bracket_inputs_unchanged']=same
    # Each run is immutable; only the current summary is replaced.
    immutable_capture(output,run_id,phase,data)
    atomic(output/'status.json',status)
    if phase in ('after','standalone'):
        atomic(output/'previous-observation.json',{'run_id':run_id,'phase':phase})
    print(text(status))
    return status

def safe_observe(root, phase, run_id):
    """Nonfatal boundary: observer failure cannot rerun or suppress selections."""
    output=root/RELATIVE
    try:
        return record(root,output,phase,run_id)
    except Exception as exc:
        # Do not log raw request exceptions: their strings can contain URLs.
        status={'status':'CAPACITY_REVIEW_REQUIRED' if isinstance(exc,CaptureCapacityError) else 'CHECK_FAILED','checked_at':datetime.now(timezone.utc).isoformat(),
                'error_type':type(exc).__name__,'run_id':run_id,'phase':phase,
                'pricing_and_stakes_changed':False}
        try: atomic(output/'status.json',status)
        except OSError: pass
        print('WARNING: tennis input health CHECK_FAILED; pricing continues unchanged. '+type(exc).__name__)
        return status

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    p.add_argument('--output',type=Path)
    p.add_argument('--phase',choices=('before','after','standalone'),default='standalone')
    p.add_argument('--run-id',default=uuid.uuid4().hex)
    a=p.parse_args()
    if a.output: record(a.root,a.output,a.phase,a.run_id)
    else: safe_observe(a.root,a.phase,a.run_id)

if __name__=='__main__': main()
