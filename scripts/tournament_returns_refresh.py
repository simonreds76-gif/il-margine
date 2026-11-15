"""Rebuild the display-only tournament returns inside the existing Atlas batch."""
import hashlib
import importlib.util
import json
import math
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

DATA = Path('src/data/tennis-tournament-returns.json')
EVIDENCE = Path('src/data/tennis-tournament-completion-evidence.json')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    temporary.replace(path)


def content(value):
    # An unchanged result set must not cause another deployment just because
    # the source was checked again. The snapshot keeps its true prior date.
    return {k: v for k, v in value.items() if k not in ('version', 'asOf', 'coverageUpdatedAt')}


def version(value):
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    return 'tr-' + hashlib.sha256(payload.encode()).hexdigest()[:20]


def check_counts(row):
    keys = ('completed', 'paired', 'noPrice', 'pickems', 'bettable')
    if any(type(row.get(k)) is not int or row[k] < 0 for k in keys):
        raise ValueError('Invalid tournament counts')
    if row['completed'] != row['paired'] + row['noPrice'] or row['paired'] != row['bettable'] + row['pickems']:
        raise ValueError('Tournament coverage does not reconcile')
    if sum(row['priceMix'].values()) != row['paired']:
        raise ValueError('Tournament price basis does not reconcile')
    for side in ('favourite', 'underdog'):
        s = row[side]
        if any(type(s.get(k)) is not int or s[k] < 0 for k in ('wins', 'losses', 'stake')):
            raise ValueError('Invalid tournament strategy counts')
        if s['wins'] + s['losses'] != s['stake'] or s['stake'] != row['bettable']:
            raise ValueError('Tournament strategy does not reconcile')
        if not math.isfinite(s['profit']):
            raise ValueError('Invalid tournament profit')
        if s['stake']:
            if not isinstance(s['roi'], (int, float)) or not math.isfinite(s['roi']) or abs(s['roi'] - 100 * s['profit'] / s['stake']) > .0001:
                raise ValueError('Tournament ROI does not reconcile')
        elif s['profit'] != 0 or s['roi'] is not None:
            raise ValueError('Empty tournament sample has a return')
    if row['favourite']['wins'] + row['underdog']['wins'] != row['bettable']:
        raise ValueError('Tournament sides do not reconcile')


def validate(old, new):
    if new.get('schema') != 1 or not new.get('families'):
        raise ValueError('Missing tournament snapshot')
    previous = {e['id']: e for f in (old or {}).get('families', []) for e in f['editions']}
    current = {}
    for family in new['families']:
        for e in family['editions']:
            if e['id'] in current:
                raise ValueError('Duplicate tournament edition')
            check_counts(e)
            current[e['id']] = e
            prior = previous.get(e['id'])
            if prior:
                if any(prior[k] != e[k] for k in ('event', 'year', 'surface')):
                    raise ValueError('Existing tournament identity changed')
                if any(e[k] < prior[k] for k in ('completed', 'paired', 'bettable', 'pickems')):
                    raise ValueError('Existing tournament observations disappeared')
                for side in ('favourite', 'underdog'):
                    if any(e[side][k] < prior[side][k] for k in ('wins', 'losses')):
                        raise ValueError('Existing tournament outcomes changed')
                    if e['bettable'] == prior['bettable'] and e[side] != prior[side]:
                        raise ValueError('Existing tournament returns changed without new observations')
        for window in family['windows'].values():
            check_counts(window['pool'])
            if any('opening' in k.lower() for k in window['pool']['priceMix']):
                raise ValueError('Opening prices entered the comparison')
    if not previous.keys() <= current.keys():
        raise ValueError('Existing tournament editions disappeared')


def rebuild(candidate, site_root, audit_dir):
    path = Path(__file__).with_name('build-tennis-tournament-returns.py')
    spec = importlib.util.spec_from_file_location('tournament_returns_builder', path)
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    builder.build(candidate, site_root, audit_dir)
    return read(Path(site_root) / DATA)


def prepare(checkout, candidate, *, builder=None):
    """Isolate a bad derived view: retain its last good data, refresh other tools."""
    checkout, candidate = Path(checkout), Path(candidate)
    target, prior = candidate / 'release' / DATA, checkout / DATA
    audit_dir = candidate / 'tournament-private'
    audit_dir.mkdir(parents=True, exist_ok=True)
    checked = datetime.now(timezone.utc).isoformat()
    old = read(prior) if prior.exists() else None
    try:
        evidence = candidate / 'release' / EVIDENCE
        evidence.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(checkout / EVIDENCE, evidence)
        new = (builder or rebuild)(candidate, candidate / 'release', audit_dir)
        validate(old, new)
        if old and content(old) == content(new) and old['asOf'][:4] == new['asOf'][:4]:
            new = dict(old)
        # Version is embedded into the rendered page so publication checks the
        # actual UI, rather than assuming a green build means fresh figures.
        new['version'] = version({k: v for k, v in new.items() if k != 'version'})
        changed = old != new
        if not changed:
            # Git may check JSON out as CRLF on Windows. Preserve the original
            # bytes when the parsed snapshot is identical; do not create a
            # phantom stage/empty commit from newline conversion alone.
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(prior, target)
        else:
            write(target, new)
        report = {'status': 'validated', 'checkedAt': checked, 'version': new['version'],
                  'changed': changed,
                  'archiveVersion': new['archiveVersion'], 'sourceUpdatedAt': new['coverageUpdatedAt'],
                  'through': new['through'], 'families': len(new['families']),
                  'paired': sum(e['paired'] for f in new['families'] for e in f['editions']),
                  'completed': sum(e['completed'] for f in new['families'] for e in f['editions']),
                  'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}
    except Exception as exc:
        if old:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(prior, target)
        elif target.exists():
            target.unlink()  # only this unpublished derived candidate
        report = {'status': 'retained_previous' if old else 'unavailable', 'checkedAt': checked,
                  'changed': False, 'version': (old or {}).get('version'),
                  'errorType': type(exc).__name__, 'error': str(exc)[:500]}
    write(audit_dir / 'refresh-status.json', report)
    return report


def expected_version(checkout):
    path = Path(checkout) / DATA
    if not path.exists():
        return None
    value = read(path)
    actual = value.get('version')
    if not isinstance(actual, str) or not re.fullmatch(r'tr-[a-f0-9]{20}', actual):
        raise ValueError('Tournament snapshot version missing')
    if actual != version({k: v for k, v in value.items() if k != 'version'}):
        raise ValueError('Tournament snapshot checksum mismatch')
    return actual


def page_version(html):
    found = re.findall(r'data-tournament-returns-version="(tr-[a-f0-9]{20})"', html)
    if len(found) != 1:
        raise ValueError('Rendered tournament snapshot version missing or ambiguous')
    return found[0]


def is_live(checkout, site, fetch):
    expected = expected_version(checkout)
    if not expected:
        return True
    try:
        return page_version(fetch(site + '/tennis-matchday').decode('utf-8')) == expected
    except (ValueError, OSError, RuntimeError):
        return False
