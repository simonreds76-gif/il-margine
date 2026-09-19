"""Once-daily local archive refresh. Publish only validated, changed static data.

Runs after the existing OnCourt morning refresh; no web request triggers this job.
Machine configuration contains paths and public project IDs, never credentials.
"""
import argparse
import csv
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import date, datetime, timezone

BRANCH = 'codex/fair-odds-daily-pitch-20260908'
REMOTE = 'https://github.com/simonreds76-gif/il-margine.git'
SITE = 'https://ilmargine.bet'
TEAM = 'team_UgA9caW5xCBxDyssrOuTQz7S'
PROJECT = 'prj_OnvAAAzkpLa5N9uZI3Iy2mwEj6IL'
HERE = Path(__file__).resolve().parent


def run(args, cwd=None, env=None, timeout=600):
    result = subprocess.run([str(a) for a in args], cwd=cwd, env=env, capture_output=True,
                            text=True, encoding='utf-8', errors='replace', timeout=timeout,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if result.returncode:
        # Never print environment variables, authenticated headers or CLI credentials.
        raise RuntimeError(f'{Path(str(args[0])).name} failed ({result.returncode}): {result.stderr[-1800:]}')
    return result.stdout


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write_json(path, value):
    path = Path(path)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)


def fetch(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'IlMargine-ReturnAtlas/1.0'})
    with urllib.request.urlopen(request, timeout=60) as response:
        if response.status != 200:
            raise RuntimeError(f'Source returned HTTP {response.status}')
        data = response.read(30_000_001)
    if len(data) > 30_000_000:
        raise RuntimeError('Unexpectedly large archive response')
    return data


def records(index):
    players = index['players']
    return {m[0]: [m[1], players[m[2]]['id'], players[m[3]]['id'], *m[4:]] for m in index['matches']}


def validate_transition(old, new, as_of):
    """Existing prices/results cannot silently change or disappear in an automatic release."""
    previous, candidate = records(old), records(new)
    if len(candidate) != len(new['matches']):
        raise ValueError('Duplicate match ID')
    for key, value in previous.items():
        if candidate.get(key) != value:
            raise ValueError(f'Existing record changed or disappeared: {key}; review required')
    for key, value in candidate.items():
        if value[0] > as_of or value[1] == value[2] or value[5] not in [0, 1]:
            raise ValueError(f'Invalid result: {key}')
        if not all(isinstance(p, (float, int)) and 1 < p < 1001 for p in value[3:5]):
            raise ValueError(f'Invalid paired odds: {key}')
    if len(candidate) - len(previous) > 400:
        raise ValueError('More than 400 new matches; review large backfill before publication')
    return candidate != previous


def source_csv(data, year):
    text = data.decode('utf-8-sig')
    rows = list(csv.DictReader(io.StringIO(text), delimiter=';'))
    required = {'genre', 'categorie', 'date', 'match_id', 'joueur1', 'joueur2',
                'joueur1_id', 'joueur2_id', 'vainqueur_id', 'tournoi', 'tour',
                'surface', 'score', 'cote1_cloture', 'cote2_cloture'}
    if not rows or not required.issubset(rows[0]):
        raise ValueError('Odds archive is empty or its schema has changed')
    if any(not r['date'].startswith(str(year)) for r in rows):
        raise ValueError('Odds archive contains an unexpected season')
    return len(rows)


def live_version():
    html = fetch(SITE + '/return-atlas').decode('utf-8')
    match = re.search(r'/return-atlas/data/(\d{8}-[a-f0-9]{12})/index.json', html)
    if not match:
        raise RuntimeError('Cannot verify the currently published archive')
    return match.group(1)


