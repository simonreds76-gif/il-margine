"""Offline, exact-fixture settlement evidence. Never a model or training input."""
import csv
import hashlib
import json
from datetime import datetime, date, time, timedelta, timezone
from functools import lru_cache
from pathlib import Path

RELATIVE = Path('data/tennis-ml-research/settlement-evidence-v1')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def utc(value):
    try:
        v = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return v.astimezone(timezone.utc) if v.tzinfo else None
    except (ValueError, TypeError):
        return None


def key(row):
    return '|'.join([str(row['tour_id']), str(row['round_id']), *sorted(map(str, row['players']))])


def game_key(g):
    return '|'.join([str(g['tour_id']), str(g['round_id']), *sorted([str(g['winner_id']), str(g['loser_id'])])])


def signature(path):
    p = Path(path)
    try:
        s = p.stat()
        return str(p.resolve()), s.st_size, s.st_mtime_ns
    except OSError:
        return str(p.resolve()), 0, 0


@lru_cache(maxsize=8)
def _load_registry(reg_sig, players_sig, tours_sig, source_signatures, checkpoint_sig):
    path = Path(reg_sig[0]); root = path.parent
    if not path.exists():
        return {}, None, 'missing_settlement_registry'
    try:
        with Path(players_sig[0]).open(encoding='utf-8-sig') as f:
            players = {r['id'] for r in csv.DictReader(f)}
        with Path(tours_sig[0]).open(encoding='utf-8-sig') as f:
            tours = {r['id'] for r in csv.DictReader(f)}
        rows = [json.loads(x) for x in path.read_text(encoding='utf8').splitlines() if x.strip()]
        checkpoint=json.loads(Path(checkpoint_sig[0]).read_bytes())
        by_key = {}; previous = None; heads=set()
        for row in rows:
            if row.get('schema_version')!=1:raise ValueError('unsupported_evidence_schema')
            content = {k:v for k,v in row.items() if k != 'sha256'}
            if row['sha256'] != digest(content) or row['previous_sha256'] != previous:
                raise ValueError('broken_evidence_chain')
            previous = row['sha256']
            heads.add(previous)
            parts = row['fixture_key'].split('|')
            if len(parts)!=4 or parts[0] not in tours or parts[2] == parts[3] or not set(parts[2:]) <= players or parts[2:] != sorted(parts[2:]) or not parts[1].isdigit():
                raise ValueError('unverified_native_identity')
            if row['kind'] not in ('walkover', 'pair_not_played', 'revised_schedule') or row['fixture_key'] in by_key:
                raise ValueError('ambiguous_evidence_kind_or_key')
            if not utc(row['observed_at']) or not row['sources']:
                raise ValueError('missing_observation_or_source')
            for source in row['sources']:
                rel = Path(source['file'])
                if rel.is_absolute() or '..' in rel.parts or not source['url'].startswith('https://'):
                    raise ValueError('invalid_source_path')
                if hashlib.sha256((root/rel).read_bytes()).hexdigest() != source['sha256']:
                    raise ValueError('source_hash_mismatch')
            if row['kind'] == 'revised_schedule':
                start = utc(row['revised_start']); published = utc(row['source_published_at'])
                if not start or not published or not published < start or row.get('time_basis') != 'official_not_before':
                    raise ValueError('invalid_revised_start')
            else:
                date.fromisoformat(row['event_date'])
            by_key[row['fixture_key']] = row
        if checkpoint['last_seen_head'] not in heads:
            raise ValueError('registry_truncated_or_replaced')
        return by_key, previous, None
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return {}, None, 'invalid_settlement_evidence:'+str(exc)


def registry(root):
    root = Path(root); folder = root/RELATIVE
    # Include source mtimes in the cache identity, so a changed source fails closed.
    sources = tuple(signature(p) for p in sorted((folder/'sources').glob('*')))
    return _load_registry(signature(folder/'registry.jsonl'), signature(root/'data/oncourt/players_atp.csv'),
                          signature(root/'data/oncourt/tours_atp.csv'), sources,signature(folder/'checkpoint.json'))


