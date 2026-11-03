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
import requests

ROOT = Path(__file__).resolve().parents[1]
BRANCH = 'codex/fair-odds-daily-pitch-20260908'
TEAM = 'team_UgA9caW5xCBxDyssrOuTQz7S'
PROJECT = 'prj_OnvAAAzkpLa5N9uZI3Iy2mwEj6IL'
DATA = 'src/data/penalty-news.json'
CHECKPOINT = 'data/penalty-news/capture-state.json'
PUBLICATION_PREFIX = 'codex/penalty-news-publish-'


class GitFailure(RuntimeError):
    def __init__(self, reason, code):
        self.reason = reason
        super().__init__(f'git failed: {reason} (exit {code}); captured evidence retained')


def git_failure_reason(message):
    """Return an allowlisted diagnosis, never credential-bearing CLI output."""
    message = message.lower()
    if any(s in message for s in ('authentication failed', 'permission denied', 'error: 403', 'error: 401', 'protected branch', 'gh006', 'gh013')):
        return 'authentication_or_permission'
    if any(s in message for s in ('non-fast-forward', 'fetch first', 'cannot lock ref', 'stale info')):
        return 'branch_advanced'
    if any(s in message for s in ('timed out', 'could not resolve', 'connection reset', 'remote end hung up', 'error: 502', 'error: 503', 'error: 504')):
        return 'transport'
    return 'unclassified'


def run(*args, timeout=120, env=None, input_text=None):
    result = subprocess.run([str(v) for v in args], cwd=ROOT, capture_output=True, text=True, timeout=timeout, env=env, input=input_text)
    if result.returncode:
        if Path(str(args[0])).stem == 'git':
            raise GitFailure(git_failure_reason(result.stdout + result.stderr), result.returncode)
        # CLI errors may echo configuration; retain only the command name and code.
        raise RuntimeError(f'{Path(str(args[0])).name} exited {result.returncode}')
    return result.stdout.strip()


def capture_push(base, state):
    """Preserve a news-only commit across concurrent, unrelated branch writes.

    Never force-push, replay the collector or overwrite concurrent news edits.
    Build Git objects on the remote tree; leave the checkout and index alone.
    """
    captured = run('git', 'rev-parse', 'HEAD')
    paths = run('git', 'diff', '--name-only', base, captured).splitlines()
    if not paths or set(paths) - {DATA, CHECKPOINT}:
        raise RuntimeError('Capture push requires a news-only commit')
    receipt = {'captureBase': base, 'captureSha': captured, 'attempts': []}
    target = captured

    def save(status, **extra):
        receipt.update(status=status, **extra)
        (state / 'capture-push.json').write_text(json.dumps(receipt, indent=2))

    def remote_head():
        run('git', 'fetch', '--no-tags', 'origin', 'refs/heads/' + BRANCH)
        return run('git', 'rev-parse', 'FETCH_HEAD')

    def contains(head, commit):
        return run('git', 'merge-base', head, commit) == commit

    save('pending')
    for attempt in range(1, 4):
        remote = remote_head()
        if contains(remote, target):
            save('saved', sourceSha=remote)
            return remote
        if not contains(remote, base):
            save('blocked', reason='branch_history_changed')
            raise RuntimeError('News branch history changed; captured evidence retained')
        if run('git', 'diff', '--name-only', base, remote, '--', DATA, CHECKPOINT):
            save('blocked', reason='concurrent_news_change')
            raise RuntimeError('Concurrent news data changed; refusing overwrite; captured evidence retained')
        if remote != base:
            index = state / 'capture-push.index'
            index.unlink(missing_ok=True)
            env = dict(os.environ, GIT_INDEX_FILE=str(index.resolve()))
            run('git', 'read-tree', remote, env=env)
            for path in paths:
                entry = run('git', 'ls-tree', captured, '--', path).split()
                if len(entry) != 4 or entry[0:2] != ['100644', 'blob'] or entry[3] != path:
                    raise RuntimeError('Capture must contain regular news files')
                run('git', 'update-index', '--add', '--cacheinfo', entry[0], entry[2], path, env=env)
            tree = run('git', 'write-tree', env=env)
            if set(run('git', 'diff', '--name-only', remote, tree).splitlines()) - {DATA, CHECKPOINT}:
                raise RuntimeError('Capture merge changed unrelated files')
            target = run('git', 'commit-tree', tree, '-p', remote, '-p', captured,
                         '-m', 'data: preserve penalty news across concurrent branch update')
        receipt['attempts'].append({'attempt': attempt, 'remoteSha': remote, 'targetSha': target})
        save('pushing')
        try:
            run('git', 'push', 'origin', target + ':refs/heads/' + BRANCH)
        except (GitFailure, subprocess.TimeoutExpired) as exc:
            reason = exc.reason if isinstance(exc, GitFailure) else 'transport'
            receipt['attempts'][-1]['failure'] = reason
            save('retry_pending')
            if reason not in {'branch_advanced', 'transport'}:
                save('blocked', reason=reason)
                raise
            print(f'::notice::News capture push {reason}; verifying remote before bounded retry')
        else:
            save('saved', sourceSha=target)
            return target
    # A timed-out push may already have succeeded. Check before reporting failure.
    remote = remote_head()
    if contains(remote, target):
        save('saved', sourceSha=remote)
        return remote
    save('blocked', reason='retry_limit')
    raise RuntimeError('News capture push exhausted three attempts; captured evidence retained')


