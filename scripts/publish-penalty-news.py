"""Daily news publication, independent of hierarchy review decisions.

One data-only commit/build per changed batch, never per article or visitor.
Production promotion follows the existing Atlas candidate/verify/promote flow.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
BRANCH = 'codex/fair-odds-daily-pitch-20260908'
TEAM = 'team_UgA9caW5xCBxDyssrOuTQz7S'
PROJECT = 'prj_OnvAAAzkpLa5N9uZI3Iy2mwEj6IL'
DATA = 'src/data/penalty-news.json'
CHECKPOINT = 'data/penalty-news/capture-state.json'


def run(*args, timeout=120, env=None):
    result = subprocess.run([str(v) for v in args], cwd=ROOT, capture_output=True, text=True, timeout=timeout, env=env)
    if result.returncode:
        # CLI errors may echo configuration; retain only the command name and code.
        raise RuntimeError(f'{Path(str(args[0])).name} exited {result.returncode}')
    return result.stdout.strip()


def deployment_page(vercel, url, route):
    # Match the Atlas publisher: the full URL avoids /user, which a
    # project-scoped CI token cannot access. Deployment protection stays enabled.
    return run(vercel, 'curl', url + route, '--', '--fail', '--silent')


def api_response(output):
    # Promotion returns HTTP 204. The CLI has already checked HTTP success.
    return json.loads(output) if output.strip() else {}


def news_tree(live_sha, source_sha, state):
    """Overlay only validated news files onto the exact production tree."""
    live_data = json.loads(run('git', 'show', live_sha + ':' + DATA))
    source_data = json.loads(run('git', 'show', source_sha + ':' + DATA))
    live_articles = {a['id']: a for a in live_data['articles']}
    source_articles = {a['id']: a for a in source_data['articles']}
    if (source_data['generatedAt'] < live_data['generatedAt'] or
            set(live_articles) - set(source_articles) or
            any(source_articles[k].get('updatedAt', '') < a.get('updatedAt', '') for k, a in live_articles.items())):
        raise RuntimeError('News source would remove or regress published reports')
    index = state / 'publication.index'
    index.unlink(missing_ok=True)
    env = dict(os.environ, GIT_INDEX_FILE=str(index.resolve()))
    run('git', 'read-tree', live_sha, env=env)
    for path in (DATA, CHECKPOINT):
        entry = run('git', 'ls-tree', source_sha, '--', path).split()
        if len(entry) != 4 or entry[0] != '100644' or entry[1] != 'blob' or entry[3] != path:
            raise RuntimeError('Expected a regular news data file')
        run('git', 'update-index', '--add', '--cacheinfo', entry[0], entry[2], path, env=env)
    tree = run('git', 'write-tree', env=env)
    changed = set(run('git', 'diff-tree', '--name-only', '-r', live_sha + '^{tree}', tree).splitlines())
    if changed - {DATA, CHECKPOINT}:
        raise RuntimeError('Candidate contains changes outside news data')
    return tree


def publication_candidate(live_sha, source_sha, state):
    run('git', 'fetch', '--no-tags', 'origin', live_sha)
    tree = news_tree(live_sha, source_sha, state)
    ref = 'codex/penalty-news-' + live_sha[:12] + '-' + tree[:12]
    existing = run('git', 'ls-remote', 'origin', 'refs/heads/' + ref)
    if existing:
        sha = existing.split()[0]
        run('git', 'fetch', '--no-tags', 'origin', ref)
        if run('git', 'show', '-s', '--format=%P', sha) != live_sha or run('git', 'rev-parse', sha + '^{tree}') != tree:
            raise RuntimeError('Existing publication candidate does not match live parent and news tree')
    else:
        sha = run('git', 'commit-tree', tree, '-p', live_sha, '-m', 'data: publish verified penalty news on current live site')
        run('git', 'push', 'origin', sha + ':refs/heads/' + ref)
    return sha, ref


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--mode', choices=['daily', 'post-match'], default='daily')
    args = parser.parse_args()
    args.state = args.state.resolve()
    args.state.mkdir(parents=True, exist_ok=True)
    config = json.loads((ROOT / 'config/penalty-news-publication.json').read_text())
    if config.get('enabled') is not True and not args.dry_run:
        print('Preview only; public publication disabled')
        return
    if run('git', 'status', '--porcelain', '--untracked-files=no'):
        raise RuntimeError('Checkout has unrelated tracked changes')
    if not args.dry_run and run('git', 'rev-parse', '--abbrev-ref', 'HEAD') != BRANCH:
        raise RuntimeError('Publication requires the production branch')
    checkpoint = args.state / 'capture-state.json'
    if (ROOT / CHECKPOINT).exists():
        shutil.copyfile(ROOT / CHECKPOINT, checkpoint)
    run(sys.executable, 'scripts/build-penalty-news.py', '--days', '2' if args.mode == 'post-match' else str(config['lookbackDays']),
        '--mode', args.mode, '--checkpoint', checkpoint,
        '--allow-partial', '--evidence-dir', args.state, timeout=1200)
    capture = json.loads((args.state / 'report.json').read_text())
    print(f"Checked {capture['matchesChecked']}/{capture['matchesExpected']} fixtures; "
          f"{len(capture['errors'])} source errors; {len(capture['excluded'])} held events")
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as summary:
            summary.write(f"## Penalty News capture\n\nFixtures: {capture['matchesChecked']}/{capture['matchesExpected']}. "
                          f"Reports in archive: {capture['articles']}. Source errors: {len(capture['errors'])}. "
                          f"Held events: {len(capture['excluded'])}.\n\n"
                          f"Mode: {args.mode}. Deferred fixtures: {capture.get('deferred', 0)}. "
                          f"Pending fixture IDs: {', '.join(capture.get('pendingMatchIds', [])) or 'none'}.\n\n"
                          "Hierarchy review decisions are not read by this job. Full evidence is attached as an artifact.\n")
    if args.dry_run:
        shutil.copyfile(ROOT / DATA, args.state / 'candidate.json')
        print('Dry run only; no commit or deployment')
        if capture['errors'] or capture['excluded']:
            raise RuntimeError('Capture incomplete; inspect retained evidence and pending fixtures')
        return
    (ROOT / CHECKPOINT).parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(checkpoint, ROOT / CHECKPOINT)
    changed = run('git', 'diff', '--name-only').splitlines()
    if set(changed) - {DATA, CHECKPOINT} or run('git', 'diff', '--cached', '--name-only'):
        raise RuntimeError('Only validated news data and its capture checkpoint may be committed')
    # Capture/retry state must survive even if the deployment service is down.
    # Git auto-deployment is disabled for this branch; this is not publication.
    if changed:
        run('git', 'add', '--', DATA, CHECKPOINT)
        run('git', 'commit', '-m', 'data: reconcile penalty news and completed fixtures')
        run('git', 'push', 'origin', 'HEAD:' + BRANCH)
    vercel = shutil.which('vercel') or shutil.which('vercel.cmd')
    if not vercel or not os.environ.get('VERCEL_TOKEN'):
        raise RuntimeError('Existing Vercel publication credentials are unavailable')
    (ROOT / '.vercel').mkdir(exist_ok=True)
    (ROOT / '.vercel/project.json').write_text(json.dumps({'projectId': PROJECT, 'orgId': TEAM, 'projectName': 'il-margine'}))

    def api(path, *extra):
        return api_response(run(vercel, 'api', path + '?teamId=' + TEAM, *extra, '--raw'))

    alias = api('/v4/aliases/ilmargine.bet')['deploymentId']
    live = api('/v13/deployments/' + alias)
    live_sha = live.get('meta', {}).get('githubCommitSha')
    if not live_sha:
        raise RuntimeError('Cannot verify current production ancestry')
    source_sha = run('git', 'rev-parse', 'HEAD')
    data = json.loads((ROOT / DATA).read_text())
    version = data['generatedAt']
    # The collector changes this revision only when the published packet changes.
    live_page = deployment_page(vercel, 'https://' + live['url'], '/penalty-news')
    if f'data-news-version="{version}"' in live_page:
        (args.state / 'publication.json').write_text(json.dumps({'status': 'already_current', 'sha': live_sha, 'sourceSha': source_sha, 'version': version,
            'deploymentId': live['id'], 'articles': len(data['articles']), 'verifiedAt': datetime.now(timezone.utc).isoformat()}, indent=2))
        print('Published news already matches; no build required')
        if capture['errors'] or capture['excluded']:
            raise RuntimeError('Capture incomplete; unresolved fixtures saved for retry')
        return
    sha, publication_ref = publication_candidate(live_sha, source_sha, args.state)
    request = args.state / 'deployment-request.json'
    request.write_text(json.dumps({'target': 'production', 'name': 'il-margine', 'project': PROJECT,
                                  'autoAssignCustomDomains': False,
                                  'gitSource': {'type': 'github', 'repoId': '1148849644', 'ref': publication_ref, 'sha': sha}}))
    deployment = api('/v13/deployments', '-X', 'POST', '--input', request)
    for _ in range(60):
        deployment = api('/v13/deployments/' + deployment['id'])
        if deployment.get('readyState') == 'READY':
            break
        if deployment.get('readyState') in ('ERROR', 'CANCELED'):
            raise RuntimeError('Candidate build failed; public alias unchanged')
        time.sleep(30)
    else:
        raise RuntimeError('Candidate build timed out; public alias unchanged')
    url = 'https://' + deployment['url']
    page = deployment_page(vercel, url, '/penalty-news')
    if f'data-news-version="{version}"' not in page or re.search(r'<meta[^>]+name="robots"[^>]+content="[^"]*noindex', page):
        raise RuntimeError('Candidate news version/indexability validation failed')
    for a in data['articles'][:3]:
        page = deployment_page(vercel, url, '/penalty-news/' + a['slug'])
        if f'data-article-id="{a["id"]}"' not in page:
            raise RuntimeError('Candidate article route failed verification')
    if run('git', 'ls-remote', 'origin', 'refs/heads/' + BRANCH).split()[0] != source_sha:
        raise RuntimeError('Production branch advanced; refusing stale promotion')
    if api('/v4/aliases/ilmargine.bet')['deploymentId'] != alias:
        raise RuntimeError('Public deployment changed; refusing stale promotion')
    # The API avoids the CLI's personal-user lookup with a project token.
    api(f'/v10/projects/{PROJECT}/promote/{deployment["id"]}', '-X', 'POST')
    deadline = time.monotonic() + 180
    while api('/v4/aliases/ilmargine.bet')['deploymentId'] != deployment['id']:
        if time.monotonic() > deadline:
            raise RuntimeError('Promotion has not been verified')
        time.sleep(5)
    (args.state / 'publication.json').write_text(json.dumps({'status': 'published', 'sha': sha, 'sourceSha': source_sha, 'liveParent': live_sha, 'version': version,
        'deploymentId': deployment['id'], 'articles': len(data['articles']), 'verifiedAt': datetime.now(timezone.utc).isoformat()}, indent=2))
    print(f"Published {len(data['articles'])} verified reports")
    if capture['errors'] or capture['excluded']:
        raise RuntimeError('Verified articles published; unresolved fixtures saved for retry')


if __name__ == '__main__':
    main()
