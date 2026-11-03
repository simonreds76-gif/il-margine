"""Pinned v4 Reep release adapter; never replaces the live identity registry."""
import argparse
import csv
import gzip
import hashlib
from collections import Counter, defaultdict
from pathlib import Path
from football_identity import canonical, compatible_label, inventory, key, read, write
from football_identity_research import SUPPLEMENT

RELEASE = '2026-10-31.1'
HASHES = {
    'bridges': '0c9912fb18f9e78b118c9b2d15054138a5d2967cf6117b5e6824ade7bbcf894d',
    'entities': '4d7c27a35fd79d58e92176c736e134fad8857daa10d12b2528c3bfabbe256923',
    'redirects': 'e54d6cad14108fe0ef91fa3fc932c10abd527f7bfd1216c949006bb940966c01',
}
TARGETS = {('espn', 'person'), ('api_football', 'player'), ('opta', 'person_numeric'),
           ('sofascore', 'player')}


def build(root, downloads, output, extra=None):
    for name, digest in HASHES.items():
        with (downloads / (name + '.csv.gz')).open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != digest:
                raise ValueError('Unverified release checksum: ' + name)
    def rows(name):
        with gzip.open(downloads / (name + '.csv.gz'), 'rt', encoding='utf8', newline='') as stream:
            yield from csv.DictReader(stream)
    redirects = {r['from_id']: r['to_id'] for r in rows('redirects')}
    population = inventory(root)
    wanted = population['entities']
    for row in extra or []:
        k = key('fotmob', 'person', row['id'])
        if k not in wanted:
            wanted[k] = {'names': [row['name']]}
    found = defaultdict(list)
    for row in rows('bridges'):
        k = key(row['provider'], row['namespace'], row['external_id'])
        if k in wanted:
            found[k].append(row)
    selected = {canonical(r['reep_id'], redirects) for rr in found.values() for r in rr}
    selected.discard(None)
    entities = {r['reep_id']: r for r in rows('entities') if r['reep_id'] in selected}
    links = defaultdict(list)
    target_keys = set()
    for row in rows('bridges'):
        rid = canonical(row['reep_id'], redirects)
        if rid in selected and (row['provider'], row['namespace']) in TARGETS:
            links[rid].append(row)
            target_keys.add(key(row['provider'], row['namespace'], row['external_id']))
    owners = defaultdict(set)
    for row in rows('bridges'):
        k = key(row['provider'], row['namespace'], row['external_id'])
        if k in target_keys:
            owners[k].add(canonical(row['reep_id'], redirects))
    out = {}
    for k, local in wanted.items():
        rr = found[k]
        ids = {canonical(r['reep_id'], redirects) for r in rr}
        rid = next(iter(ids)) if len(ids) == 1 else None
        record = entities.get(rid, {})
        status = 'linked'
        if not rr:
            status = 'missing_source_id'
        elif None in ids:
            status = 'withdrawn_or_inactive_source'
        elif len(ids) != 1:
            status = 'ambiguous_source'
        elif record.get('entity_type') != 'player' or any(r['entity_type'] != 'player' for r in rr):
            status = 'not_player_record'
        elif not compatible_label(local['names'], record.get('canonical_name')):
            status = 'name_review_required'
        entry = {'status': status, 'reep_id': rid, 'local_names': local['names'],
                 'registry_label': record.get('canonical_name'), 'targets': {}}
        grouped = defaultdict(list)
        if status == 'linked':
            for row in links[rid]:
                grouped[key(row['provider'], row['namespace'], '')].append(row)
            for target, tr in grouped.items():
                vals = {r['external_id'] for r in tr}
                ts = 'linked'
                if len(vals) != 1:
                    ts = 'ambiguous_target'
                elif any(r['entity_type'] != 'player' or owners[key(r['provider'], r['namespace'], r['external_id'])] != {rid} for r in tr):
                    ts = 'target_collision'
                entry['targets'][target] = {'status': ts, 'id': next(iter(vals)) if ts == 'linked' else None}
        out[k] = entry
    registry = {'schema_version': 1, 'release': RELEASE, 'checksums': HASHES,
                'source': 'https://data.reep.football/releases/latest.json', 'license': 'CC0-1.0',
                'purpose': 'opt-in private source comparison only; original registry and IDs unchanged',
                'input_sha256': population['input_sha256'], 'entities': out}
    write(output, registry)
    health = {'release': RELEASE, 'players': len(out), 'status': dict(Counter(r['status'] for r in out.values())),
              'targets': {p: sum(e['targets'].get(key(p, n, ''), {}).get('status') == 'linked' for e in out.values()) for p, n in TARGETS}}
    write(output.parent / 'reep-research-health.json', health)
    return health


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--downloads', type=Path, required=True)
    parser.add_argument('--extra-players', type=Path)
    args = parser.parse_args()
    print(build(args.root, args.downloads, args.root / SUPPLEMENT,
                read(args.extra_players, []) if args.extra_players else None))
