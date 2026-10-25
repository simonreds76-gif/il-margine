"""Exact-ID, bounded height recovery in the existing football publication job.

Heights belong to players, not club/name pairs. Lineup membership and profile
primary-team labels are separate evidence (first/reserve teams often differ).
No inferred measurements, name-only joins, formula changes or historical rewrites.
"""
from datetime import timedelta
from hashlib import sha256
import json
import math
import re
import time
import unicodedata
from urllib.parse import urlparse
import requests
from aerial_data import LEAGUES, read, save, utc, make_fixture
from football_identity import resolve, compatible_label

MAX_PER_RUN = 8
MAX_PER_DAY = 32


def valid_height(value):
    return type(value) in (int, float) and math.isfinite(value) and 130 <= value <= 230


def held(row):
    return row.get('status') == 'held' or row.get('height_status') == 'held'


def merge_squad(old, player, tid, group, url, digest, now):
    """Refresh membership independently; never erase a sourced measurement."""
    pid = str(player['id'])
    if old.get('id', pid) != pid:
        raise ValueError('Height/player identity mismatch')
    result = {**old, 'id': pid, 'name': player['name'], 'team_id': str(tid),
              'positions': player.get('positionIdsDesc') or old.get('positions'),
              'role_group': group, 'club_observed_at': now.isoformat(),
              'club_source_url': url, 'club_source_sha256': digest}
    value = player.get('height')
    protected = held(old) or old.get('source_kind') == 'reviewed_external'
    if valid_height(value) and not protected:
        result.update(height_cm=value, source_url=url, source_sha256=digest,
                      observed_at=now.isoformat(), source_kind='current_squad', status='reported')
    elif not valid_height(old.get('height_cm')) and not protected:
        result.update(height_cm=None, source_url=url, source_sha256=digest,
                      observed_at=now.isoformat(), source_kind='current_squad', status='reported')
    return result


def lineup_targets(root, calendar, heights, now):
    """Reuse the board's identity/freshness validator, without scanning history."""
    lines = {}
    duplicates = set()
    for slug, _, _ in LEAGUES.values():
        name = 'confirmed-lineups.json' if slug == 'serie-a' else slug+'-confirmed-lineups.json'
        for line in read(root/'data/goalscorer'/name, {}).get('fixtures', []):
            mid = str(line.get('fotmob_match_id'))
            if mid in lines:
                duplicates.add(mid)
            lines[mid] = line
    targets, errors = {}, []
    for row in calendar.get('fixtures', []):
        if row.get('disposition') != 'not_completed' or not now < utc(row['date']) <= now+timedelta(days=8):
            continue
        try:
            if row['id'] in duplicates:
                raise ValueError('Duplicate live fixture')
            fixture = make_fixture(row, lines.get(row['id']), [], heights, now)
            for team in fixture['teams']:
                for player in team['players']:
                    pid = player['id']
                    target = dict(id=pid, name=player['name'], team_id=team['id'], team=team['name'],
                                  role=player['role'],
                                  fixture_id=fixture['id'], kickoff=fixture['kickoff'],
                                  observed_at=fixture['observed_at'], source_url=fixture['source_url'])
                    # Prefer the most recently observed valid XI for club membership.
                    if pid not in targets or utc(target['observed_at']) > utc(targets[pid]['observed_at']):
                        targets[pid] = target
        except (ValueError, KeyError, TypeError) as exc:
            errors.append(dict(fixture_id=row.get('id'), reason=str(exc)))
    return targets, errors


def profile_record(page, pid, old, url, digest, now):
    profile = page.get('data', {})
    if str(profile.get('id')) != pid or profile.get('isCoach') or not profile.get('name'):
        raise ValueError('Profile identity mismatch')
    dob = (profile.get('birthDate') or {}).get('utcTime', '')[:10]
    if old.get('dob') and dob and old['dob'][:10] != dob:
        raise ValueError('Profile birth date mismatch')
    fields = [p for p in profile.get('playerInformation', [])
              if p.get('translationKey') == 'height_sentencecase']
    values = [p.get('value', {}).get('numberValue') for p in fields]
    if len(values) > 1:
        raise ValueError('Ambiguous profile height')
    value = values[0] if values else None
    if value is not None and not valid_height(value):
        raise ValueError('Invalid profile height')
    result = {**old, 'id': pid, 'name': old.get('name') or profile['name'],
              'dob': dob or old.get('dob'), 'profile_checked_at': now.isoformat(),
              'profile_team_id': str((profile.get('primaryTeam') or {}).get('teamId') or ''),
              'profile_source_url': url, 'profile_source_sha256': digest}
    # Membership remains the roster/fixture ID, never a potentially stale primaryTeam.
    if not result.get('positions'):
        positions = profile.get('positionDescription', {}).get('positions', [])
        primary = [p.get('strPosShort', {}).get('label') for p in positions if p.get('isMainPosition')]
        if len(primary) == 1 and primary[0]:
            result['positions'] = primary[0]
    if valid_height(value) and not held(old) and old.get('source_kind') != 'reviewed_external':
        result.update(height_cm=value, source_url=url, source_sha256=digest,
                      observed_at=now.isoformat(), source_kind='player_profile', status='reported')
    return result, value


