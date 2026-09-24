"""Local Pinnacle 1X2 archive and validated weekly Football Atlas publication.

No Football-Data requests, visitor-triggered work, bookmaker substitution or
in-play prices. Private provenance stays in SQLite, outside the deployed tree.
"""
import argparse
import contextlib
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import shutil
import sqlite3
import sys
import time
import unicodedata
import urllib.request

HERE = Path(__file__).resolve().parent
UTC = timezone.utc
LEAGUES = {'premier-league': (1980, 36), 'serie-a': (2436, 34),
           'la-liga': (2196, 31), 'bundesliga': (1842, 8), 'ligue-1': (2036, 11)}


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, value):
    path = Path(path)
    tmp = path.with_name(path.name + f'.{os.getpid()}.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)


def dt(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('Missing timezone')
    return result.astimezone(UTC)


def normal(name):
    return re.sub('[^a-z0-9]', '', unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode().lower())


def walk(value):
    if isinstance(value, dict):
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        if value and isinstance(value[0], int):
            yield value
        else:
            for child in value:
                yield from walk(child)


def get_json(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def database(state):
    db = sqlite3.connect(state / 'archive.sqlite', timeout=30)
    db.row_factory = sqlite3.Row
    db.executescript('''
      CREATE TABLE IF NOT EXISTS quotes (
        event TEXT, league TEXT, home TEXT, away TEXT, kickoff TEXT,
        captured TEXT, version TEXT, odds TEXT, PRIMARY KEY(event,captured));
      CREATE INDEX IF NOT EXISTS quote_fixture ON quotes(league,home,away,kickoff);
      CREATE TABLE IF NOT EXISTS results (
        id TEXT PRIMARY KEY, signature TEXT, first_seen TEXT, last_seen TEXT);
    ''')
    return db


def calendar(config, now, force=False):
    state = Path(config['stateDirectory'])
    path = state / 'calendar.json'
    if not force and path.exists():
        cached = read(path)
        if now - dt(cached['checkedAt']) < timedelta(hours=12):
            return cached['fixtures']
    aliases = read(config['aliases'])
    year = now.year if now.month >= 7 else now.year - 1
    fixtures = []
    # Include previous season briefly across rollover, so late corrections are visible.
    years = [year - 1, year] if now.month in (7, 8) else [year]
    for season_year in years:
        for league, (_, lid) in LEAGUES.items():
            season = f'{season_year}-{season_year+1}'
            url = f'https://football.goaloo.com/jsData/matchResult/json/{season}/s{lid}_en.json'
            payload = get_json(url)
            teams = {r[0]: r[1] for r in payload['TeamInfo']}
            rows = list(walk(payload['ScheduleList']))
            if len(rows) < 200:
                raise ValueError(f'Incomplete fixture calendar: {league} {season}')
            for row in rows:
                kickoff = (datetime.fromisoformat(row[3]) - timedelta(hours=8)).replace(tzinfo=UTC)
                names = [aliases.get(league, {}).get(normal(teams[row[i]])) for i in (4, 5)]
                if not all(names):
                    raise ValueError(f'Unreviewed team mapping: {league} {teams[row[4]]} / {teams[row[5]]}')
                score = re.fullmatch(r'(\d+)-(\d+)', str(row[6]))
                fixtures.append(dict(id=str(row[0]), league=league, season=season,
                                     home=names[0], away=names[1], kickoff=kickoff.isoformat(),
                                     status=row[2], score=[int(score[1]), int(score[2])] if score else None))
            time.sleep(.2)
    ids = [f['id'] for f in fixtures]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate calendar fixture IDs')
    write(path, {'checkedAt': now.isoformat(), 'fixtures': fixtures})
    return fixtures


def extract_quotes(fixtures, markets, league, aliases, captured):
    """Require root fixture, regulation time, complete same-market triplet and pre-start clock."""
    lookup = {m['id']: m for m in fixtures if m.get('type') == 'matchup' and not m.get('parentId')
              and not m.get('isLive') and m.get('status') in ('pending', 'unavailable')}
    out = []
    seen = set()
    for market in markets:
        event = lookup.get(market.get('matchupId'))
        if not event or market.get('type') != 'moneyline' or market.get('period') != 0:
            continue
        if market.get('status') != 'open' or market.get('isAlternate'):
            continue
        kickoff = dt(event['startTime'])
        if captured >= kickoff or (market.get('cutoffAt') and captured >= dt(market['cutoffAt'])):
            continue
        participants = {p.get('alignment'): p.get('name', '') for p in event.get('participants', [])}
        home, away = (aliases.get(normal(participants.get(side, ''))) for side in ('home', 'away'))
        if not home or not away or home == away:
            raise ValueError(f'Unreviewed Pinnacle team: {league} {participants}')
        raw = market.get('prices', [])
        if len(raw) != 3 or {p.get('designation') for p in raw} != {'home', 'draw', 'away'}:
            continue
        prices = {}
        for p in raw:
            n = float(p['price'])
            if not math.isfinite(n) or abs(n) < 100:
                raise ValueError('Invalid American price')
            prices[p['designation']] = 1 + (n / 100 if n > 0 else 100 / abs(n))
        odds = [prices[s] for s in ('home', 'draw', 'away')]
        if not all(1 < p < 1001 for p in odds) or not .99 <= sum(1/p for p in odds) <= 1.25:
            raise ValueError('Invalid three-way book')
        if event['id'] in seen:
            raise ValueError('Conflicting full-time market')
        seen.add(event['id'])
        out.append((str(event['id']), league, home, away, kickoff.isoformat(), captured.isoformat(),
                    str(market.get('version', '')), json.dumps(odds)))
    return out


def capture(config, force=False):
    now = datetime.now(UTC)
    state = Path(config['stateDirectory'])
    expected = calendar(config, now, force)
    aliases = read(config['aliases'])
    pin = load_module('pinnacle_source', HERE / 'pinnacle-scrape-corners.py')
    counts, problems = {}, []
    db = database(state)
    try:
        observe_results(db, expected, dt(read(state / 'calendar.json')['checkedAt']))
        for league, (lid, _) in LEAGUES.items():
            near = [f for f in expected if f['league'] == league and now < dt(f['kickoff']) <= now + timedelta(minutes=90)]
            # Off-match days have zero Pinnacle requests; --force is the installation probe.
            if not near and not force:
                counts[league] = {'due': 0, 'captured': 0}
                continue
            fixtures = pin._get(f'leagues/{lid}/matchups?withSpecials=false&brandId=0', retries=1)
            markets = pin._get(f'leagues/{lid}/markets/straight', retries=1)
            quotes = extract_quotes(fixtures, markets, league, aliases[league], datetime.now(UTC))
            with db:
                db.executemany('INSERT OR IGNORE INTO quotes VALUES (?,?,?,?,?,?,?,?)', quotes)
            counts[league] = {'due': len(near), 'captured': len(quotes)}
            for f in near:
                if dt(f['kickoff']) - now > timedelta(minutes=30):
                    continue
                if not any(q[2] == f['home'] and q[3] == f['away'] and dt(q[4]) == dt(f['kickoff']) for q in quotes):
                    problems.append(f"Missing 1X2: {league} {f['home']} v {f['away']}")
        # Detect missed near-close captures after sleep/outage, not only while games are pending.
        for f in expected:
            if dt(config['startedAt']) <= dt(f['kickoff']) < now - timedelta(minutes=5) and now - dt(f['kickoff']) < timedelta(days=2):
                if select_quote(db, f) is None:
                    problems.append(f"No pre-match price within 30m: {f['home']} v {f['away']}")
    finally:
        db.close()
    report = {'checkedAt': now.isoformat(), 'status': 'failed' if problems else 'healthy',
              'leagues': counts, 'problems': problems, 'nextKickoff': min((f['kickoff'] for f in expected if dt(f['kickoff']) > now), default=None)}
    write(state / 'capture-status.json', report)
    publication = state / 'publish-status.json'
    last_check = dt(read(publication)['checkedAt']) if publication.exists() else dt(config['startedAt'])
    if now - last_check > timedelta(days=8):
        problems.append('Weekly publisher has not completed a check in over eight days')
    if problems:
        raise ValueError('; '.join(problems[:8]))
    return report


def observe_results(db, fixtures, now):
    with db:
        for f in fixtures:
            if f['status'] != -1 or not f['score'] or dt(f['kickoff']) > now - timedelta(hours=3):
                continue
            signature = json.dumps([f['kickoff'], f['home'], f['away'], f['score']])
            prior = db.execute('SELECT * FROM results WHERE id=?', (f['id'],)).fetchone()
            first = prior['first_seen'] if prior and prior['signature'] == signature else now.isoformat()
            last = max(prior['last_seen'], now.isoformat()) if prior and prior['signature'] == signature else now.isoformat()
            db.execute('INSERT OR REPLACE INTO results VALUES (?,?,?,?)', (f['id'], signature, first, last))


def select_quote(db, fixture):
    kickoff = dt(fixture['kickoff'])
    rows = db.execute('SELECT * FROM quotes WHERE league=? AND home=? AND away=? ORDER BY captured DESC',
                      (fixture['league'], fixture['home'], fixture['away']))
    for row in rows:
        # A rescheduled fixture must acquire a fresh quote for its actual kickoff.
        if dt(row['kickoff']) == kickoff and timedelta(0) < kickoff - dt(row['captured']) <= timedelta(minutes=30):
            return json.loads(row['odds'])
    return None


def candidate(old, fixtures, db, config, now):
    new = copy.deepcopy(old)
    keys = {(r[1], old['leagues'][r[2]], old['teams'][r[4]], old['teams'][r[5]]): r for r in old['fixtures']}
    additions, issues = [], []
    for f in fixtures:
        kickoff = dt(f['kickoff'])
        if kickoff < dt(config['startedAt']) or kickoff > now - timedelta(hours=3):
            continue
        if f['status'] != -1 or not f['score']:
            if kickoff < now - timedelta(days=2) and f['status'] not in (-10, -11, -12, -14):
                issues.append(f"Unresolved result: {f['id']}")
            continue
        signature = json.dumps([f['kickoff'], f['home'], f['away'], f['score']])
        prior = db.execute('SELECT * FROM results WHERE id=?', (f['id'],)).fetchone()
        if not prior or prior['signature'] != signature:
            with db:
                db.execute('INSERT OR REPLACE INTO results VALUES (?,?,?,?)', (f['id'], signature, now.isoformat(), now.isoformat()))
            issues.append(f"Result awaiting second observation: {f['id']}")
            continue
        if dt(prior['last_seen']) - dt(prior['first_seen']) < timedelta(hours=1):
            issues.append(f"Result not stable for one hour: {f['id']}")
            continue
        odds = select_quote(db, f)
        key = (kickoff.date().isoformat(), f['league'], f['home'], f['away'])
        if key in keys:
            if keys[key][6:8] != f['score']:
                issues.append(f"Published score correction requires review: {f['id']}")
            continue
        if odds is None:
            issues.append(f"Missing verified near-close: {f['id']}")
            continue
        if f['season'] not in new['seasons']:
            new['seasons'].append(f['season'])
        if any(n not in new['teams'] for n in (f['home'], f['away'])):
            issues.append(f"New club needs crest/name review: {f['id']}")
            continue
        additions.append(['pin-' + f['id'], key[0], new['leagues'].index(f['league']), new['seasons'].index(f['season']),
                          new['teams'].index(f['home']), new['teams'].index(f['away']), *f['score'], *odds, 2])
    if issues:
        raise ValueError('; '.join(issues[:10]))
    if len(additions) > 100:
        raise ValueError('More than 100 additions: review backfill')
    new['fixtures'].extend(additions)
    new['fixtures'].sort(key=lambda r: (r[1], r[0]))
    if len({r[0] for r in new['fixtures']}) != len(new['fixtures']):
        raise ValueError('Duplicate match ID')
    return new, len(additions)


def alert(config, message):
    """Deduplicate failures for 24h; credentials never copied into config/repo/logs."""
    state = Path(config['stateDirectory'])
    for env_path in config.get('envFiles', []):
        for line in Path(env_path).read_text(encoding='utf-8-sig').splitlines():
            if '=' in line and not line.lstrip().startswith('#'):
                k, v = line.split('=', 1)
                if k.strip() in ('OPS_ALERT_TELEGRAM_BOT_TOKEN', 'OPS_ALERT_TELEGRAM_CHAT_ID'):
                    os.environ[k.strip()] = v.strip().strip('"').strip("'")
    token = os.environ.get('OPS_ALERT_TELEGRAM_BOT_TOKEN')
    chat = os.environ.get('OPS_ALERT_TELEGRAM_CHAT_ID')
    if not token or not chat:
        raise RuntimeError('Telegram failure notification credentials missing')
    stamp = state / 'last-alert.json'
    digest = hashlib.sha256(message.encode()).hexdigest()
    if stamp.exists():
        prev = read(stamp)
        if prev['digest'] == digest and datetime.now(UTC) - dt(prev['sentAt']) < timedelta(hours=24):
            return
    req = urllib.request.Request(f'https://api.telegram.org/bot{token}/sendMessage',
          data=json.dumps({'chat_id': chat, 'text': 'Football Return Atlas\n' + message[:3000]}).encode(),
          headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            if not json.load(response).get('ok'):
                raise RuntimeError('Telegram did not accept notification')
    except Exception:
        raise RuntimeError('Telegram notification failed (credentials withheld)') from None
    write(stamp, {'digest': digest, 'sentAt': datetime.now(UTC).isoformat()})


def refresh(config, dry_run=False):
    helper = load_module('atlas_publish_helpers', HERE / 'refresh-return-atlas.py')
    state, checkout = Path(config['stateDirectory']), Path(config['checkout'])
    run = helper.run
    now = datetime.now(UTC)
    fixtures = calendar(config, now, force=True)
    if run(['git', 'status', '--porcelain'], checkout).strip():
        raise ValueError('Publication checkout dirty; retained for review')
    run(['git', 'pull', '--ff-only', 'origin', helper.BRANCH], checkout)
    manifest_path = Path('src/data/football-atlas-release.json')
    manifest = read(checkout / manifest_path)
    previous_index = manifest['indexUrl']
    old = read(checkout / 'public' / manifest['indexUrl'].lstrip('/'))
    with contextlib.closing(database(state)) as db:
        observe_results(db, fixtures, now)
        new, count = candidate(old, fixtures, db, config, now)
    status = {'checkedAt': now.isoformat(), 'newMatches': count, 'status': 'validated' if dry_run else 'unchanged'}
    if dry_run:
        write(state / 'publish-status.json', status)
        return status
    if not count:
        html = helper.fetch('https://ilmargine.bet/football-atlas').decode('utf-8')
        if manifest['version'] not in html:
            # Resume an interrupted push/deployment without making another data commit.
            run(['git', 'push', 'origin', f'HEAD:{helper.BRANCH}'], checkout)
            publish(config, helper, manifest['version'], Path('public') / manifest['indexUrl'].lstrip('/'), status)
        else:
            write(state / 'publish-status.json', status)
        return status
    payload = json.dumps(new, ensure_ascii=False, separators=(',', ':')).encode()
    version = hashlib.sha256(payload).hexdigest()[:12]
    path = Path(f'public/football-atlas/index-{version}.json')
    (checkout / path).write_bytes(payload)
    priced = [r for r in new['fixtures'] if all(isinstance(p, (int, float)) and math.isfinite(p) and 1 < p < 1001 for p in r[8:11])]
    manifest.update(version=version, indexUrl='/' + path.relative_to('public').as_posix(),
                    checkedAt=now.isoformat(), through=max(r[1] for r in priced), matches=len(priced),
                    fixtures=len(new['fixtures']), bytes=len(payload), seasons=new['seasons'], previewOnly=False)
    manifest['coverage'] = {league: {season: {'eligible': sum(r[2] == li and r[3] == si for r in new['fixtures']),
                                           'priced': sum(r[2] == li and r[3] == si for r in priced)}
                          for si, season in enumerate(new['seasons'])} for li, league in enumerate(new['leagues'])}
    write(checkout / manifest_path, manifest)
    run(['node', '--experimental-strip-types', '--test', 'scripts/tests/football-atlas.test.mjs'], checkout)
    # Retain the new archive, previous pointer and the actually live version.
    live_html = helper.fetch('https://ilmargine.bet/football-atlas').decode('utf-8')
    live_paths = set(re.findall(r'/football-atlas/index-[a-f0-9]{12}\.json', live_html))
    if not live_paths:
        raise RuntimeError('Unable to identify live archive for safe retention')
    keep = live_paths | {manifest['indexUrl'], previous_index}
    deleted = []
    data_root = (checkout / 'public/football-atlas').resolve()
    for archive_path in data_root.glob('index-*.json'):
        if re.fullmatch(r'index-[a-f0-9]{12}\.json', archive_path.name) and '/football-atlas/' + archive_path.name not in keep:
            if archive_path.resolve().parent != data_root:
                raise RuntimeError('Archive retention path escaped data directory')
            relative = archive_path.relative_to(checkout.resolve()).as_posix()
            run(['git', 'rm', '--', relative], checkout)
            deleted.append(relative)
    run(['git', 'add', '--', path, manifest_path], checkout)
    staged = run(['git', 'diff', '--cached', '--name-only'], checkout).splitlines()
    if set(staged) != {path.as_posix(), manifest_path.as_posix(), *deleted}:
        raise ValueError('Unexpected staged files')
    run(['git', 'commit', '-m', f'data: refresh Football Atlas through {manifest["through"]}'], checkout)
    run(['git', 'push', 'origin', f'HEAD:{helper.BRANCH}'], checkout)
    status.update(status='committed', version=version)
    write(state / 'publish-status.json', status)
    publish(config, helper, version, path, status)
    return status


def publish(config, helper, version, path, status):
    checkout, state = Path(config['checkout']), Path(config['stateDirectory'])
    run = helper.run
    vercel = shutil.which('vercel.cmd') or shutil.which('vercel')
    if not vercel:
        raise RuntimeError('Vercel CLI unavailable')
    (checkout / '.vercel').mkdir(exist_ok=True)
    write(checkout / '.vercel/project.json', {'projectId': helper.PROJECT, 'orgId': helper.TEAM, 'projectName': 'il-margine'})
    def api(route, body=None):
        args = [vercel, 'api', route + ('&' if '?' in route else '?') + 'teamId=' + helper.TEAM, '--raw']
        if body is not None:
            request = state / 'deploy-request.json'
            write(request, body)
            args += ['-X', 'POST', '--input', request]
        return json.loads(run(args, checkout, timeout=120))
    before = api('/v4/aliases/ilmargine.bet')['deploymentId']
    sha = run(['git', 'rev-parse', 'HEAD'], checkout).strip()
    prior_path = state / 'deployment-state.json'
    prior = read(prior_path) if prior_path.exists() else {}
    if prior.get('sha') == sha and prior.get('id'):
        deployment = api('/v13/deployments/' + prior['id'])
        if deployment.get('readyState') in ('ERROR', 'CANCELED'):
            raise RuntimeError('Previous candidate build failed; review before creating another deployment')
    else:
        deployment = api('/v13/deployments', {'target': 'production', 'name': 'il-margine', 'project': helper.PROJECT,
                          'autoAssignCustomDomains': False, 'gitSource': {'type': 'github', 'repoId': '1148849644', 'ref': helper.BRANCH, 'sha': sha}})
        write(prior_path, {'sha': sha, 'id': deployment['id']})
    status.update(deploymentId=deployment['id'], status='building')
    write(state / 'publish-status.json', status)
    deadline = time.monotonic() + 1800
    while deployment.get('readyState') != 'READY':
        if deployment.get('readyState') in ('ERROR', 'CANCELED') or time.monotonic() > deadline:
            raise RuntimeError('Candidate build failed/timed out; live release retained')
        time.sleep(30)
        deployment = api('/v13/deployments/' + deployment['id'])
    url = 'https://' + deployment['url']
    page = run([vercel, 'curl', '/football-atlas', '--deployment', url, '--', '--fail', '--silent'], checkout)
    if version not in page or re.search(r'<meta[^>]+name="robots"[^>]+content="[^"]*noindex', page, re.I):
        raise ValueError('Candidate metadata/archive pointer failed validation')
    archive = run([vercel, 'curl', '/' + path.relative_to('public').as_posix(), '--deployment', url, '--', '--fail', '--silent'], checkout)
    if json.loads(archive) != read(checkout / path):
        raise ValueError('Deployed archive differs from validated candidate')
    if api('/v4/aliases/ilmargine.bet')['deploymentId'] != before or run(['git', 'ls-remote', 'origin', 'refs/heads/' + helper.BRANCH], checkout).split()[0] != sha:
        raise RuntimeError('Another release advanced; refusing to replace newer production')
    run([vercel, 'promote', url, '--yes', '--scope', 'simones-projects-fb02b6e0'], checkout, timeout=180)
    if json.loads(helper.fetch('https://ilmargine.bet/' + path.relative_to('public').as_posix())) != read(checkout / path):
        raise RuntimeError('Live archive validation failed; investigate promotion')
    status.update(status='published', deploymentUrl=url, publishedAt=datetime.now(UTC).isoformat())
    write(state / 'publish-status.json', status)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['capture', 'publish', 'test-alert'])
    p.add_argument('--config', required=True)
    p.add_argument('--force', action='store_true')
    p.add_argument('--dry-run', action='store_true')
    args = p.parse_args()
    config = read(args.config)
    state = Path(config['stateDirectory'])
    state.mkdir(parents=True, exist_ok=True)
    import msvcrt
    with (state / (args.action + '.lock')).open('a+b') as lock:
        lock.seek(0)
        if not lock.read(1):
            lock.write(b'0'); lock.flush()
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            print('Football Atlas updater already running'); return
        try:
            if args.action == 'capture':
                result = capture(config, args.force)
            elif args.action == 'publish':
                result = refresh(config, args.dry_run)
            else:
                alert(config, 'Notification test: Football Atlas failure alerts are connected.')
                result = {'status': 'alert-sent'}
            print(json.dumps(result))
        except Exception as exc:
            message = f'{args.action} failed: {type(exc).__name__}: {str(exc)[:1800]}'
            write(state / (args.action + '-status.json'), {'status': 'failed', 'checkedAt': datetime.now(UTC).isoformat(), 'error': message})
            try:
                alert(config, message + '\nThe last published archive has been retained unless promotion already completed.')
            except Exception as alert_error:
                print(str(alert_error), file=sys.stderr)
            print(message, file=sys.stderr)
            raise SystemExit(1)


if __name__ == '__main__':
    main()
