"""Recover only append-only Pinnacle evidence across concurrent Git writers.

Never force push, discard commits, or resolve code conflicts automatically.
"""
import argparse
import csv
import io
from pathlib import Path
import subprocess
import time

CAPTURE = 'data/corners-ou/pinnacle-corners-odds.csv'
BRANCH = 'golden-with-speed-insights'


def union_csv(base, local, remote):
    def parse(text):
        reader = csv.DictReader(io.StringIO(text.lstrip('\ufeff')))
        return reader.fieldnames, list(reader)
    fields, original = parse(base)
    lf, left = parse(local)
    rf, right = parse(remote)
    if not fields or fields != lf or fields != rf:
        raise ValueError('Capture schemas differ; manual review required')
    tuples = lambda rows: {tuple(r.get(k, '') for k in fields) for r in rows}
    if not tuples(original) <= tuples(left) or not tuples(original) <= tuples(right):
        raise ValueError('Capture rewrite/deletion detected; refusing automatic merge')
    identity = ['captured_at', 'league', 'match_date', 'kickoff_iso', 'home_team', 'away_team', 'line', 'side']
    if not set(identity) <= set(fields):
        raise ValueError('Capture identity fields missing')
    seen, output = {}, []
    for row in right + left:
        key = tuple(row[k] for k in identity)
        if key in seen:
            if row != seen[key]:
                raise ValueError('Conflicting price for the same capture; manual review required')
            continue
        seen[key] = row
        output.append(row)
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
    writer.writeheader()
    writer.writerows(output)
    return stream.getvalue()


def git(root, *args, check=True):
    result = subprocess.run(['git', *args], cwd=root, capture_output=True, encoding='utf-8', errors='replace', timeout=180)
    if check and result.returncode:
        raise RuntimeError(f'git {args[0]} failed: {result.stderr.strip()[:700]}')
    return result


def sync(root):
    if git(root, 'status', '--porcelain', '--untracked-files=no').stdout.strip():
        raise ValueError('Capture checkout has uncommitted edits; retained for review')
    git(root, 'fetch', 'origin', BRANCH)
    remote = 'origin/' + BRANCH
    if git(root, 'merge-base', '--is-ancestor', 'HEAD', remote, check=False).returncode == 0:
        git(root, 'merge', '--ff-only', remote)
        return
    base = git(root, 'merge-base', 'HEAD', remote).stdout.strip()
    # Inspect each unpublished commit, not merely a cancelling net diff.
    changed = set(git(root, 'log', '--format=', '--name-only', remote+'..HEAD').stdout.split())
    if changed - {CAPTURE}:
        raise ValueError('Unpublished non-capture changes require manual review: '+str(sorted(changed)))
    combined = union_csv(*(git(root, 'show', ref+':'+CAPTURE).stdout for ref in (base, 'HEAD', remote)))
    if git(root, 'merge-base', '--is-ancestor', remote, 'HEAD', check=False).returncode == 0:
        return  # Pending evidence already based on remote; publisher will retry it.
    result = git(root, 'merge', '--no-ff', '--no-commit', remote, check=False)
    try:
        conflicts = set(git(root, 'diff', '--name-only', '--diff-filter=U').stdout.splitlines())
        if conflicts - {CAPTURE} or (result.returncode and not conflicts):
            raise ValueError('Unexpected merge failure; retaining original commits')
        (root/CAPTURE).write_text(combined, encoding='utf-8', newline='')
        git(root, 'add', '--', CAPTURE)
        git(root, 'commit', '-m', 'fix: preserve concurrent Pinnacle corners captures')
    except Exception:
        git(root, 'merge', '--abort', check=False)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--publish', action='store_true')
    args = parser.parse_args()
    for attempt in range(3 if args.publish else 1):
        sync(args.root)
        if not args.publish or git(args.root, 'push', 'origin', 'HEAD:'+BRANCH, check=False).returncode == 0:
            print('Pinnacle capture history synchronized'+(' and published' if args.publish else ''))
            return
        time.sleep(3 * (attempt+1))
    raise RuntimeError('Capture publication failed after three attempts; evidence remains committed for the next run')


if __name__ == '__main__':
    main()