def sky_url(registry, pid, row):
    link = resolve(registry, 'fotmob', 'person', pid, 'opta', 'person_numeric')
    if link.get('status') != 'registry_linked' or not link['id'].isdigit() or not row.get('dob'):
        return None
    name = row['name'].translate(str.maketrans({'ø':'o','Ø':'O','ł':'l','Ł':'L','ß':'ss','æ':'ae','œ':'oe','đ':'d'}))
    slug = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode().lower()
    slug = re.sub(r'[^a-z0-9]+', '-', slug).strip('-')
    return f'https://sport.sky.it/calcio/atleti/{slug}/{link["id"]}'


def fetch_secondary(url):
    response = requests.get(url, timeout=25)
    response.raise_for_status()
    time.sleep(.5)
    return response.text, sha256(response.content).hexdigest()


def secondary_record(html, old, url, digest, now):
    """Mapped Opta ID AND exact DOB AND compatible name, never a fuzzy lookup."""
    canonical = re.findall(r'<link\b[^>]*rel=[\"\']canonical[\"\'][^>]*href=[\"\']([^\"\']+)', html, re.I)
    expected = urlparse(url)
    if len(canonical) != 1 or urlparse(canonical[0]).netloc != expected.netloc or \
            urlparse(canonical[0]).path.rstrip('/').split('/')[-1] != expected.path.split('/')[-1]:
        raise ValueError('Secondary profile ID mismatch')
    people = []
    for block in re.findall(r'<script[^>]*type=[\"\']application/ld\+json[\"\'][^>]*>(.*?)</script>', html, re.S|re.I):
        parsed = json.loads(block)
        for item in parsed if isinstance(parsed, list) else [parsed]:
            if item.get('@type') == 'Person':
                people.append(item)
    if len(people) != 1:
        raise ValueError('Secondary profile not a unique person')
    person = people[0]
    if not old.get('dob') or person.get('birthDate') != old['dob'] or not compatible_label([old['name']], person.get('name')):
        raise ValueError('Secondary profile name/birth date mismatch')
    raw = person.get('height')
    match = re.fullmatch(r'(\d{3}(?:\.\d+)?)\s*cm', str(raw or '').strip())
    value = float(match.group(1)) if match else None
    if raw and raw not in ('-', '0 cm') and (not match or not valid_height(value)):
        raise ValueError('Secondary height format invalid')
    result = dict(old)
    if valid_height(value) and not held(old):
        result.update(height_cm=value, source_url=canonical[0], source_sha256=digest,
                      observed_at=now.isoformat(), source_kind='mapped_secondary_profile', status='reported',
                      height_identity_check='mapped_opta_id+exact_dob+compatible_name')
    return result, value, person


