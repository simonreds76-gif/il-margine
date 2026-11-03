"""Keep source comparisons inside the existing server-only private snapshot.

Only the keeper_source_comparison field is touched. Skyline forecasts, results,
alert receipts and report timestamps are preserved by the existing CAS writer.
"""
import argparse
from copy import deepcopy
from pathlib import Path
from football_identity import read, write
from skyline_store import fetch, update

FIELD = 'keeper_source_comparison'
DIRECTORY = Path('data/goalkeeper-saves/source-comparison')


def merge(current, incoming):
    if incoming.get('version') != 'keeper-source-comparison-v1':
        raise ValueError('Unexpected keeper comparison version')
    if current and current.get('version') != incoming['version']:
        raise ValueError('Existing keeper comparison version conflict')
    out = deepcopy(current or {'version': incoming['version'], 'archive': {'schema_version': 1, 'fixtures': {}}, 'state': {}})
    for mid, versions in incoming['archive']['fixtures'].items():
        target = out['archive']['fixtures'].setdefault(mid, [])
        existing = {r['record_sha256']: r for r in target}
        for record in versions:
            sha = record['record_sha256']
            if sha not in existing:
                target.append(deepcopy(record)); existing[sha] = record
            elif {k:v for k,v in existing[sha].items() if k not in ('observed_at','cohort')} != {k:v for k,v in record.items() if k not in ('observed_at','cohort')}:
                raise ValueError('Conflicting immutable keeper comparison')
    for mid, row in incoming['state'].items():
        if row['checked_at'] >= out['state'].get(mid, {}).get('checked_at', ''):
            out['state'][mid] = deepcopy(row)
    if incoming['status']['generated_at'] >= out.get('status', {}).get('generated_at', ''):
        out['status'] = deepcopy(incoming['status'])
    return out


def local(root):
    directory = root / DIRECTORY
    return {'version': 'keeper-source-comparison-v1',
            'archive': read(directory/'comparisons.json.gz', {'schema_version':1,'fixtures':{}}),
            'state': read(directory/'state.json', {}), 'status': read(directory/'status.json', {})}


def restore(root):
    row = fetch(root)
    if row is None:
        raise ValueError('Existing private snapshot unavailable; refusing new public row')
    remote = row['payload'].get(FIELD)
    if not remote:
        return
    state = merge(local(root), remote)
    directory = root / DIRECTORY
    write(directory/'comparisons.json.gz', state['archive'])
    write(directory/'state.json', state['state'])
    write(directory/'status.json', state['status'])


def persist(root):
    incoming = local(root)
    if not incoming['status'].get('generated_at'):
        raise ValueError('Keeper comparison status missing')
    def change(state):
        state[FIELD] = merge(state.get(FIELD), incoming)
    update(root, change)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('restore', 'persist'))
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    (restore if args.action == 'restore' else persist)(args.root)
    print('Private keeper comparison ' + args.action + ' complete')
