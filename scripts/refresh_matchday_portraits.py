"""Bounded, presentation-only portrait recovery for the existing daily publisher.

Only unique exact ATP identities (or reviewed aliases) are accepted. Failed
lookups and official silhouettes never replace a previously verified image.
The private audit is independent of H2H, odds, ratings and model inputs.
"""
import hashlib
import json
import re
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from urllib.parse import quote, urlparse
import requests

ATP = 'https://www.atptour.com'
ALIASES = {
    'tai leonard sach': 'tai sach',
    'felipe meligeni rodrigues alves': 'felipe meligeni alves',
}
PLACEHOLDERS = {'f4b6ac97747d85f58b048ac7785915ce91271feac602928cb6dad25d92017130'}

def normal(value):
    value = ''.join(c for c in unicodedata.normalize('NFD', str(value or '')) if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', ' ', value.lower()).strip()

def get(url, timeout=5):
    with requests.get(url, timeout=timeout, stream=True) as response:
        response.raise_for_status()
        data = response.raw.read(1_500_001, decode_content=True)
        if len(data) > 1_500_000:
            raise ValueError('oversize_response')
        return data, response.headers.get('Content-Type', '').split(';')[0]

def exact_player(name, rows):
    key = ALIASES.get(normal(name), normal(name))
    matches = [row for row in rows if normal(str(row.get('FirstName', ''))+' '+str(row.get('LastName', ''))) == key]
    return matches[0] if len(matches) == 1 and re.fullmatch(r'[A-Za-z0-9]{4}', str(matches[0].get('PlayerId', ''))) else None

def valid_image(data, mime, placeholders):
    # The official 300x300 silhouette returns HTTP 200, just like a real photo.
    return (mime in ('image/png', 'image/jpeg', 'image/webp') and 7000 < len(data) <= 1_500_000
            and (data.startswith(b'\x89PNG\r\n\x1a\n') or data.startswith(b'\xff\xd8\xff') or data.startswith(b'RIFF'))
            and hashlib.sha256(data).hexdigest() not in placeholders)

def recover(name, placeholders, fetch=get):
    query = ALIASES.get(normal(name), normal(name)).split()[-1]
    search = ATP + '/en/-/www/players/find/byname/' + quote(query) + '/en'
    raw, _ = fetch(search)
    player = exact_player(name, json.loads(raw))
    if not player:
        return None, {'name': name, 'status': 'identity_unresolved', 'source': search}
    pid = player['PlayerId'].lower()
    url = player.get('PlayerHeadshotUrl', '')
    if url.lower() != (ATP+'/-/media/alias/player-headshot/'+pid).lower():
        raise ValueError('unexpected_portrait_url')
    data, mime = fetch(url)
    if not valid_image(data, mime, placeholders):
        url = 'https://images.wimbledon.com/wide_nobg/atp'+pid+'.png'
        data, mime = fetch(url)
        if not valid_image(data, mime, placeholders):
            return None, {'name': name, 'atpId': pid, 'status': 'official_photo_unavailable', 'source': url}
    row = {'name': name, 'src': url, 'atpId': pid, 'sha256': hashlib.sha256(data).hexdigest(),
           'profile': ATP+'/en/players/'+normal(player['FirstName']+' '+player['LastName']).replace(' ', '-')+'/'+pid+'/overview'}
    return row, {'name': name, 'atpId': pid, 'status': 'verified', 'source': url}

def refresh(schedule, catalogue, previous, cache_path, overrides=(), max_players=8, fetch=get):
    now = datetime.now(timezone.utc)
    names = sorted({str(row.get(k, '')).strip() for row in schedule for k in ('player1_name','player2_name') if row.get(k)})
    known = {normal(row['name']): row for row in catalogue if row.get('src')}
    result = dict(previous or {})
    for row in overrides:
        result[normal(row['name'])] = dict(row)
    for name in names:
        alias = ALIASES.get(normal(name))
        if alias in known and normal(name) not in result:
            result[normal(name)] = {**known[alias], 'name': name, 'canonicalName': known[alias]['name']}
    cache = json.loads(cache_path.read_text(encoding='utf-8')) if cache_path.exists() else {}
    eligible = []
    for name in names:
        key = normal(name)
        if key in result or key in known:
            continue
        prior = cache.get(key, {})
        if prior.get('retryAfter', '') > now.isoformat():
            continue
        eligible.append(name)
    # Eight players / at most three public requests each, 3 workers, <=45s network
    # time under normal timeouts. A single missing player cannot block peers.
    started = time.monotonic()
    selected = eligible[:max_players]
    observations = []
    placeholders = PLACEHOLDERS
    def worker(name):
        try:
            return recover(name, placeholders, fetch)
        except Exception as exc:
            return None, {'name': name, 'status': 'source_error', 'reason': type(exc).__name__}
    with ThreadPoolExecutor(max_workers=3) as pool:
        for future in as_completed([pool.submit(worker, name) for name in selected]):
            row, observation = future.result()
            key = normal(observation['name'])
            if row:
                result[key] = row
            observation['checkedAt'] = now.isoformat()
            delay = 1 if observation['status'] == 'source_error' else 7
            observation['retryAfter'] = (now + timedelta(days=delay)).isoformat()
            cache[key] = observation
            observations.append(observation)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache, indent=2), encoding='utf-8')
    missing = [{'name': name, 'status': cache.get(normal(name), {}).get('status', 'queued')}
               for name in names if normal(name) not in known and normal(name) not in result]
    audit = {'checkedAt': now.isoformat(), 'players': len(names), 'covered': len(names)-len(missing),
             'missing': missing, 'attempted': len(selected), 'queued': len(eligible)-len(selected),
             'seconds': round(time.monotonic()-started, 2), 'observations': observations}
    return result, audit