def publish(checkout, version, status, save):
    vercel = shutil.which('vercel.cmd') or shutil.which('vercel')
    if not vercel:
        raise RuntimeError('Vercel CLI unavailable')
    sha = run(['git', 'rev-parse', 'HEAD'], checkout).strip()
    if status.get('deploymentSha') == sha and status.get('deploymentId'):
        deployment_id = status['deploymentId']
    else:
        request_path = Path(status['stateDirectory']) / 'deployment-request.json'
        write_json(request_path, {'target': 'production', 'name': 'il-margine', 'project': PROJECT,
                                 'autoAssignCustomDomains': False,
                                 'gitSource': {'type': 'github', 'repoId': '1148849644', 'ref': BRANCH, 'sha': sha}})
        response = json.loads(run([vercel, 'api', f'/v13/deployments?teamId={TEAM}', '-X', 'POST',
                                   '--input', request_path, '--raw'], checkout, timeout=120))
        deployment_id = response['id']
        status.update(deploymentId=deployment_id, deploymentSha=sha, status='building')
        save()
    deadline = time.monotonic() + 2100
    while time.monotonic() < deadline:
        deployment = json.loads(run([vercel, 'api', f'/v13/deployments/{deployment_id}?teamId={TEAM}', '--raw'], checkout, timeout=90))
        state = deployment.get('readyState') or deployment.get('status')
        if state == 'READY':
            break
        if state in ['ERROR', 'CANCELED']:
            status.pop('deploymentId', None)
            raise RuntimeError(f'Candidate deployment {state}; public alias unchanged')
        time.sleep(30)
    else:
        raise RuntimeError('Candidate build timed out; public alias unchanged')
    url = 'https://' + deployment['url']
    page = run([vercel, 'curl', '/return-atlas', '--deployment', url, '--', '--fail', '--silent'], checkout, timeout=120)
    if version not in page or re.search(r'<meta[^>]+name="robots"[^>]+content="[^"]*noindex', page, re.I):
        # Vercel protection adds noindex as a HEADER; page metadata itself must stay indexable.
        raise RuntimeError('Candidate page failed version/indexability validation')
    candidate_index = run([vercel, 'curl', f'/return-atlas/data/{version}/index.json', '--deployment', url,
                           '--', '--fail', '--silent'], checkout, timeout=120)
    if not json.loads(candidate_index).get('matches'):
        raise RuntimeError('Candidate archive unavailable')
    remote_sha = run(['git', 'ls-remote', 'origin', f'refs/heads/{BRANCH}'], checkout).split()[0]
    if remote_sha != sha:
        raise RuntimeError('Deployment branch advanced during build; refusing to promote older code')
    run([vercel, 'promote', url, '--yes'], checkout, timeout=180)
    if live_version() != version:
        raise RuntimeError('Promotion finished but public archive version has not been verified')
    status.update(status='published', publishedVersion=version, publishedAt=datetime.now(timezone.utc).isoformat(), deploymentUrl=url)
    save()


