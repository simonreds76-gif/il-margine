"""Retain named keeper outcomes from the existing Aerial match response.

Research labels only. No forecasts, odds, selections or settlements are edited.
Conflicting source revisions remain separate; missing counts remain unknown.
"""
from hashlib import sha256
from aerial_source import validate
from football_identity import read, write
from verified_player_targets import extract


def target_record(page, fixture, raw, observed_at):
    validate(page, fixture)
    digest = sha256(raw).hexdigest()
    rows = extract({'props': {'pageProps': page}}, digest)
    keepers = [r for r in rows if r['is_goalkeeper']]
    if not keepers:
        raise ValueError('No explicit keeper appearances in completed match')
    return {'match_id': str(fixture['id']), 'kickoff': page['general']['matchTimeUTCDate'],
            'league_id': str(fixture['league_id']), 'home': page['general']['homeTeam'],
            'away': page['general']['awayTeam'], 'observed_at': observed_at,
            'source_url': f'https://www.fotmob.com/api/data/matchDetails?matchId={fixture["id"]}',
            'source_sha256': digest, 'keepers': keepers,
            'full_match_agreement': len(keepers) == 2 and all(
                r['started'] and r['minutes'] == 90 and r['saves'] is not None
                and r['saves'] == r['event_saves'] and not r['target_conflict'] for r in keepers)}


def retain(path, record):
    archive = read(path, {'schema_version': 1, 'fixtures': {}})
    if archive.get('schema_version') != 1:
        raise ValueError('Unsupported named-keeper history schema')
    versions = archive['fixtures'].setdefault(record['match_id'], [])
    if any(r['source_sha256'] == record['source_sha256'] for r in versions):
        return False
    versions.append(record)
    write(path, archive)
    return True