def recover(root, calendar, now, fetch, online=True, max_per_run=MAX_PER_RUN, max_per_day=MAX_PER_DAY,
            secondary_fetch=fetch_secondary):
    data = root/'data/aerial'
    heights = read(data/'heights.json.gz', {})
    state = read(data/'height-recovery-state.json', {'attempts': {}})
    targets, errors = lineup_targets(root, calendar, heights, now)
    for pid, target in targets.items():
        old = heights.get(pid, {})
        # This is fixture membership, not a claim of transfer or permanent employment.
        heights[pid] = {**old, 'id': pid, 'name': old.get('name') or target['name'],
                        'height_cm': old.get('height_cm'), 'lineup_membership': target}
        if not old.get('team_id'):
            heights[pid].update(team_id=target['team_id'],club_observed_at=target['observed_at'],
                                club_source_url=target['source_url'],club_mapping_basis='validated_lineup')
    if state.get('day') != now.date().isoformat():
        state.update(day=now.date().isoformat(), requests_today=0, background_requests_today=0)
    attempts = state.setdefault('attempts', {})
    registry = read(data/'identity-registry.json.gz', {})
    missing = [pid for pid, row in heights.items() if not held(row) and
               (not valid_height(row.get('height_cm')) or
                (row.get('source_kind') == 'player_profile' and attempts.get(pid, {}).get('status') == 'recovered'
                 and not attempts.get(pid+'|sky') and sky_url(registry, pid, row)))]
    missing.sort(key=lambda pid: (pid not in targets, targets.get(pid, {}).get('kickoff', ''),
                                  targets.get(pid, {}).get('role') == 'GK',
                                  attempts.get(pid, {}).get('attempted_at', ''), pid))
    recovered, attempted = [], []
    budget = min(max_per_run, max(0, max_per_day-state['requests_today'])) if online else 0
    if state.get('source_blocked_until') and now < utc(state['source_blocked_until']):
        budget = 0
    while missing:
        pid = missing.pop(0)
        if len(attempted) >= budget:
            break
        # Reserve half of the day's allowance for later expected/official XIs.
        if pid not in targets and state.get('background_requests_today', 0) >= max_per_day//2:
            continue
        previous = attempts.get(pid, {})
        url = f'https://www.fotmob.com/players/{pid}'
        primary_recent = previous.get('attempted_at') and now-utc(previous['attempted_at']) < timedelta(days=7)
        secondary = previous.get('status') in ('no_reported_height','recovered') and primary_recent and sky_url(registry, pid, heights[pid])
        attempt_key = pid+'|sky' if secondary else pid
        if secondary:
            url = secondary
            previous = attempts.get(attempt_key, {})
        # A missing field is retried weekly; transient failures after six hours.
        cooldown = timedelta(days=7) if previous.get('status') in ('no_reported_height', 'profile_not_found') else timedelta(hours=6)
        if previous.get('attempted_at') and now-utc(previous['attempted_at']) < cooldown:
            continue
        if not pid.isdigit():
            continue
        attempt = dict(attempted_at=now.isoformat(), status='attempting', source_url=url)
        attempts[attempt_key] = attempt
        state['requests_today'] += 1
        if pid not in targets:
            state['background_requests_today'] = state.get('background_requests_today', 0)+1
        attempted.append(attempt_key)
        # Persist before requesting: failed/crashed calls also consume the budget.
        save(data/'height-recovery-state.json', state)
        try:
            old = heights[pid]
            if secondary:
                html, digest = secondary_fetch(url)
                entry, value, evidence = secondary_record(html, old, url, digest, now)
                if valid_height(old.get('height_cm')) and valid_height(value):
                    comparison = dict(primary_cm=old['height_cm'],secondary_cm=value,
                                      primary_url=old.get('source_url'),secondary_url=url,
                                      checked_at=now.isoformat())
                    if abs(old['height_cm']-value) > 2:
                        entry = {**old,'height_cm':None,'status':'held','source_kind':'profile_conflict',
                                 'height_conflict':comparison}
                    else:
                        entry = {**old,'height_crosscheck':comparison}
            else:
                page, digest = fetch(url)
                entry, value = profile_record(page, pid, old, url, digest, now)
                profile = page['data']
                evidence = {k:profile.get(k) for k in ('id','name','birthDate','primaryTeam',
                            'playerInformation','positionDescription')}
            heights[pid] = entry
            attempt.update(status='recovered' if valid_height(value) else 'no_reported_height',
                           source_sha256=digest, reported_height_cm=value)
            if held(entry):
                attempt['status'] = 'conflicting_heights'
                if pid in recovered: recovered.remove(pid)
            elif valid_height(value) and not valid_height(old.get('height_cm')):
                recovered.append(pid)
            # Retain compact exact source fields, not every season's profile statistics.
            filename = pid+'-sky' if secondary else pid
            evidence_path = data/'height-profile-evidence.json.gz'
            retained = read(evidence_path, {})
            retained[filename] = dict(url=url, sha256=digest, observed_at=now.isoformat(), fields=evidence)
            save(evidence_path, retained)
            # An official XI may arrive less than an hour before kickoff. Try
            # its mapped fallback in THIS cycle, within the same request cap.
            if not secondary and sky_url(registry, pid, entry):
                missing.insert(0, pid)
        except Exception as exc:
            attempt.update(status='error', error=str(exc))
            response = getattr(exc, 'response', None)
            if response is not None and response.status_code == 404:
                attempt['status'] = 'profile_not_found'
            if response is not None and response.status_code in (403, 429):
                state['source_blocked_until'] = (now+timedelta(hours=6)).isoformat()
                break
        finally:
            save(data/'heights.json.gz', heights)
            save(data/'height-recovery-state.json', state)
    save(data/'heights.json.gz', heights)
    gaps = [dict(id=pid, name=row.get('name'), team_id=targets.get(pid, {}).get('team_id', row.get('team_id')),
                 team=targets.get(pid, {}).get('team'), upcoming=pid in targets,
                 status='held' if held(row) else attempts.get(pid+'|sky', attempts.get(pid, {})).get('status', 'not_checked'),
                 source_url=attempts.get(pid+'|sky', attempts.get(pid, {})).get('source_url'))
            for pid, row in heights.items() if held(row) or not valid_height(row.get('height_cm'))]
    report = dict(generated_at=now.isoformat(), registry_players=len(heights), missing=len(gaps),
                  upcoming_players=len(targets), upcoming_missing=sum(g['upcoming'] for g in gaps),
                  attempted=attempted, recovered=recovered, requests_today=state['requests_today'],
                  daily_budget=max_per_day, budget_mode='one_off_catchup' if max_per_day > MAX_PER_DAY else 'scheduled',
                  gaps=gaps, invalid_lineups=errors)
    save(data/'height-recovery-health.json', report)
    return report
