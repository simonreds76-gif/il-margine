"""Read-only source verification. Paper-source freshness never certifies live Elo."""
from __future__ import annotations
import hashlib
import json
import math
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

MAX_SOURCE_AGE_DAYS = 14
MAX_OBSERVATION_AGE_HOURS = 48
MAX_BYTES = 4 * 1024 * 1024


def stamp(value):
    dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if dt.tzinfo is None:
        raise ValueError('timezone_missing')
    return dt.astimezone(timezone.utc)


def bounded_bytes(path):
    with path.open('rb') as handle:
        raw = handle.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError('evidence_too_large')
    return raw


def published_source(root, tour, now):
    """Verify the existing dated collector's immutable evidence; no HTTP or writes."""
    result = {'role': 'paper_comparison_only', 'live_ratings_changed': False,
              'state': 'UNAVAILABLE', 'tour': tour}
    players = {}
    try:
        folder = root / 'data/tennis-elo-source' / tour.lower()
        status = json.loads(bounded_bytes(folder / 'status.json'))
        good = status['last_good']
        relative = Path(good['snapshot'])
        path = (folder / relative).resolve()
        if relative.is_absolute() or path.parent != (folder / 'snapshots').resolve():
            raise ValueError('snapshot_path_invalid')
        raw = bounded_bytes(path)
        if hashlib.sha256(raw).hexdigest() != good['sha256']:
            raise ValueError('snapshot_hash_mismatch')
        data = json.loads(raw)
        if data['version'] != 'ta-elo-isolated-v1' or data['tour'] != tour:
            raise ValueError('snapshot_schema_mismatch')
        if data.get('live_writes') is not False or status.get('live_writes') is not False:
            raise ValueError('unexpected_live_writer_claim')
        if data['publication_date'] != good['publication_date'] or data['observed_at'] != good['observed_at']:
            raise ValueError('snapshot_pointer_metadata_mismatch')
        raw_hash = data['raw_sha256']
        if not re.fullmatch('[0-9a-f]{64}', raw_hash):
            raise ValueError('raw_hash_invalid')
        if hashlib.sha256(bounded_bytes(folder / 'raw' / (raw_hash + '.html'))).hexdigest() != raw_hash:
            raise ValueError('raw_source_hash_mismatch')
        observed = stamp(data['observed_at'])
        attempted = stamp(status['last_attempt_at'])
        published = date.fromisoformat(data['publication_date'])
        if observed > now or attempted > now or published > observed.date():
            raise ValueError('future_source_evidence')
        if attempted < observed - timedelta(minutes=1):
            raise ValueError('attempt_precedes_observation')
        records = data['players']
        if any(not math.isfinite(float(row['overall'])) or float(row['overall']) <= 0 for row in records):
            raise ValueError('source_rating_invalid')
        players = {int(row['oncourt_id']): row for row in records}
        if len(players) != len(records) or len(records) + len(data['gaps']) != data['source_row_count']:
            raise ValueError('source_identity_counts_invalid')
        state = 'CURRENT'
        if (now.date() - published).days > MAX_SOURCE_AGE_DAYS:
            state = 'STALE_PUBLICATION'
        elif now - observed > timedelta(hours=MAX_OBSERVATION_AGE_HOURS):
            state = 'STALE_OBSERVATION'
        elif status.get('state') != 'VALIDATED':
            state = 'LAST_ATTEMPT_FAILED_OR_INCOMPLETE'
        result.update(state=state, publication_date=published.isoformat(), observed_at=observed.isoformat(),
                      last_attempt_at=attempted.isoformat(), last_attempt_state=status.get('state'),
                      source_age_days=(now.date() - published).days,
                      mapped_players=len(players), source_players=data['source_row_count'],
                      unresolved_source_identities=len(data['gaps']), snapshot_sha256=good['sha256'],
                      raw_sha256=raw_hash, integrity_verified=True)
    except FileNotFoundError:
        result.update(state='MISSING_EVIDENCE', integrity_verified=False)
        players = {}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        result.update(state='INVALID_EVIDENCE', integrity_verified=False)
        players = {}
    return result, players


def native_research_source(root, now):
    result={'role':'research_source_only','live_ratings_changed':False,'state':'MISSING_EVIDENCE'}
    folder=root/'data/tennis-elo-source/native-adult-v1'
    try:
        s=json.loads(bounded_bytes(folder/'status.json'))
        if s['version']!='native-adult-elo-source-v1-20261101' or s['live_writes'] is not False:
            raise ValueError('invalid_native_source')
        for filename,field in [('candidate.json','candidate_sha256'),('history.json.gz','history_file_sha256')]:
            if (folder/filename).stat().st_size>64*1024*1024:raise ValueError('source_size_limit')
            if hashlib.sha256((folder/filename).read_bytes()).hexdigest()!=s[field]:raise ValueError('source_integrity')
        observed=stamp(s['checked_at']);cutoff=date.fromisoformat(s['latest_available_result'])
        if observed>now or cutoff>=date.fromisoformat(s['as_of_exclusive']):raise ValueError('future_source')
        state=s['state']
        if now-observed>timedelta(hours=48):state='STALE_OBSERVATION'
        if (now.date()-cutoff).days>3:state='STALE_RESULT_CUTOFF'
        result.update(state=state,integrity_verified=True,checked_at=s['checked_at'],
            latest_available_result=s['latest_available_result'],history_matches=s['history_matches'],rating_rows=s['rating_rows'],
            candidate_sha256=s['candidate_sha256'],missing_player_followup=s['missing_player_followup'],
            limitation='Restored adult ITF source; not promoted and not proof of live source freshness.')
    except FileNotFoundError:pass
    except (OSError,ValueError,KeyError,TypeError):result.update(state='INVALID_EVIDENCE',integrity_verified=False)
    return result


def annotate_sources(root, status, elo, now, names=None):
    """Attach independent source status without relaxing any legacy health state."""
    names = names or {}
    sources = {}
    atp = {}
    for tour in ('ATP', 'WTA'):
        sources[tour], players = published_source(root, tour, now)
        if tour == 'ATP':
            atp = players
    status['elo_sources'] = {
        'live': {'state': 'PROVENANCE_UNVERIFIED', 'last_verified_refresh_at': None,
                 'timestamp_semantics': 'Legacy writers omitted updated_at; stored dates do not prove last refresh.',
                 'action': 'Keep current ratings; a source substitution requires a separate reviewed model decision.'},
        'published_research': sources,
        'native_adult_research': native_research_source(root,now),
    }
    missing = {}
    for fixture in status.get('fixtures', []):
        for pid, surface in fixture.get('missing_elo_keys', []):
            missing.setdefault(int(pid), set()).add(surface)
    status['missing_elo_players'] = [
        {'player_id': pid, 'name': names.get(pid, str(pid)), 'missing_surfaces': sorted(surfaces),
         'available_in_verified_published_snapshot': pid in atp}
        for pid, surfaces in sorted(missing.items())
    ]
    # Compare Overall only. Mixed legacy algorithms preclude treating disagreement as dated staleness.
    differences = [abs(float(row['elo']) - float(atp[int(row['player_id'])]['overall']))
                   for row in elo if row['surface'] == 'Overall' and int(row['player_id']) in atp]
    status['published_overall_parity'] = {
        'compared_players': len(differences), 'different_players': sum(d > 0.05 for d in differences),
        'max_absolute_difference': max(differences) if differences else None,
        'interpretation': 'Content comparison only; mixed legacy origin prevents inferring a last refresh date.',
    }
    return status
