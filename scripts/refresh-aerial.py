"""Bounded enrichment inside the existing football cloud publisher. No odds calls."""
from datetime import datetime, timezone, timedelta
from hashlib import sha256
import argparse
import json
import re
import time
import requests
from aerial_data import ROOT, LEAGUES, utc, read, save, build, validate
from aerial_source import extract

def page(url):
    response = requests.get(url, timeout=25)
    response.raise_for_status()  # No retry or challenge bypass, including 403/429.
    hit = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', response.text)
    if not hit:
        raise ValueError('Source page has no supported data')
    time.sleep(.5)
    return json.loads(hit.group(1))['props']['pageProps'], sha256(response.content).hexdigest()

def refresh(root=ROOT, now=None, online=True, force=False):
    now = now or datetime.now(timezone.utc)
    data = root/'data/aerial'
    calendar = read(data/'calendar.json.gz')
    health = read(data/'health.json', {})
    due = force or now-utc(calendar['observed_at']) > timedelta(hours=18)
    # A failed attempt has a persisted cooldown too, preventing hot-job retries.
    attempted = health.get('last_attempt_at')
    if due and online and (force or not attempted or now-utc(attempted) >= timedelta(hours=6)):
        health['last_attempt_at'] = now.isoformat(); save(data/'health.json', health)
        rows, evidence = [], []
        year = now.year if now.month >= 7 else now.year-1
        season = f'{year}/{year+1}'
        for lid, (_, label, count) in LEAGUES.items():
            url = f'https://www.fotmob.com/leagues/{lid}/fixtures?season={year}%2F{year+1}'
            p, digest = page(url)
            if str(p['details']['id']) != lid or p['details']['selectedSeason'] != season:
                raise ValueError('Wrong calendar identity')
            fixtures = p['fixtures']['allMatches']
            if len(fixtures) != count*(count-1) or len({str(m['id']) for m in fixtures}) != len(fixtures):
                raise ValueError('Incomplete season calendar')
            evidence.append(dict(url=url, sha256=digest))
            for m in fixtures:
                s = m['status']; normal = not s.get('cancelled') and not s.get('awarded')
                rows.append(dict(id=str(m['id']), league_id=lid, league=label, season=season,
                    date=s['utcTime'], home_id=str(m['home']['id']), away_id=str(m['away']['id']),
                    home=m['home']['name'], away=m['away']['name'], score=s.get('scoreStr'),
                    disposition='collect' if s.get('finished') and normal else 'not_completed' if not s.get('finished') and normal else 'excluded',
                    match_url='https://www.fotmob.com'+m['pageUrl']))
        calendar = dict(observed_at=now.isoformat(), fixtures=rows, evidence=evidence)
        save(data/'calendar.json.gz', calendar)
        history = read(data/'history.json.gz'); existing = {r['id'] for r in history['matches']}
        missing = sorted([r for r in rows if r['disposition']=='collect' and r['id'] not in existing], key=lambda r:r['date'])
        # Twenty results plus five calendars per refresh. Catch-up is bounded.
        for row in missing[:20]:
            url = f'https://www.fotmob.com/api/data/matchDetails?matchId={row["id"]}'
            response = requests.get(url, timeout=25); response.raise_for_status(); time.sleep(.5)
            record = extract(response.json(), row)
            record['players']=[{k:v for k,v in p.items() if k in ('id','minutes','aerials_won','aerials_attempted','headed_shots')} for p in record['players']]
            record.pop('coverage',None);record.pop('exceptions',None)
            record.update(home=row['home'], away=row['away'], league=row['league'],
                          source_url=url, source_sha256=sha256(response.content).hexdigest(), observed_at=now.isoformat())
            history['matches'].append(record)
            save(data/'history.json.gz', history)
        health.update(last_collection_at=now.isoformat(), remaining_results=max(0,len(missing)-20))
        save(data/'health.json', health)
        heights = read(data/'heights.json.gz')
        sources = read(data/'roster-sources.json', {})
        # Rotate at most eight current squads per daily collection, once per fortnight.
        due_teams = sorted((tid for tid,s in sources.items() if now-utc(s['observed_at']) >= timedelta(days=14)),
                           key=lambda tid: sources[tid]['observed_at'])[:8]
        for tid in due_teams:
            source=sources[tid]; p,digest=page(source['url'])
            team=p.get('fallback',{}).get('team-'+tid,{})
            if str(team.get('details',{}).get('id')) != tid:
                raise ValueError('Roster identity mismatch')
            groups=team.get('squad',{}).get('squad',[])
            if not groups:
                raise ValueError('Roster unavailable')
            for group in groups:
                if group.get('title')=='coach': continue
                for player in group.get('members',[]):
                    pid=str(player['id']); old=heights.get(pid,{})
                    if old.get('source_kind')=='reviewed_external': continue
                    height=player.get('height')
                    height=height if type(height) in (int,float) and 130<=height<=230 else None
                    heights[pid]=dict(id=pid,name=player['name'],height_cm=height,team_id=tid,
                        positions=player.get('positionIdsDesc'),role_group=group['title'],
                        source_url=source['url'],observed_at=now.isoformat(),source_kind='current_squad',
                        source_sha256=digest,status='reported')
            source['observed_at']=now.isoformat()
            save(data/'heights.json.gz',heights);save(data/'roster-sources.json',sources)
    payload = build(root, now)
    save(root/'public/fair-odds-lab/aerial.json', payload)
    health.update(last_build_at=now.isoformat(), fixtures=len(payload['fixtures']),
        usable_lineups=sum(f['state'] in ('expected','confirmed') for f in payload['fixtures']),
        missing_heights=sum(p['height_cm'] is None for f in payload['fixtures'] for t in f['teams'] for p in t['players']),
        exclusions=payload['exclusions'], history_through=payload['history_through'])
    save(data/'health.json', health)
    return payload

def publish(client, root=ROOT, now=None):
    now = now or datetime.now(timezone.utc)
    data = root/'data/aerial'
    try:
        payload = refresh(root, now)
        validate(payload, now)
        body = json.dumps(payload, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()
        # One atomic object contains data and its version; never a partially updated board.
        client.put('fair-odds-lab/aerial.json', body, access='public', content_type='application/json',
                   overwrite=True, cache_control_max_age=60)
        health = read(data/'health.json', {})
        health.update(last_publish_at=now.isoformat(), published_version=payload['version'], last_error=None)
        save(data/'health.json', health)
        print(f'Aerial published: {len(payload["fixtures"])} upcoming fixtures, {health["usable_lineups"]} usable lineups')
    except Exception as exc:
        health = read(data/'health.json', {})
        health.update(last_error=str(exc), failed_at=now.isoformat())
        save(data/'health.json', health)
        # Other football publishing must complete independently; failures remain visible in CI.
        print(f'::warning::Aerial refresh failed; last public snapshot retained: {exc}')
        return False
    return True

if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--offline', action='store_true'); parser.add_argument('--force',action='store_true')
    args = parser.parse_args()
    result = refresh(online=not args.offline,force=args.force)
    print(json.dumps({k:result[k] for k in ('version','generated_at','history_through','history_matches')}))
    print('Upcoming fixtures:',len(result['fixtures']))