def verify_current_news(source_sha):
    run('git', 'fetch', '--no-tags', 'origin', 'refs/heads/' + BRANCH)
    current = run('git', 'rev-parse', 'FETCH_HEAD')
    if run('git', 'diff', '--name-only', source_sha, current, '--', DATA, CHECKPOINT):
        raise RuntimeError('News data advanced; refusing stale promotion')


def deployment_page(vercel, url, route):
    # Match the Atlas publisher: the full URL avoids /user, which a
    # project-scoped CI token cannot access. Deployment protection stays enabled.
    return run(vercel, 'curl', url + route, '--', '--fail', '--silent')


def api_response(output):
    # Promotion returns HTTP 204. The CLI has already checked HTTP success.
    return json.loads(output) if output.strip() else {}


def vercel_read(path):
    """Bounded read recovery; never repeat a deployment/promotion mutation."""
    if not re.fullmatch(r'/v4/aliases/ilmargine\.bet|/v13/deployments/[A-Za-z0-9_-]+', path):
        raise ValueError('Unexpected Vercel read path')
    token = os.environ.get('VERCEL_TOKEN')
    if not token:
        raise RuntimeError('Existing Vercel publication credentials are unavailable')
    for attempt in range(3):
        delay = 2 ** (attempt + 1)
        try:
            response = requests.get('https://api.vercel.com' + path,
                params={'teamId': TEAM}, headers={'Authorization': 'Bearer ' + token},
                timeout=(5, 15), allow_redirects=False)
        except (requests.Timeout, requests.ConnectionError):
            failure = 'transport timeout or connection failure'
        else:
            if response.status_code == 200:
                try:
                    payload = response.json()
                except ValueError:
                    raise RuntimeError('Vercel read returned invalid JSON') from None
                if not isinstance(payload, dict):
                    raise RuntimeError('Vercel read returned an invalid object')
                return payload
            failure = 'HTTP ' + str(response.status_code)
            if response.status_code != 429 and response.status_code < 500:
                raise RuntimeError('Vercel read failed: ' + failure)
            retry_after = response.headers.get('Retry-After')
            if retry_after:
                try:
                    delay = max(delay, float(retry_after))
                except ValueError:
                    # Do not retry before an unparsed provider deadline.
                    raise RuntimeError('Vercel requested a later retry; retaining capture for the next run') from None
                if not 0 <= delay <= 30:
                    raise RuntimeError('Vercel requested a later retry; retaining capture for the next run')
        if attempt == 2:
            raise RuntimeError('Vercel read unavailable after three bounded attempts: ' + failure) from None
        print(f'::notice::Vercel read {failure}; retrying in {delay:g}s')
        time.sleep(delay)


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
    # The explicit staged build below owns publication. Prevent an additional
    # automatic Git preview for its private candidate branch, preserving every
    # other setting from the exact live deployment.
    config = json.loads(run('git', 'show', live_sha + ':vercel.json'))
    rules = config.setdefault('git', {}).get('deploymentEnabled', True)
    if rules is not False:
        if rules is True:
            rules = {}
        # A broad true wildcard would override the narrow false rule on Vercel.
        if any(value is True for value in rules.values()):
            raise RuntimeError('Review conflicting automatic deployment rules before news publication')
        rules[PUBLICATION_PREFIX + '*'] = False
        config['git']['deploymentEnabled'] = rules
        blob = run('git', 'hash-object', '-w', '--stdin', input_text=json.dumps(config, indent=2) + '\n')
        run('git', 'update-index', '--cacheinfo', '100644', blob, 'vercel.json', env=env)
    tree = run('git', 'write-tree', env=env)
    changed = set(run('git', 'diff-tree', '--name-only', '-r', live_sha + '^{tree}', tree).splitlines())
    if changed - {DATA, CHECKPOINT, 'vercel.json'}:
        raise RuntimeError('Candidate contains changes outside news data')
    return tree