def refresh(config, dry_run=False):
    state = Path(config['stateDirectory'])
    checkout = Path(config['checkout'])
    status_path = state / 'status.json'
    status = read_json(status_path) if status_path.exists() else {}
    status.update(stateDirectory=str(state), startedAt=datetime.now(timezone.utc).isoformat(), status='checking', dryRun=dry_run)
    save = lambda: write_json(status_path, status)
    save()
    try:
        if not (checkout / '.git').exists():
            if dry_run:
                raise RuntimeError('Provision the isolated checkout before the dry run')
            run(['git', 'clone', '--filter=blob:none', '--sparse', '--single-branch', '--depth', '1', '--branch', BRANCH, REMOTE, checkout], timeout=600)
            run(['git', 'sparse-checkout', 'set', 'scripts', 'src/data', 'src/components/return-atlas', 'public/return-atlas'], checkout, timeout=600)
        if run(['git', 'status', '--porcelain', '--untracked-files=no'], checkout).strip():
            raise RuntimeError('Isolated publication checkout has uncommitted changes; preserving it for review')
        run(['git', 'pull', '--ff-only', 'origin', BRANCH], checkout, timeout=180)
        as_of = date.today().isoformat()
        current_year = date.today().year
        cache = state / 'source-cache'
        cache.mkdir(exist_ok=True)
        for year in range(2025, current_year + 1):
            target = cache / f'valuebetennis-{year}.csv'
            stamp = cache / f'{year}-checked.txt'
            if target.exists() and (year < current_year or (stamp.exists() and stamp.read_text() == as_of)):
                continue
            data = fetch(f'https://www.valuebetennis.com/datasets/valuebetennis-matchs-{year}.csv')
            source_csv(data, year)
            temporary = target.with_suffix('.tmp')
            temporary.write_bytes(data)
            temporary.replace(target)
            stamp.write_text(as_of)
        candidate = state / 'candidate'
        (candidate / 'oncourt').mkdir(parents=True, exist_ok=True)
        source = Path(config['oncourt'])
        files = [source / name for name in ['games_atp.csv', 'players_atp.csv', 'tours_atp.csv']]
        fingerprints = [(p.stat().st_size, p.stat().st_mtime_ns) for p in files]
        if any(time.time() - p.stat().st_mtime > 30 * 3600 for p in files):
            raise RuntimeError('OnCourt export is older than 30 hours; public archive retained')
        for p in files:
            shutil.copy2(p, candidate / 'oncourt' / p.name)
        if fingerprints != [(p.stat().st_size, p.stat().st_mtime_ns) for p in files]:
            raise RuntimeError('OnCourt files changed while being copied; retry after refresh completes')
        env = dict(os.environ, RETURN_ATLAS_CONFIG=config['_path'], RETURN_ATLAS_CANDIDATE=str(candidate),
                   RETURN_ATLAS_AS_OF=as_of, RETURN_ATLAS_OUTPUT_ROOT=str(candidate / 'release'))
        run([sys.executable, HERE / 'return_atlas_history.py'], env=env, timeout=600)
        preview = candidate / 'preview'
        for filename in ['portraits.mjs', 'portrait-credits.html', 'return-atlas-wordmark.png']:
            shutil.copy2(Path(config['previewAssets']) / filename, preview / filename)
        run(['node', HERE / 'build-return-atlas.mjs', preview, as_of], env=env)
        run(['node', '--test', HERE / 'tests/return-atlas.test.mjs'], env=env)
        manifest_path = Path('src/data/return-atlas-release.json')
        old_manifest = read_json(checkout / manifest_path)
        new_manifest = read_json(candidate / 'release' / manifest_path)
        old = read_json(checkout / 'public' / old_manifest['indexUrl'].lstrip('/'))
        new = read_json(candidate / 'release/public' / new_manifest['indexUrl'].lstrip('/'))
        changed = validate_transition(old, new, as_of)
        # Detect score/event edits even when the numeric return remains unchanged.
        for player in old['players']:
            old_details = read_json(checkout / 'public' / old_manifest['detailsBase'].lstrip('/') / (player['id'] + '.json'))
            new_details = read_json(candidate / 'release/public' / new_manifest['detailsBase'].lstrip('/') / (player['id'] + '.json'))
            by_id = {r[0]: r for r in new_details['matches']}
            if any(by_id.get(r[0]) != r for r in old_details['matches']):
                raise ValueError('Existing match description changed; review required')
        status.update(checkedAt=datetime.now(timezone.utc).isoformat(), matches=new_manifest['matches'],
                      through=new_manifest['through'], newMatches=new_manifest['matches'] - old_manifest['matches'])
        if dry_run:
            status.update(status='validated-dry-run', changed=changed)
            save()
            return status
        if changed:
            data_path = Path('public') / new_manifest['indexUrl'].lstrip('/').rsplit('/', 1)[0]
            shutil.copytree(candidate / 'release' / data_path, checkout / data_path, dirs_exist_ok=True)
            shutil.copy2(candidate / 'release' / manifest_path, checkout / manifest_path)
            # Only archive data and its release pointer can be staged by this job.
            run(['git', 'add', '--', data_path, manifest_path], checkout)
            run(['git', 'commit', '-m', f'data: refresh Return Atlas through {new_manifest["through"]}'], checkout)
            run(['git', 'push', 'origin', f'HEAD:{BRANCH}'], checkout, timeout=180)
        else:
            new_manifest = old_manifest
        if live_version() != new_manifest['version']:
            # Also recovers a previous successful commit whose push was interrupted.
            run(['git', 'push', 'origin', f'HEAD:{BRANCH}'], checkout, timeout=180)
            publish(checkout, new_manifest['version'], status, save)
        else:
            status.update(status='unchanged', publishedVersion=new_manifest['version'])
            save()
        return status
    except Exception as exc:
        status.update(status='failed', error=str(exc), failedAt=datetime.now(timezone.utc).isoformat())
        save()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    config = read_json(args.config)
    config['_path'] = str(Path(args.config).resolve())
    state = Path(config['stateDirectory'])
    state.mkdir(parents=True, exist_ok=True)
    # OS-owned lock releases even if Python crashes; no stale lock-file deadlock.
    import msvcrt
    with (state / 'refresh.lock').open('a+b') as lock:
        lock.seek(0)
        if not lock.read(1):
            lock.write(b'0'); lock.flush()
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            print('Return Atlas refresh already running')
            return
        result = refresh(config, args.dry_run)
        print(json.dumps({key: result.get(key) for key in ['status', 'through', 'matches', 'newMatches', 'publishedVersion']}))


if __name__ == '__main__':
    main()
