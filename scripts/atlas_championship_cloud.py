"""Durable independent Championship extension; never publishes the website."""
import argparse
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import requests
from atlas_championship_state import read, encoded, atomic, validate
from atlas_championship_weekly import run, ROOT, FORWARD_START

KEY = 'football_atlas_championship_extension_v1'
TABLE = 'goalscorer_live_snapshot'


def check(payload):
    if (payload.get('schema'), payload.get('competition'), payload.get('scope'), payload.get('startDate')) != (1, 'championship', 'regular-season', FORWARD_START):
        raise ValueError('Wrong extension checkpoint')
    validate(payload['rows'])
    if any(r['date'] < FORWARD_START or r.get('provenance') != 'goaloo+fotmob+oddspapi' for r in payload['rows']):
        raise ValueError('Only independently collected forward records may be uploaded')
    if 'seedSha256' in payload or 'shadowedSeedRows' in payload:
        raise ValueError('Private seed metadata is not part of this checkpoint')
    return payload


class Store:
    def __init__(self):
        base = (os.environ.get('NEXT_PUBLIC_SUPABASE_URL') or '').rstrip('/')
        token = os.environ.get('SUPABASE_SERVICE_ROLE_KEY')
        if not base.startswith('https://') or not token:
            raise ValueError('Existing snapshot credentials missing')
        self.url = base + '/rest/v1/' + TABLE
        self.headers = {'apikey': token, 'Authorization': 'Bearer ' + token, 'Prefer': 'return=representation'}

    def request(self, method, **kwargs):
        try:
            r = requests.request(method, self.url, headers=self.headers, timeout=(10,45), **kwargs)
            if not r.ok:
                raise ValueError('Extension checkpoint HTTP ' + str(r.status_code))
            return r.json()
        except requests.RequestException:
            raise ValueError('Extension checkpoint request failed; no replacement permitted') from None

    def get(self):
        rows = self.request('GET', params={'snapshot_key': 'eq.' + KEY, 'select': 'updated_at,payload'})
        if len(rows) > 1:
            raise ValueError('Ambiguous extension checkpoint')
        if rows:
            check(rows[0]['payload'])
        return rows[0] if rows else None

    def put(self, payload, previous):
        check(payload)
        if previous and encoded(previous['payload']) == encoded(payload):
            return 'unchanged'
        row = {'snapshot_key': KEY, 'updated_at': datetime.now(timezone.utc).isoformat(), 'payload': payload}
        if previous:
            result = self.request('PATCH', params={'snapshot_key': 'eq.' + KEY, 'updated_at': 'eq.' + previous['updated_at']}, json=row)
        else:
            # No upsert: a concurrent first writer must cause a conflict, not overwrite.
            result = self.request('POST', json=row)
        if len(result) != 1:
            raise ValueError('Concurrent checkpoint writer; rerun from latest state')
        verified = self.get()
        if not verified or encoded(verified['payload']) != encoded(payload):
            raise ValueError('Extension read-back mismatch')
        return 'verified'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--state', type=Path, required=True)
    p.add_argument('--dry-run', action='store_true')
    a = p.parse_args()
    store = Store()
    previous = store.get()  # A network/read error must never fall back to an empty ledger.
    seed = check(read(ROOT/'data/football-atlas/extensions/championship-bootstrap.json'))
    payload = previous['payload'] if previous else seed
    atomic(a.state/'ledger.json', payload)
    report = run(a.state, a.state/'evidence', datetime.now(timezone.utc), capture=True)
    candidate = check(read(a.state/'ledger.json'))
    if candidate.get('conflicts'):
        raise ValueError('Result/identity conflict: durable last-good checkpoint retained')
    report['database'] = 'dry-run' if a.dry_run else store.put(candidate, previous)
    report['snapshotKey'] = KEY
    report['checkpointSha256'] = hashlib.sha256(encoded(candidate)).hexdigest()
    atomic(a.state/'cloud-report.json', report)
    print({k:report[k] for k in ('newResults','newPriced','pending','through','database','checkpointSha256')})


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        raise SystemExit(str(exc) if isinstance(exc, ValueError) else type(exc).__name__) from None
