"""Data-only Atlas releases on the exact current production commit."""
import hashlib
import json
from pathlib import Path
import re
import shutil


def production_commit(deployment):
    meta = deployment.get('meta') or {}
    values = [meta.get(k) for k in ('githubCommitSha', 'gitCommitSha') if meta.get(k)]
    if (deployment.get('gitSource') or {}).get('sha'):
        values.append(deployment['gitSource']['sha'])
    if not values or any(not isinstance(s, str) or not re.fullmatch(r'[a-f0-9]{40}', s) for s in values):
        raise RuntimeError('Cannot establish the exact production commit')
    if len(set(values)) != 1:
        raise RuntimeError('Conflicting production commit metadata')
    return values[0]


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def football_paths(root):
    paths = set()
    def add_url(url, prefix):
        if not isinstance(url, str) or not url.startswith(prefix) or not url.endswith('.json'):
            raise RuntimeError('Invalid Atlas publication path')
        path = Path('public') / url.lstrip('/')
        if '..' in path.parts or '\\' in url or not (root / path).is_file():
            raise RuntimeError('Missing or unsafe Atlas publication file')
        paths.add(path)
        return read(root / path)
    for name, prefix in [('football-atlas-release.json','/football-atlas/'),('manager-atlas-release.json','/manager-atlas/')]:
        p = Path('src/data') / name; paths.add(p)
        add_url(read(root / p)['indexUrl'], prefix)
    board_path = Path('src/data/atlas-fixtures.json'); paths.add(board_path)
    board = read(root / board_path)
    add_url(board['evidenceUrl'], '/football-atlas/fixtures/')
    ext = Path('src/data/covered-leagues-release.json')
    if (root / ext).exists():
        paths.add(ext); data = read(root / ext)
        if data['baseBoardVersion'] != board['version']:
            raise RuntimeError('Extension does not match fixture board')
        add_url(data['historyUrl'], '/football-atlas/covered/')
        covered = add_url(data['boardUrl'], '/football-atlas/covered/')
        add_url(covered['evidenceUrl'], '/football-atlas/covered/')
    return sorted(paths)


def preserve_history(live, source):
    for name, rows_key in [('football-atlas-release.json','fixtures'),('manager-atlas-release.json','rows')]:
        def archive(root):
            manifest = read(root / 'src/data' / name)
            return read(root / 'public' / manifest['indexUrl'].lstrip('/'))
        old, new = archive(live), archive(source)
        # Append-only public histories: no result, price, assignment or indexed
        # identity may disappear/change when a publisher branch trails the site.
        encode = lambda row: json.dumps(row, sort_keys=True, ensure_ascii=False)
        if not set(map(encode, old[rows_key])).issubset(set(map(encode, new[rows_key]))):
            raise RuntimeError('Current production history would change: ' + name)
        for key in ('teams', 'leagues', 'seasons', 'managers'):
            if key not in old:
                continue
            def identity(row):
                return row.get('id') if isinstance(row, dict) else row
            prior = list(map(identity, old[key])); candidate = list(map(identity, new[key]))
            if candidate[:len(prior)] != prior:
                raise RuntimeError('Current production identity ordering would change: ' + key)


def stage_football(source, state, deployment, run, *, worktree_root=None):
    source, state = Path(source), Path(state)
    base = production_commit(deployment)
    paths = football_paths(source)
    digest = hashlib.sha256(b''.join(p.as_posix().encode() + b'\0' + (source / p).read_bytes() for p in paths)).hexdigest()[:12]
    branch = f'codex/football-atlas-release-{base[:12]}-{digest}'
    root = Path(worktree_root) if worktree_root else state / 'production-releases'
    root.mkdir(parents=True, exist_ok=True)
    target = root / f'{base[:12]}-{digest}'
    run(['git','fetch','--no-tags','origin',base],source)
    if not target.exists():
        run(['git','worktree','add','--detach',target,base],source)
    if run(['git','status','--porcelain','--untracked-files=no'],target).strip():
        raise RuntimeError('Production release checkout is dirty')
    # Use independent sparse configuration, never mutate a shared checkout.
    if run(['git','config','--bool','--default','false','--get','core.sparseCheckout'],target).strip() == 'true':
        if run(['git','config','--bool','--default','false','--get','extensions.worktreeConfig'],source).strip() != 'true':
            raise RuntimeError('Independent worktree configuration required')
        run(['git','sparse-checkout','add','public'],target)
    preserve_history(target, source)
    for path in paths:
        (target / path).parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source / path, target / path)
    run(['git','add','--',*paths],target)
    changed = set(run(['git','diff','--name-only',base],target).splitlines())
    if not changed.issubset({p.as_posix() for p in paths}):
        raise RuntimeError('Unrelated file entered Football Atlas release')
    if run(['git','diff','--cached','--name-only'],target).strip():
        run(['git','-c','user.name=Il Margine Publisher','-c','user.email=partners@ilmargine.bet',
             'commit','-m','data: refresh validated football archives on current live site'],target)
    sha = run(['git','rev-parse','HEAD'],target).strip()
    run(['git','push','origin',f'HEAD:refs/heads/{branch}'],target)
    return target, branch, base, sha