def publication_candidate(live_sha, source_sha, state):
    run('git', 'fetch', '--no-tags', 'origin', live_sha)
    tree = news_tree(live_sha, source_sha, state)
    ref = PUBLICATION_PREFIX + live_sha[:12] + '-' + tree[:12]
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
    capture_base = run('git', 'rev-parse', 'HEAD')
    checkpoint = args.state / 'capture-state.json'
    if (ROOT / CHECKPOINT).exists():
        shutil.copyfile(ROOT / CHECKPOINT, checkpoint)
    run(sys.executable, 'scripts/build-penalty-news.py', '--days', '2' if args.mode == 'post-match' else str(config['lookbackDays']),
        '--mode', args.mode, '--checkpoint', checkpoint,
        '--allow-partial', '--evidence-dir', args.state, timeout=1200)
    capture = json.loads((args.state / 'report.json').read_text())
    waiting = capture.get('waitingForFinalData', [])
    print(f"Checked {capture['matchesChecked']}/{capture['matchesExpected']} fixtures; "
          f"{len(capture['errors'])} source errors; {len(capture['excluded'])} held events; "
          f"{len(waiting)} awaiting final source data")
    if waiting:
        print('::notice::Final match data pending for fixture(s) ' + ', '.join(item['matchId'] for item in waiting)
              + '. Retained for the next existing run; no live-match article published. Escalates after one hour.')
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as summary:
            summary.write(f"## Penalty News capture\n\nFixtures: {capture['matchesChecked']}/{capture['matchesExpected']}. "
                          f"Reports in archive: {capture['articles']}. Source errors: {len(capture['errors'])}. "
                          f"Held events: {len(capture['excluded'])}.\n\n"
                          f"Mode: {args.mode}. Deferred fixtures: {capture.get('deferred', 0)}. "
                          f"Pending fixture IDs: {', '.join(capture.get('pendingMatchIds', [])) or 'none'}.\n\n"
                          f"Awaiting final source data within one-hour grace: {len(waiting)}.\n\n"
                          "Hierarchy review decisions are not read by this job. Full evidence is attached as an artifact.\n")
    # Retain the exact packet even when Git or deployment publication fails.
    shutil.copyfile(ROOT / DATA, args.state / 'candidate.json')
    if args.dry_run:
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
    source_sha = capture_base
    if changed:
        run('git', 'add', '--', DATA, CHECKPOINT)
        run('git', 'commit', '-m', 'data: reconcile penalty news and completed fixtures')
        source_sha = capture_push(capture_base, args.state)
    vercel = shutil.which('vercel') or shutil.which('vercel.cmd')
    if not vercel or not os.environ.get('VERCEL_TOKEN'):
        raise RuntimeError('Existing Vercel publication credentials are unavailable')
    (ROOT / '.vercel').mkdir(exist_ok=True)
    (ROOT / '.vercel/project.json').write_text(json.dumps({'projectId': PROJECT, 'orgId': TEAM, 'projectName': 'il-margine'}))

    def api(path, *extra):
        if not extra:
            return vercel_read(path)
        return api_response(run(vercel, 'api', path + '?teamId=' + TEAM, *extra, '--raw'))

    alias = api('/v4/aliases/ilmargine.bet')['deploymentId']
    live = api('/v13/deployments/' + alias)
    live_sha = live.get('meta', {}).get('githubCommitSha')
    if not live_sha:
        raise RuntimeError('Cannot verify current production ancestry')
    data = json.loads(run('git', 'show', source_sha + ':' + DATA))
    version = data['generatedAt']
    # The collector changes this revision only when the published packet changes.
    live_page = deployment_page(vercel, 'https://' + live['url'], '/penalty-news')
    if f'data-news-version="{version}"' in live_page:
        (args.state / 'publication.json').write_text(json.dumps({'status': 'already_current', 'sha': live_sha, 'sourceSha': source_sha, 'version': version,
            'deploymentId': live['id'], 'articles': len(data['articles']), 'verifiedAt': datetime.now(timezone.utc).isoformat(),
            'pendingMatchIds': capture.get('pendingMatchIds', []), 'waitingForFinalData': waiting}, indent=2))
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
    verify_current_news(source_sha)
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
        'deploymentId': deployment['id'], 'articles': len(data['articles']), 'verifiedAt': datetime.now(timezone.utc).isoformat(),
        'pendingMatchIds': capture.get('pendingMatchIds', []), 'waitingForFinalData': waiting}, indent=2))
    print(f"Published {len(data['articles'])} verified reports")
    if capture['errors'] or capture['excluded']:
        raise RuntimeError('Verified articles published; unresolved fixtures saved for retry')


if __name__ == '__main__':
    main()
