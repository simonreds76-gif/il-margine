"""Presentation-only, bounded identity recovery for the current Lab highlights.

Legacy signal IDs are never interpreted as FotMob IDs. A missing player is
resolved independently, by exact full name in their named club's verified squad.
The private cache survives existing polls; no website request performs this work.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

import requests
from player_name_matching import fold_name_text

PHOTO = 'https://images.fotmob.com/image_resources/playerimages/{}.png'
CACHE = 'lab-highlight-portrait-evidence.json'
RETRY = timedelta(hours=6)


def key(value):
    return re.sub(r'[^a-z0-9]', '', fold_name_text(value).lower())


def read(path, default):
    try:
        return json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError):
        return default


class NextData(HTMLParser):
    def __init__(self):
        super().__init__(); self.capture = False; self.parts = []

    def handle_starttag(self, tag, attrs):
        self.capture = tag == 'script' and dict(attrs).get('id') == '__NEXT_DATA__'

    def handle_data(self, value):
        if self.capture:
            self.parts.append(value)

    def handle_endtag(self, tag):
        if tag == 'script':
            self.capture = False


def exact_squad_player(html, club_id, name):
    parser = NextData(); parser.feed(html)
    data = json.loads(''.join(parser.parts))
    team = data.get('props', {}).get('pageProps', {}).get('fallback', {}).get(f'team-{club_id}', {})
    if team.get('details', {}).get('id') != club_id:
        raise ValueError('club_identity_mismatch')
    # No surname, initial, fuzzy or opponent-based guesses.
    if len(fold_name_text(name).split()) < 2:
        raise ValueError('full_name_required')
    matches = set()
    for group in team.get('squad', {}).get('squad') or []:
        if 'coach' in str(group.get('title', '')).lower():
            continue
        for player in group.get('members') or []:
            pid = player.get('id')
            if type(pid) is int and pid > 0 and key(player.get('name')) == key(name):
                matches.add(pid)
    if len(matches) != 1:
        raise ValueError('player_missing_or_ambiguous')
    return str(matches.pop())


def enrich(highlights, input_dir: Path, *, session=None, now=None):
    """Only photo fields and a separate coverage report may change."""
    now = now or datetime.now(timezone.utc)
    session = session or requests.Session()
    cache_path = input_dir / CACHE
    saved = read(cache_path, {'schema': 1, 'players': {}})
    entries = saved.get('players', {})
    teams = read(input_dir / 'team-logo-map.json', {}).get('leagues', {})
    curated = read(input_dir / 'penalty-player-portraits.json', {})
    # Hard budget for new identities; exceptions cannot block other highlights.
    requests_used = 0
    image_requests = 0
    team_pages = {}
    output, missing = [], []
    for original in highlights:
        row = dict(original)
        if re.fullmatch(r'https://images\.fotmob\.com/image_resources/playerimages/[1-9]\d*\.png', row.get('player_photo_url') or ''):
            output.append(row); continue
        identity = '|'.join([str(row.get('league', '')), key(row.get('team')), key(row.get('player'))])
        prior = entries.get(identity, {})
        if prior.get('status') == 'verified' and str(prior.get('fotmob_player_id', '')).isdigit() and int(prior['fotmob_player_id']) > 0:
            row['player_photo_url'] = PHOTO.format(prior['fotmob_player_id'])
            output.append(row); continue
        last = prior.get('checked_at')
        try:
            cooldown = last and now - datetime.fromisoformat(last) < RETRY
        except (TypeError, ValueError):
            cooldown = False
        if cooldown:
            missing.append({'id': row['id'], 'player': row['player'], 'reason': prior.get('reason', 'awaiting_retry')})
            output.append(row); continue
        evidence = {'checked_at': now.isoformat(), 'status': 'unresolved', 'player': row['player'], 'team': row.get('team')}
        try:
            pid = str(curated.get(key(row['player']), ''))
            if pid.isdigit() and int(pid) > 0:
                evidence['identity_source'] = 'verified_penalty_portrait_catalogue'
            else:
                options = teams.get(row.get('league'), {}).get('teams', {})
                matched = [v for name, v in options.items() if key(row.get('team')) in
                           {key(name), key(v.get('fotmob_name')), key(v.get('fotmob_short_name')), key(v.get('team_key'))}]
                ids = {v.get('fotmob_team_id') for v in matched}
                if len(ids) != 1 or not matched or type(matched[0].get('fotmob_team_id')) is not int:
                    raise ValueError('club_missing_or_ambiguous')
                club_id = matched[0]['fotmob_team_id']
                url = f'https://www.fotmob.com/teams/{club_id}/overview'
                evidence['identity_source'] = url
                if club_id not in team_pages:
                    if requests_used >= 6:
                        raise ValueError('bounded_request_budget')
                    requests_used += 1
                    response = session.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
                    response.raise_for_status()
                    if urlparse(response.url).hostname not in {'www.fotmob.com', 'fotmob.com'}:
                        raise ValueError('unexpected_source_redirect')
                    team_pages[club_id] = response.text
                pid = exact_squad_player(team_pages[club_id], club_id, row['player'])
            photo = PHOTO.format(pid)
            # One bounded image check per newly recovered identity, never per visitor.
            if image_requests >= 6:
                raise ValueError('bounded_request_budget')
            image_requests += 1
            image = session.get(photo, timeout=5, stream=True)
            try:
                image.raise_for_status()
                if not image.headers.get('Content-Type', '').lower().startswith('image/'):
                    raise ValueError('portrait_response_not_image')
            finally:
                image.close()
            evidence.update(status='verified', fotmob_player_id=pid, photo_url=photo)
            row['player_photo_url'] = photo
        except (requests.RequestException, ValueError, TypeError, KeyError, AttributeError) as exc:
            # No arbitrary response contents/credentials in public data or logs.
            reason = str(exc) if isinstance(exc, ValueError) and str(exc) in {
                'club_identity_mismatch', 'full_name_required', 'player_missing_or_ambiguous',
                'club_missing_or_ambiguous', 'bounded_request_budget', 'unexpected_source_redirect',
                'portrait_response_not_image'} else 'portrait_source_unavailable'
            evidence['reason'] = reason
            missing.append({'id': row['id'], 'player': row['player'], 'reason': reason})
        entries[identity] = evidence
        output.append(row)
    state = {'schema': 1, 'players': entries, 'coverage': {'checked_at': now.isoformat(),
             'highlights': len(output), 'with_photo': sum(bool(h.get('player_photo_url')) for h in output),
             'missing': missing, 'team_requests': requests_used, 'image_requests': image_requests}}
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = cache_path.with_suffix('.tmp')
    temporary.write_text(json.dumps(state, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    temporary.replace(cache_path)
    return output, state['coverage']
