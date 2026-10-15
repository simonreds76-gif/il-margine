"""Build a compact, pinned Reep sidecar from previously downloaded CC0 CSVs.

No network or dependencies. All publication is separate. Checksums must be
explicitly reviewed when changing release; never silently accept a new dump.
"""
import argparse
import csv
import gzip
import hashlib
from collections import defaultdict
from pathlib import Path
from football_identity import REGISTRY, audit, canonical, compatible_label, inventory, key, write

RELEASE = '20261005T180536Z'
CHECKSUMS = {
    'bridges': 'ccfe36b94612890102d89159b82eb92f22245151b4b7ebbf2859e38f069d7731',
    'players': '3c8f1994e82b0eeab5e309826d44409f66648628c243ef97833a47711a9b6851',
    'redirects': '1c78dad87f4d1be2714343c5d62a498cdf7c13b98d50cce6cbdc2660bb83d724',
}


def build(root, downloads, destination):
    for name, expected in CHECKSUMS.items():
        with (downloads / (name + '.csv.gz')).open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != expected:
                raise ValueError('Checksum mismatch: ' + name)

    def rows(name):
        with gzip.open(downloads / (name + '.csv.gz'), 'rt', encoding='utf-8', newline='') as stream:
            yield from csv.DictReader(stream)

    redirects = {r['from_id']: r['to_id'] for r in rows('redirects')}
    population = inventory(root)
    wanted = population['entities']
    found = defaultdict(list)
    for row in rows('bridges'):
        k = key(row['provider'], row['namespace'], row['external_id'])
        if k in wanted:
            found[k].append(row)
    print('Source ID scan complete', flush=True)
    selected = {canonical(r['reep_id'], redirects) for rr in found.values() for r in rr}
    selected.discard(None)
    players = {r['reep_id']: r for r in rows('players') if r['reep_id'] in selected}
    bridges = defaultdict(list)
    target_keys = set()
    for row in rows('bridges'):
        rid = canonical(row['reep_id'], redirects)
        if rid in selected:
            bridges[rid].append(row)
            target_keys.add(key(row['provider'], row['namespace'], row['external_id']))
    print('Target provider scan complete', flush=True)
    # Global check, including entities outside our population, catches a target
    # ID that the registry also assigns to someone else. No full in-memory dump.
    owners = defaultdict(set)
    for row in rows('bridges'):
        k = key(row['provider'], row['namespace'], row['external_id'])
        if k in target_keys:
            owners[k].add(canonical(row['reep_id'], redirects))
    print('Global collision scan complete', flush=True)
    entities = {}
    for k, local in wanted.items():
        rr = found[k]
        ids = {canonical(r['reep_id'], redirects) for r in rr}
        status = 'linked'
        if not rr:
            status = 'missing_source_id'
        elif None in ids or any(r.get('upstream_status') for r in rr):
            status = 'withdrawn_or_inactive_source'
        elif len(ids) != 1:
            status = 'ambiguous_source'
        rid = next(iter(ids)) if len(ids) == 1 else None
        record = players.get(rid)
        if status == 'linked' and (not record or record.get('status') != 'active'):
            status = 'not_active_player_record'
        if status == 'linked' and not compatible_label(local['names'], record['label']):
            status = 'name_review_required'
        entry = dict(status=status, reep_id=rid, local_names=local['names'],
                     registry_label=record.get('label') if record else None, targets={})
        grouped = defaultdict(list)
        if status == 'linked':
            for row in bridges[rid]:
                grouped[key(row['provider'], row['namespace'], '')].append(row)
            for target, rows_ in grouped.items():
                active = [r for r in rows_ if not r.get('upstream_status')]
                vals = {r['external_id'] for r in active}
                target_status = 'linked'
                if not active:
                    target_status = 'inactive_target'
                elif len(vals) != 1:
                    target_status = 'ambiguous_target'
                elif any(owners[key(r['provider'], r['namespace'], r['external_id'])] != {rid} for r in active):
                    target_status = 'target_collision'
                entry['targets'][target] = {'status': target_status, 'id': next(iter(vals)) if target_status == 'linked' else None}
        entities[k] = entry
    registry = {'schema_version': 1, 'release': RELEASE, 'source': 'https://reep.football/data/',
                'license': 'CC0-1.0', 'checksums': CHECKSUMS,
                'input_sha256': population['input_sha256'], 'entities': entities,
                'purpose': 'advisory identity lookup only; no model or statistical inputs'}
    write(destination, registry)
    report = audit(root, registry)
    write(destination.parent / 'identity-health.json', report)
    print({k: v['status'] for k, v in report['scopes'].items()}, flush=True)
    return registry


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--downloads', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    build(args.root, args.downloads, args.output or args.root / REGISTRY)
