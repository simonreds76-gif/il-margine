"""Validate a bounded browser export before using the production index builder."""
import argparse, base64, hashlib, importlib.util, json, os, subprocess, sys, zlib
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

def timestamp(value):
    parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Timestamps must include a timezone')
    return parsed

def validate(source, now=None):
    now = now or datetime.now(timezone.utc)
    pages = source.get('pages', [])
    if not 4 <= len(pages) <= 8:
        raise ValueError('Capture must contain 4–8 event pages')
    if not -60 <= (now - timestamp(source.get('captured_at'))).total_seconds() <= 21600:
        raise ValueError('Capture is stale or future dated')
    seen = set()
    counts = {'football': 0, 'tennis': 0}
    allowed = {'football': {'Win Market', 'Draw No Bet', 'Total Goals Over/Under', 'Both Teams To Score', 'Total Corners'}, 'tennis': {'Win Market', 'Handicaps'}}
    for page in pages:
        url = urlparse(page.get('url', ''))
        sport = page.get('sport')
        if sport not in counts or url.scheme != 'https' or url.netloc != 'www.oddschecker.com' or not url.path.startswith('/'+sport+'/') or not url.path.endswith('/winner'):
            raise ValueError('Unexpected source URL or sport')
        if page['url'] in seen or not page.get('home') or not page.get('away') or page['home'] == page['away']:
            raise ValueError('Duplicate or unidentified event')
        seen.add(page['url'])
        captured = timestamp(page.get('captured_at'))
        starts = timestamp(page.get('starts_at'))
        if not -60 <= (now-captured).total_seconds() <= 21600 or starts <= now or captured >= starts:
            raise ValueError('Only fresh, upcoming pre-match captures can publish')
        page['grids'] = [g for g in page.get('grids', []) if g.get('market') in allowed[sport]]
        if not page['grids']:
            raise ValueError('No supported comparison grids')
        counts[sport] += 1
    if min(counts.values()) < 2:
        raise ValueError('Need at least two distinct events per sport')
    return source

def decode_capture(encoded):
    raw = base64.b64decode(encoded, validate=True)
    dec = zlib.decompressobj()
    decoded = dec.decompress(raw, 2_000_001)
    if len(decoded) > 2_000_000 or not dec.eof or dec.unused_data:
        raise ValueError('Invalid or oversized compressed capture')
    return json.loads(decoded)

def check_result(result):
    if result.get('status') not in {'PASS', 'PASS_LIMITED'}:
        raise ValueError('Builder did not produce a publishable snapshot')
    if result.get('coverage', {}).get('payload_operators', 0) < 10:
        raise ValueError('Fewer than ten bookmakers returned complete source data')
    passing = [s for s in result.get('segments', []) if s.get('status') in {'PASS','PASS_LIMITED'}]
    if not {'Football','Tennis'} <= {s.get('sport') for s in passing}:
        raise ValueError('Both sports need a publishable comparison')
    return result

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repository', required=True)
    ap.add_argument('--output-dir', required=True)
    args = ap.parse_args()
    out = Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)
    source = validate(decode_capture(os.environ['CAPTURE_ZLIB_BASE64']))
    raw = out/'oddschecker-capture.json'
    raw.write_text(json.dumps(source, indent=2), encoding='utf-8')
    index = out/'margin-index.json'
    subprocess.run([sys.executable, str(Path(args.repository)/'scripts/bookmaker-margin-index.py'), '--oddschecker-json', str(raw), '--output', str(index)], check=True)
    result = check_result(json.loads(index.read_text(encoding='utf-8')))
    result['generated_at'] = source['captured_at']
    result['capture_mode'] = 'browser_snapshot'
    result['capture']['source_captured_at'] = source['captured_at']
    result['capture']['raw_capture_sha256'] = hashlib.sha256(raw.read_bytes()).hexdigest()
    result['methodology']['scope'] = 'Dated public Oddschecker UK pre-match snapshot; complete like-for-like fixed-odds sportsbook outcome sets only. Not a live feed or long-run bookmaker ranking.'
    index.write_text(json.dumps(result, indent=2, sort_keys=True), encoding='utf-8')
    print(json.dumps({'status': result['status'], 'captured_at': result['generated_at'], 'coverage': result['coverage'], 'summary': result['summary']}))

if __name__ == '__main__':
    main()
