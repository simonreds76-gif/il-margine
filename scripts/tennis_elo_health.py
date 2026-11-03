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


def missing_requirements(status):
    """Current fixture requirements, never a fixed list of player IDs."""
    required = {}
    for fixture in status.get('fixtures', []):
        if fixture.get('active_for_coverage') is False:
            continue
        for pid, surface in fixture.get('missing_elo_keys', []):
            required.setdefault(int(pid), set()).add(str(surface))
    return required


def research_followup(ratings, required, names=None):
    names = names or {}
    lookup = {}
    for row in ratings:
        key = (int(row['player_id']), str(row['surface']))
        value = float(row['elo'])
        if key in lookup or not math.isfinite(value) or value <= 0 or int(row['match_count']) <= 0:
            raise ValueError('invalid_or_duplicate_research_rating')
        lookup[key] = row
    result = []
    for pid, surfaces in sorted(required.items()):
        needed = sorted(set(surfaces) | {'Overall'})
        values = {surface: lookup.get((pid, surface)) for surface in needed}
        result.append({'player_id': pid, 'name': names.get(pid, str(pid)),
                       'required_surfaces': sorted(surfaces), 'ratings': values,
                       'Overall': values.get('Overall'), 'I.hard': values.get('I.hard'),
                       'history_quality': {surface: 'NO_VALIDATED_HISTORY' if row is None else
                           'THIN_HISTORY' if int(row['match_count']) < 10 else 'OBSERVED_HISTORY'
                           for surface, row in values.items()}})
    return result


def native_research_source(root, now, required=None, names=None):
    result={'role':'research_source_only','live_ratings_changed':False,'state':'MISSING_EVIDENCE'}
    folder=root/'data/tennis-elo-source/native-adult-v1'
    try:
        s=json.loads(bounded_bytes(folder/'status.json'))
        if s['version']!='native-adult-elo-source-v1-20261101' or s['live_writes'] is not False:
            raise ValueError('invalid_native_source')
        candidate = None
        for filename,field in [('candidate.json','candidate_sha256'),('history.json.gz','history_file_sha256')]:
            if (folder/filename).stat().st_size>64*1024*1024:raise ValueError('source_size_limit')
            raw = (folder/filename).read_bytes()
            if hashlib.sha256(raw).hexdigest()!=s[field]:raise ValueError('source_integrity')
            if filename == 'candidate.json': candidate = json.loads(raw)
        observed=stamp(s['checked_at']);cutoff=date.fromisoformat(s['latest_available_result'])
        if observed>now or cutoff>=date.fromisoformat(s['as_of_exclusive']) or date.fromisoformat(s['as_of_exclusive'])>now.date():raise ValueError('future_source')
        if (candidate['version'] != s['version'] or candidate['live_writes'] is not False
                or candidate['as_of_exclusive'] != s['as_of_exclusive']
                or candidate['latest_available_result'] != s['latest_available_result']
                or candidate['method'] != s['method']):
            raise ValueError('candidate_contract_mismatch')
        followup = research_followup(candidate['ratings'], required or {}, names)
        state=s['state']
        if now-observed>timedelta(hours=48):state='STALE_OBSERVATION'
        if (now.date()-cutoff).days>3:state='STALE_RESULT_CUTOFF'
        changed_exports = []
        for filename in ('players_atp.csv','tours_atp.csv','games_atp.csv','courts.csv'):
            relative = 'data/oncourt/' + filename
            expected = s['source_hashes'].get(relative)
            if not expected:
                raise ValueError('native_input_manifest_missing')
            with (root/relative).open('rb') as handle:
                current = hashlib.file_digest(handle, 'sha256').hexdigest()
            if current != expected:
                changed_exports.append(relative)
        if changed_exports: state='SOURCE_EXPORTS_CHANGED'
        result.update(state=state,integrity_verified=True,checked_at=s['checked_at'],
            latest_available_result=s['latest_available_result'],history_matches=s['history_matches'],rating_rows=s['rating_rows'],
            candidate_sha256=s['candidate_sha256'],as_of_exclusive=s['as_of_exclusive'],
            method=s['method'],missing_player_followup=followup,
            changed_exports=changed_exports,
            followup_scope='current active fixture gaps; recomputed on every health observation',
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
    missing = missing_requirements(status)
    native = native_research_source(root, now, missing, names)
    history = {row['player_id']: row for row in native.get('missing_player_followup', [])}
    status['elo_sources'] = {
        'live': {'state': 'PROVENANCE_UNVERIFIED', 'last_verified_refresh_at': None,
                 'timestamp_semantics': 'Legacy writers omitted updated_at; stored dates do not prove last refresh.',
                 'action': 'Keep current ratings; a source substitution requires a separate reviewed model decision.'},
        'published_research': sources,
        'native_adult_research': native,
    }
    status['missing_elo_players'] = []
    counts = {'live_gap_with_reconstructed_history': 0, 'no_validated_surface_history': 0,
              'history_unverified': 0}
    for pid, surfaces in sorted(missing.items()):
        assessments = {}
        for surface in sorted(surfaces):
            row = history.get(pid, {}).get('ratings', {}).get(surface)
            verified = native.get('state') == 'VALIDATED_RESEARCH_SOURCE' and native.get('integrity_verified')
            state = ('HISTORY_UNVERIFIED' if not verified else 'LIVE_GAP_WITH_RECONSTRUCTED_HISTORY'
                     if row else 'NO_VALIDATED_SURFACE_HISTORY')
            counts[{'HISTORY_UNVERIFIED':'history_unverified',
                    'LIVE_GAP_WITH_RECONSTRUCTED_HISTORY':'live_gap_with_reconstructed_history',
                    'NO_VALIDATED_SURFACE_HISTORY':'no_validated_surface_history'}[state]] += 1
            published = atp.get(pid, {})
            published_value = (published.get('overall') if surface == 'Overall' else
                               published.get('surface_blended', {}).get('Hard' if surface == 'I.hard' else surface))
            assessments[surface] = {
                'state': state, 'validated_match_count': int(row['match_count']) if verified and row else 0 if verified else None,
                'history_as_of_exclusive': native.get('as_of_exclusive'),
                'reconstructed_rating': float(row['elo']) if verified and row else None,
                'reconstructed_rating_role': 'research_only_not_a_live_replacement',
                'latest_validated_result': row.get('latest_result') if verified and row else None,
                'published_value': published_value,
                'published_kind': ('hard_blend_proxy_not_indoor' if surface == 'I.hard' else
                                   'published_overall' if surface == 'Overall' else 'published_surface_blend') if published_value is not None else None,
                'live_changed': False}
        status['missing_elo_players'].append({'player_id':pid, 'name':names.get(pid,str(pid)),
            'missing_surfaces':sorted(surfaces), 'available_in_verified_published_snapshot':pid in atp,
            'assessments':assessments})
    status['missing_input_classification'] = counts
    # Compare Overall only. Mixed legacy algorithms preclude treating disagreement as dated staleness.
    differences = [abs(float(row['elo']) - float(atp[int(row['player_id'])]['overall']))
                   for row in elo if row['surface'] == 'Overall' and int(row['player_id']) in atp]
    status['published_overall_parity'] = {
        'compared_players': len(differences), 'different_players': sum(d > 0.05 for d in differences),
        'max_absolute_difference': max(differences) if differences else None,
        'interpretation': 'Content comparison only; mixed legacy origin prevents inferring a last refresh date.',
    }
    return status