@lru_cache(maxsize=8)
def _nonplayed(sig):
    from oncourt_nonplayed import verified_nonplayed
    rows = {}
    for g in verified_nonplayed(Path(sig[0])):
        rows.setdefault(game_key(g), []).append(g)
    return rows


def timing(record, game, now, evidence=None):
    """Date shifts need either a conservative whole-day bound or a verified start."""
    try:
        day = date.fromisoformat(game['date'][:10]); q = record['quote']
        start = utc(q.get('kickoff_iso') or q.get('scheduled_start'))
        stamp = utc(record.get('captured_at') or record.get('registered_at'))
        quoted = utc(q.get('captured_at') or q.get('fetched_at') or q.get('observed_at'))
        if not start or not stamp or not stamp < start or day > now.date():
            return False
        if quoted and not quoted < start:
            return False
        if day == start.date():
            return True
        if abs((day-start.date()).days)>7:
            return False
        if evidence and evidence['kind']=='revised_schedule':
            revised = utc(evidence['revised_start'])
            return bool(revised and revised.date()==day and quoted and max(stamp, quoted)<revised<=now)
        earliest = datetime.combine(day, time(), timezone.utc)-timedelta(hours=14)
        return bool(quoted and max(stamp, quoted)<earliest)
    except (ValueError, KeyError, TypeError):
        return False


def resolve(root, record, games, now):
    """Return a played source row, an evidence-backed void, or an explicit hold."""
    try:
        fixture = key(record)
        if record.get('fixture_key') != fixture or any(game_key(g)!=fixture for g in games):
            return dict(status='quarantined', reason='result_identity')
        index, chain, error = registry(root); evidence = index.get(fixture)
        source_error=None
        try:
            extra = _nonplayed(signature(Path(root)/'data/oncourt/nonplayed-results_atp.csv')).get(fixture, [])
        except (OSError,ImportError,ValueError,KeyError):
            extra=[];source_error='nonplayed_source_unavailable'
        distinct = {(str(g['winner_id']),str(g['loser_id']),g['date'],g['result']):g for g in games}
        if len(distinct)>1 or (games and extra) or (games and evidence and evidence['kind']!='revised_schedule'):
            return dict(status='quarantined', reason='conflicting_result_evidence')
        if len(extra)>1:
            return dict(status='quarantined', reason='ambiguous_nonplayed_result')
        if extra:
            g = extra[0]; day = date.fromisoformat(g['date'][:10])
            start = utc(record['quote'].get('kickoff_iso') or record['quote'].get('scheduled_start'))
            if day>now.date() or not start or abs((day-start.date()).days)>7:
                return dict(status='pending', reason='nonplayed_timing')
            return dict(status='void', reason='verified_native_walkover', score=g['result'], result_date=day.isoformat(),
                        evidence_id=hashlib.sha256(json.dumps(g,sort_keys=True).encode()).hexdigest())
        if evidence and evidence['kind'] in ('walkover', 'pair_not_played'):
            start = utc(record['quote'].get('kickoff_iso') or record['quote'].get('scheduled_start'))
            day = date.fromisoformat(evidence['event_date'])
            if day>now.date() or not start or start>now or abs((day-start.date()).days)>7:
                return dict(status='pending', reason='nonplayed_timing')
            return dict(status='void',reason='verified_'+evidence['kind'],score='W/O' if evidence['kind']=='walkover' else 'CANCELLED PAIRING',
                        result_date=day.isoformat(),evidence_id=evidence['sha256'])
        if not distinct:
            return dict(status='pending', reason=error or source_error or 'result_not_available')
        g = next(iter(distinct.values()))
        if not timing(record,g,now,evidence):
            return dict(status='quarantined', reason='result_timing_unverified')
        provenance={'evidence_id':evidence['sha256']} if evidence and evidence['kind']=='revised_schedule' else {}
        return dict(status='ready',game=g,provenance=provenance)
    except (OSError, ValueError, KeyError, TypeError):
        return dict(status='quarantined',reason='invalid_settlement_input')


@lru_cache(maxsize=4)
def _baseline(data_sig, manifest_sig):
    try:
        manifest = json.loads(Path(manifest_sig[0]).read_bytes())
        path = Path(data_sig[0])
        if hashlib.sha256(path.read_bytes()).hexdigest()!=manifest['sha256']:
            return {},'baseline_checksum_mismatch'
        return json.loads(path.read_bytes()),None
    except (OSError, ValueError, KeyError, TypeError):
        return {},'baseline_missing_or_invalid'


