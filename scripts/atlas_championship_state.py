"""Isolated Championship ledger contract and atomic local checkpoint."""
import json
import math
from pathlib import Path
BASES = {1:"closing",2:"last-pre-match",3:"bet365-last-pre-match",4:"bet365-closing",5:"bet365-pre-match",6:"pinnacle-pre-match"}

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')


def atomic(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_bytes(encoded(value))
    temp.replace(path)


def validate(rows):
    ids, keys = set(), set()
    for row in rows:
        key = (row['date'], row['home'], row['away'])
        if row['id'] in ids or key in keys or row['home'] == row['away'] or row['league'] != 'championship':
            raise ValueError('Duplicate or invalid Championship fixture')
        ids.add(row['id']); keys.add(key)
        if any(type(row[s]) is not int or row[s] < 0 for s in ('hg', 'ag')):
            raise ValueError('Invalid result')
        if row['odds'] is not None and (len(row['odds']) != 3 or row['basis'] not in BASES.values() or
                not all(type(p) in (int, float) and math.isfinite(p) and 1 < p <= 1000 for p in row['odds'])):
            raise ValueError('Invalid price contract')