CATALOGUE = 'public/tennis-matchup/portraits.json'

def prepare(checkout, candidate, schedule, overrides_path, *, max_players=8, fetch=get):
    """Build a small independent photo release, preserving history and last good photos."""
    target = checkout / CATALOGUE
    prior = json.loads(target.read_text(encoding='utf-8')) if target.exists() else []
    previous = {normal(row['name']): row for row in prior if row.get('src')}
    try:
        legacy = json.loads((checkout / 'src/data/tip-tennis-portraits.json').read_text(encoding='utf-8'))
        overrides = json.loads(overrides_path.read_text(encoding='utf-8')) if overrides_path.exists() else []
        result, audit = refresh(schedule, legacy, previous,
            candidate / 'matchup-private/portrait-lookup-cache.json', overrides,
            max_players=max_players, fetch=fetch)
        rows = sorted(result.values(), key=lambda row: normal(row['name']))
    except Exception as exc:
        # Photo discovery must never stop the independent archive refresh.
        rows = prior
        audit = {'checkedAt': datetime.now(timezone.utc).isoformat(),
                 'status': 'last_good_retained', 'reason': type(exc).__name__}
    audit['changed'] = sorted(prior, key=lambda row: normal(row['name'])) != rows
    audit['catalogueEntries'] = len(rows)
    output = candidate / 'release' / CATALOGUE
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(rows, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    audit_path = candidate / 'matchup-private/matchday-portrait-audit.json'
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(json.dumps(audit, indent=2), encoding='utf-8')
    return audit

def release_fingerprint(checkout):
    target = checkout / CATALOGUE
    return hashlib.sha256(target.read_bytes()).hexdigest() if target.exists() else None

def catalogue_is_live(checkout, site, fetch):
    digest = release_fingerprint(checkout)
    if not digest:
        return True
    actual = fetch(site + '/tennis-matchup/portraits.json?v=' + digest[:16], timeout=10)
    return json.loads(actual) == json.loads((checkout / CATALOGUE).read_text(encoding='utf-8'))