def preserved(root, lane, record):
    """Keep pre-repair terminal outcomes byte-equivalent; never conceal capture edits."""
    folder = Path(root)/RELATIVE
    baseline,error = _baseline(signature(folder/'baseline.json'), signature(folder/'baseline-manifest.json'))
    if error:raise ValueError(error)
    previous = baseline.get(str(lane).replace('\\','/').split('/')[-1], {}).get(record['fixture_key'])
    if previous:
        if previous['capture_digest']!=digest(record):
            return dict(status='quarantined',reason='original_capture_digest_mismatch')
        if previous.get('location')=='excluded-outcomes.json':
            return dict(status='preserved_excluded',outcome=json.loads(json.dumps(previous['outcome'])))
        return json.loads(json.dumps(previous['outcome']))
    return None


def archive_previous(folder, names=('outcomes.json',)):
    """Retain exact original bytes before any derived report is rebuilt."""
    folder=Path(folder)
    for name in names:
        p=folder/name
        if not p.exists():continue
        raw=p.read_bytes();out=folder/'outcome-history'/(hashlib.sha256(raw).hexdigest()+'-'+name)
        if not out.exists():
            out.parent.mkdir(parents=True,exist_ok=True)
            with out.open('xb') as f:f.write(raw)


def health(root):
    rows, chain, error = registry(root)
    folder=Path(root)/RELATIVE
    baseline,baseline_error=_baseline(signature(folder/'baseline.json'),signature(folder/'baseline-manifest.json'))
    sidecar=Path(root)/'data/oncourt/nonplayed-results_atp.csv'
    try:
        _nonplayed(signature(sidecar));sidecar_state='VERIFIED' if sidecar.exists() else 'MISSING'
    except (OSError,ImportError,ValueError,KeyError):sidecar_state='UNAVAILABLE'
    return dict(state='MISSING' if error=='missing_settlement_registry' else 'INVALID' if error or baseline_error else 'VERIFIED',registry_sha256=chain,records=len(rows),error=error or baseline_error,
                baseline_state='INVALID' if baseline_error else 'VERIFIED',nonplayed_source_state=sidecar_state,
                policy='exact edition/round/IDs; verified nonplayed sidecar; conservative changed-date timing; original terminal outcomes retained')


def require_valid(root):
    """Never overwrite ledgers when their protection or chain continuity is broken."""
    state=health(root)
    if state['state']!='VERIFIED':raise ValueError(state['error'] or state['state'])
    folder=Path(root)/RELATIVE;path=folder/'checkpoint.json';checkpoint=json.loads(path.read_bytes())
    if checkpoint['last_seen_head']!=state['registry_sha256']:
        checkpoint['last_seen_head']=state['registry_sha256']
        temp=path.with_suffix('.tmp');temp.write_text(json.dumps(checkpoint,sort_keys=True),encoding='utf8');temp.replace(path)


def validate_terminal_update(folder,previous,outcomes):
    """Allow late native statistics to be added, never replace recorded terminal values."""
    additions=[]
    for fixture,old in previous.items():
        if old.get('status') not in ('settled','void'):continue
        new=outcomes.get(fixture,{})
        if any(k not in new or new[k]!=v for k,v in old.items()):
            raise ValueError('terminal_outcome_value_changed:'+fixture)
        extra=set(new)-set(old)
        if not extra <= {'first_points','first_points_status'}:
            raise ValueError('unreviewed_terminal_outcome_fields:'+fixture)
        if extra:additions.append(dict(fixture_key=fixture,fields={k:new[k] for k in sorted(extra)},previous_digest=digest(old),updated_digest=digest(new)))
    if additions:
        packet=dict(kind='append_only_native_statistics',added=additions)
        path=Path(folder)/'outcome-enrichments'/(digest(packet)+'.json')
        path.parent.mkdir(parents=True,exist_ok=True)
        if not path.exists():
            with path.open('x',encoding='utf8') as f:json.dump(packet,f,sort_keys=True)
    return additions
