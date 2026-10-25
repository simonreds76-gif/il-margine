"""Weekly Championship extension collector. Never writes incumbent archives.

Default: replay saved evidence. --capture uses the existing free account only,
with at most one fixture listing and 36 history downloads per invocation.
Only independently collected results from 23 October 2026; no historical seed.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import time

import sys
ROOT = Path(__file__).resolve().parents[1]
if os.environ.get("ATLAS_BASE_SCRIPTS"):
    sys.path.insert(0, os.environ["ATLAS_BASE_SCRIPTS"])
import football_atlas_weekly as weekly
from atlas_championship_state import read, encoded, atomic, validate
FORWARD_START = "2026-10-23"

UTC = timezone.utc
REGISTRY = ROOT / 'scripts/config/football-atlas-competitions.json'


def dt(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def key(row):
    return (row['date'], row['home'], row['away'])


def identity(f):
    return [f[k] for k in ('fixtureId', 'participant1Id', 'participant2Id', 'startTime')] + [f.get('trueStartTime'), f.get('updatedAt')]


@contextmanager
def lock(directory):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / 'collector.lock'
    # OS-owned lock releases on a crash. A stale PID file must not strand retries.
    handle = path.open('a+b')
    handle.seek(0,2)
    if handle.tell() == 0:
        handle.write(b'0'); handle.flush()
    handle.seek(0)
    try:
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(),fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == 'nt':msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
            else:fcntl.flock(handle.fileno(),fcntl.LOCK_UN)
    except OSError as exc:
        raise ValueError('Collector lock unavailable or filesystem operation failed') from exc
    finally:
        handle.close()


class Evidence:
    def __init__(self, cache, seed_cache):
        self.cache, self.seed_cache = Path(cache), Path(seed_cache)
        self.hashes = {}

    def paths(self, pattern):
        return sorted(set(self.seed_cache.glob(pattern)) | set(self.cache.glob(pattern)))

    def load(self, path):
        raw = path.read_bytes()
        self.hashes[str(path.resolve())] = hashlib.sha256(raw).hexdigest()
        return json.loads(gzip.decompress(raw) if path.suffix == '.gz' else raw.decode('utf-8-sig'))

    def named(self, name):
        for folder in (self.cache, self.seed_cache):
            if (folder / name).exists():
                return self.load(folder / name)
        raise FileNotFoundError(name)


def aliases(config):
    result = {}
    for canonical, club in config['clubs'].items():
        for name in [canonical, *club['names']]:
            if name in result and result[name] != canonical:
                raise ValueError('Ambiguous club alias')
            result[name] = canonical
    return result


def calendar(payload, config, now):
    if payload['LeagueInfo'][:2] != [config['goaloo'], 'England Championship']:
        raise ValueError('Wrong calendar competition')
    names = aliases(config)
    teams = {t[0]: names[t[1]] for t in payload['TeamInfo']}
    rows = []
    # Only regular-season rounds. Never treat aggregate playoff wrappers as games.
    for games in payload['ScheduleList']['sub_87'].values():
        for r in games:
            kickoff = datetime.fromisoformat(r[3]).replace(tzinfo=UTC) - timedelta(hours=8)
            if r[2] != -1 or kickoff > now - timedelta(hours=6):
                continue
            score = re.fullmatch(r'(\d+)-(\d+)', str(r[6]))
            if not score or r[1] != config['goaloo']:
                raise ValueError('Invalid completed calendar result')
            home, away = teams[r[4]], teams[r[5]]
            if config['clubs'][home]['goaloo'] != r[4] or config['clubs'][away]['goaloo'] != r[5]:
                raise ValueError('Calendar participant mismatch')
            rows.append({'id': 'champ-goaloo-' + str(r[0]), 'date': kickoff.date().isoformat(),
                         'home': home, 'away': away, 'hg': int(score[1]), 'ag': int(score[2]),
                         'kickoff': kickoff.isoformat(), 'league': 'championship',
                         'season': f'{kickoff.year if kickoff.month >= 7 else kickoff.year-1}-{kickoff.year+1 if kickoff.month >= 7 else kickoff.year}',
                         'odds': None, 'basis': None})
    validate(rows)
    return rows


def match_provider(row, fixtures, config):
    expected = [config['clubs'][row[k]].get('oddsPapi') for k in ('home', 'away')]
    matches = [f for f in fixtures if f.get('tournamentId') == config['oddsPapi'] and
               [f.get('participant1Id'), f.get('participant2Id')] == expected and
               abs(dt(f['startTime']) - dt(row['kickoff'])) <= timedelta(minutes=5)]
    if len(matches) != 1 or None in expected:
        raise ValueError('provider_fixture_unresolved')
    f = matches[0]
    names = aliases(config)
    if [names.get(f[k]) for k in ('participant1Name', 'participant2Name')] != [row['home'], row['away']]:
        raise ValueError('participant_mismatch')
    if f['statusId'] != 2:
        raise ValueError('provider_result_not_finished')
    return f


def verify_result(row, day, config):
    names = aliases(config)
    games = [m for l in day['leagues'] if l.get('ccode') == 'ENG' and
             l.get('primaryId', l['id']) == config['fotmob'] for m in l['matches']]
    matches = [m for m in games if [names.get(m[s]['name']) for s in ('home','away')] == [row['home'],row['away']]]
    if len(matches) != 1:
        raise ValueError('result_identity_unresolved')
    m = matches[0]
    if dt(m['status']['utcTime']) != dt(row['kickoff']):
        raise ValueError('result_kickoff_conflict')
    if not m['status'].get('finished') or m['status'].get('cancelled') or m['status'].get('awarded'):
        raise ValueError('result_not_played')
    if [m[s]['score'] for s in ('home','away')] != [row['hg'],row['ag']]:
        raise ValueError('result_score_conflict')
    for side in ('home','away'):
        known = config['clubs'][row[side]].get('fotmob')
        if known is not None and known != m[side]['id']:
            raise ValueError('result_participant_conflict')
    return m['id']


def price(row, f, raw):
    if raw.get('fixtureId') != f['fixtureId']:
        raise ValueError('price_fixture_mismatch')
    if abs(dt(f.get('trueStartTime') or f['startTime']) - dt(f['startTime'])) > timedelta(minutes=15):
        raise ValueError('reschedule_review')
    cutoff = min(dt(row['kickoff']), dt(f['startTime']), dt(f.get('trueStartTime') or f['startTime']))
    histories = {b: raw.get('bookmakers', {}).get(b, {}).get('markets', {}).get('101', {}).get('outcomes', {}) for b in ('pinnacle','bet365')}
    return {**weekly.select_market(histories, cutoff), 'cutoff': cutoff.isoformat(), 'fixtureSignature': identity(f)}


def merge(previous, candidates):
    """Stable Goaloo identity; never reprice, duplicate or silently correct a result."""
    indexed = {r['id']: r for r in previous}
    conflicts = []
    for new in candidates:
        old = indexed.get(new['id'])
        if old:
            if any(old[k] != new[k] for k in ('date','home','away','hg','ag','kickoff')):
                conflicts.append({'id':new['id'],'reason':'identity_or_result_correction','previous':old,'candidate':new})
                continue
            if old['odds'] is not None:
                continue
        indexed[new['id']] = new
    rows = sorted(indexed.values(), key=lambda r:(r['date'],r['id']))
    validate(rows)
    return rows, conflicts


class FreeCapture:
    def __init__(self, cache, env, config):
        import requests
        self.requests, self.cache, self.config = requests, cache, config
        self.key = os.environ.get("ODDSPAPI_API_KEY")
        for line in (Path(env).read_text(encoding="utf-8-sig").splitlines() if env else []):
            if '=' in line and line.split('=',1)[0].strip() in ('ODDSPAPI_API_KEY','ODDSPAPI_KEY'):
                self.key = line.split('=',1)[1].strip().strip('\"').strip("'")
        if not self.key: raise ValueError('Provider key unavailable')
        self.listings, self.histories, self.last = 0, 0, 0
        self.journal = read(cache/'requests.json') if (cache/'requests.json').exists() else []
        self.account()

    def get(self, url, params=None, provider=False):
        time.sleep(max(0, 5.3-(time.monotonic()-self.last)))
        self.last = time.monotonic()
        try:
            response = self.requests.get(url, params={**(params or {}), **({'apiKey': self.key} if provider else {})}, timeout=40, allow_redirects=False)
            entry = {'at':datetime.now(UTC).isoformat(), 'source':url, 'params':params or {}, 'status':response.status_code}
            self.journal.append(entry); atomic(self.cache/'requests.json',self.journal)
            if response.status_code != 200: raise ValueError('source_http_' + str(response.status_code))
            if len(response.content)>30_000_000: raise ValueError('source_response_too_large')
            return json.loads(response.content.decode('utf-8-sig'))
        except self.requests.RequestException:
            raise ValueError('source_network_error') from None

    def account(self):
        data=self.get('https://api.oddspapi.io/v4/account',provider=True)
        subs=[s for s in data.get('subscriptions',[]) if s.get('is_active') and 10 in (s.get('sport_ids') or [])]
        if len(subs)!=1 or subs[0].get('price') not in (None,0): raise ValueError('Free football entitlement not verified')
        sub=subs[0]
        if sub['request_limit']-sub['request_count'] <= self.config['reserve']: raise ValueError('Protected quota reserve reached')
        atomic(self.cache/'quota.json', {k:sub.get(k) for k in ('request_limit','request_count','price','auto_renew')})

    def listing(self, start, end):
        if self.listings >= 1: raise ValueError('Fixture request cap reached')
        self.account(); self.listings += 1
        raw=self.get('https://api.oddspapi.io/v4/fixtures', {'tournamentId':self.config['oddsPapi'],'from':start+'T00:00:00Z','to':end+'T23:59:59Z'}, True)
        atomic(self.cache/'fixtures-current.json',raw)

    def history(self, f):
        signature=hashlib.sha256(encoded(identity(f))).hexdigest()[:20]
        target=self.cache/f'history-{signature}.json.gz'
        if target.exists(): return json.loads(gzip.decompress(target.read_bytes()))['raw']
        attempts=[e for e in self.journal if e['source'].endswith('/historical-odds') and e['params'].get('fixtureId')==f['fixtureId']]
        if len(attempts)>=2: raise ValueError('history_unavailable_after_two_attempts')
        if attempts and dt(attempts[-1]['at']) > datetime.now(UTC)-timedelta(days=6): raise ValueError('history_retry_not_due')
        if self.histories>=36: raise ValueError('History request cap reached')
        self.histories+=1
        raw=self.get('https://api.oddspapi.io/v4/historical-odds',{'fixtureId':f['fixtureId'],'bookmakers':'pinnacle,bet365'},True)
        payload={'signature':identity(f),'raw':raw}
        temporary=target.with_suffix('.tmp');temporary.write_bytes(gzip.compress(encoded(payload)));temporary.replace(target)
        return raw


def run(state, evidence_directory, now, capture=False, env=None):
    state=Path(state); cache=state/'evidence';cache.mkdir(parents=True,exist_ok=True)
    with lock(state):
        config=read(REGISTRY)['championship']; evidence=Evidence(cache,evidence_directory)

        previous=read(state/'ledger.json') if (state/'ledger.json').exists() else {'rows':[]}
        if previous.get('retryHistory') and not (cache/'requests.json').exists():
            atomic(cache/'requests.json',previous['retryHistory'])
        api=FreeCapture(cache,env,config) if capture else None
        season=f'{now.year if now.month>=7 else now.year-1}-{now.year+1 if now.month>=7 else now.year}'
        if season != config['validatedSeason']:
            raise ValueError('Championship season registry requires validation; last good checkpoint retained')
        if api:
            atomic(cache/f'goaloo-{season}.json',api.get(f'https://football.goaloo.com/jsData/matchResult/json/{season}/s37_en.json'))
        rows=[r for r in calendar(evidence.named(f'goaloo-{season}.json'),config,now) if r['date'] >= FORWARD_START]
        pending, candidates, shadowed=[],[],[]
        validate(previous['rows'])
        priced_ids={r['id'] for r in previous['rows'] if r['odds'] is not None}
        new=[r for r in rows if r['id'] not in priced_ids and r['date'] >= (now-timedelta(days=14)).date().isoformat()]
        fixtures={}
        for p in evidence.paths('fixtures-*.json'):
            for f in evidence.load(p): fixtures[f['fixtureId']]=f
        if api and new:
            unresolved=[r for r in new if not any(abs(dt(f['startTime'])-dt(r['kickoff']))<=timedelta(minutes=5) and f.get('participant1Id')==config['clubs'][r['home']].get('oddsPapi') for f in fixtures.values())]
            if unresolved:
                start=min(r['date'] for r in unresolved)
                if (now.date()-datetime.fromisoformat(start).date()).days>14: raise ValueError('Catch-up exceeds bounded weekly window')
                api.listing(start,now.date().isoformat())
                for f in evidence.named('fixtures-current.json'): fixtures[f['fixtureId']]=f
        histories={}
        for p in evidence.paths('historical-odds-*.json'):
            raw=evidence.load(p);histories[raw['fixtureId']]=raw
        for p in evidence.paths('history-*.json.gz'):
            saved=evidence.load(p);f=fixtures.get(saved['raw']['fixtureId'])
            if f and saved['signature']==identity(f): histories[f['fixtureId']]=saved['raw']
        for row in rows:
            old=next((r for r in previous['rows'] if r['id']==row['id']),None)
            if old and old['odds'] is not None:
                candidates.append(row);continue
            if row['date'] < (now-timedelta(days=14)).date().isoformat():
                pending.append({'id':row['id'],'fixture':key(row),'state':'manual_catch_up','reason':'outside_bounded_window'});continue
            try:
                dayname='fotmob-'+row['date'].replace('-','')+'.json'
                try:day=evidence.named(dayname)
                except FileNotFoundError:
                    if not api: raise ValueError('result_evidence_missing')
                    day=api.get('https://www.fotmob.com/api/data/matches',{'date':row['date'].replace('-',''),'timezone':'Europe/London','ccode3':'GBR'})
                    atomic(cache/dayname,day);day=evidence.named(dayname)
                mid=verify_result(row,day,config)
            except (ValueError,KeyError) as exc:
                pending.append({'id':row['id'],'fixture':key(row),'state':'result_review','reason':str(exc)});continue
            row={**row,'provenance':'goaloo+fotmob+oddspapi','resultEvidence':{'fotmobMatchId':mid,'goalooId':row['id'].removeprefix('champ-goaloo-')},'managerState':'not_integrated'}
            try:
                f=match_provider(row,list(fixtures.values()),config)
                old=next((r for r in previous['rows'] if r['id']==row['id']),None)
                if old and old['odds'] is not None:
                    candidates.append(row);continue  # merge retains immutable original price/evidence
                raw=histories.get(f['fixtureId'])
                if raw is None and api: raw=api.history(f)
                if raw is None: raise ValueError('history_not_captured')
                market=price(row,f,raw)
                row.update(odds=market['odds'],basis=market['basis'],priceEvidence=market,priceState='verified')
            except (ValueError,KeyError) as exc:
                row['priceState']='unpriced'
                pending.append({'id':row['id'],'fixture':key(row),'state':'price_review','reason':str(exc)})
            candidates.append(row)
        merged,conflicts=merge(previous['rows'],candidates)
        pending_by_id={r['id']:r for r in previous.get('pending',[])}
        pending_by_id.update({r['id']:r for r in pending})
        priced={r['id'] for r in merged if r['odds'] is not None}
        pending=[r for mid,r in sorted(pending_by_id.items()) if mid not in priced]
        conflicts=list({encoded(r):r for r in previous.get('conflicts',[])+conflicts}.values())
        journal=api.journal if api else previous.get('retryHistory',[])
        retries=[e for e in journal if e['source'].endswith('/historical-odds') and e['status']!=200]
        payload={'schema':1,'competition':'championship','scope':'regular-season','startDate':FORWARD_START,'rows':merged,'pending':pending,'conflicts':conflicts,'retryHistory':retries}
        version=hashlib.sha256(encoded(payload)).hexdigest()
        # Single checkpoint includes rows, retry states and conflicts. Failed runs preserve it.
        atomic(state/'ledger.json',payload)
        report={'version':version,'newResults':len(merged),'newPriced':sum(r['odds'] is not None for r in merged),'pending':len(pending),'conflicts':len(conflicts),'through':max((r['date'] for r in merged),default=None),'evidenceHashes':evidence.hashes}
        atomic(state/'report.json',report)
        return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--state',type=Path,required=True);p.add_argument('--evidence',type=Path,required=True)
    p.add_argument('--as-of',default=datetime.now(UTC).isoformat());p.add_argument('--capture',action='store_true');p.add_argument('--credential-file',type=Path)
    args=p.parse_args()
    if args.capture and not (args.credential_file or os.environ.get('ODDSPAPI_API_KEY')):p.error('Existing provider credential required')
    try: print(json.dumps(run(args.state,args.evidence,dt(args.as_of),args.capture,args.credential_file)))
    except Exception as exc: raise SystemExit(str(exc) if isinstance(exc,(ValueError,FileExistsError)) else type(exc).__name__) from None
