"""Dated Tennis Abstract Elo research inputs. No live DB writes or model calls.

The published hElo/cElo/gElo fields are BLENDED ratings, never raw surfaces.
Snapshots become available at retrieval, not at midnight of publication date.
"""
from __future__ import annotations
import argparse, contextlib, csv, hashlib, json, math, os, re, sys, tempfile, unicodedata
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qs
from urllib.request import Request, urlopen
from bs4 import BeautifulSoup

VERSION = 'ta-elo-isolated-v1'
URLS = {t:f'https://www.tennisabstract.com/reports/{t.lower()}_elo_ratings.html' for t in ('ATP','WTA')}
MAX_AGE_DAYS = 14
MIN_ROWS = 100
MAX_BYTES = 4 * 1024 * 1024
MAX_STORE_BYTES = 128 * 1024 * 1024

class CollectorLocked(OSError): pass

def encoded(value): return json.dumps(value, sort_keys=True, separators=(',',':'), ensure_ascii=False, allow_nan=False).encode('utf8')
def digest(value): return hashlib.sha256(encoded(value)).hexdigest()
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path, default=None): return json.loads(Path(path).read_text(encoding='utf-8-sig')) if Path(path).exists() else default
def read_csv(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f: return list(csv.DictReader(f))
def norm(text):
    text=''.join(c for c in unicodedata.normalize('NFKD',str(text)) if not unicodedata.combining(c)).lower()
    if ',' in text:
        last,first=text.split(',',1); text=first+' '+last
    return ' '.join(re.findall(r'[a-z0-9]+',text))
def utc(value):
    dt=datetime.fromisoformat(str(value).replace('Z','+00:00'))
    if dt.tzinfo is None: raise ValueError('timezone_required')
    return dt.astimezone(timezone.utc)
def atomic(path,value):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix=path.name+'.',suffix='.tmp',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as f: f.write(encoded(value)); f.flush(); os.fsync(f.fileno())
        os.replace(name,path)
    finally:
        if os.path.exists(name): os.unlink(name)
def immutable(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        if path.read_bytes()!=data: raise ValueError('immutable_file_conflict')
        return
    with path.open('xb') as f: f.write(data);f.flush();os.fsync(f.fileno())

@contextlib.contextmanager
def lock(directory):
    """OS lock releases on process exit/crash; no stale-lock deletion needed."""
    directory.mkdir(parents=True,exist_ok=True)
    with (directory/'collector.lock').open('a+b') as f:
        f.seek(0,2)
        if f.tell()==0: f.write(b'0');f.flush()
        f.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError as exc:raise CollectorLocked('collector_locked') from exc
        try: yield
        finally:
            f.seek(0)
            if os.name=='nt': msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)
            else: fcntl.flock(f,fcntl.LOCK_UN)

def fetch(tour):
    request=Request(URLS[tour],headers={'User-Agent':'IlMargine research Elo reader/1.0','Accept':'text/html'})
    with urlopen(request,timeout=25) as response:
        final=urlparse(response.geturl())
        if final.scheme!='https' or final.hostname not in {'www.tennisabstract.com','tennisabstract.com'}:
            raise ValueError('unexpected_source_redirect')
        raw=response.read(MAX_BYTES+1)
    if len(raw)>MAX_BYTES: raise ValueError('source_response_too_large')
    return raw

def parse(raw,tour,observed_at,minimum=MIN_ROWS):
    if tour not in URLS: raise ValueError('unknown_tour')
    now=utc(observed_at)
    if b'</html>' not in raw.lower() or b'</table>' not in raw.lower():raise ValueError('truncated_source_document')
    soup=BeautifulSoup(raw,'html.parser')
    dates=re.findall(r'Last update:\s*(\d{4}-\d{2}-\d{2})',soup.get_text(' ',strip=True))
    if len(set(dates))!=1: raise ValueError('publication_date_missing_or_ambiguous')
    published=date.fromisoformat(dates[0]);age=(now.date()-published).days
    if not 0<=age<=MAX_AGE_DAYS: raise ValueError('source_date_future_or_stale')
    tables=soup.find_all('table',id='reportable')
    if len(tables)!=1: raise ValueError('reportable_table_missing_or_ambiguous')
    trs=tables[0].find_all('tr')
    if not trs: raise ValueError('empty_table')
    heads=[c.get_text(' ',strip=True).replace('\xa0',' ').lower() for c in trs[0].find_all(['td','th'])]
    required=('elo rank','player','elo','helo','celo','gelo')
    if any(heads.count(k)!=1 for k in required): raise ValueError('rating_schema_changed')
    ix={k:heads.index(k) for k in required}; records=[];seen=set();names=set()
    for tr in trs[1:]:
        cells=tr.find_all(['td','th'])
        if not cells: continue
        if len(cells)!=len(heads): raise ValueError('partial_rating_row')
        if cells[ix['elo rank']].get_text(strip=True)!=str(len(records)+1):raise ValueError('noncontiguous_source_ranks')
        cell=cells[ix['player']]; name=cell.get_text(' ',strip=True).replace('\xa0',' ')
        link=cell.find('a',href=True)
        if not name or link is None: raise ValueError('missing_player_identity')
        profile=urljoin(URLS[tour],link['href']);u=urlparse(profile)
        if u.hostname not in {'www.tennisabstract.com','tennisabstract.com'}: raise ValueError('unexpected_player_link')
        key=parse_qs(u.query).get('p',[''])[0]
        if not key or key in seen: raise ValueError('duplicate_or_missing_source_identity')
        seen.add(key);names.add(norm(name))
        values={}
        for field in ('elo','helo','celo','gelo'):
            text=cells[ix[field]].get_text(strip=True)
            if not text or text in {'-','—'}:
                if field=='elo': raise ValueError('missing_overall_rating')
                values[field]=None;continue
            try: value=float(text)
            except ValueError: raise ValueError('invalid_rating') from None
            if not math.isfinite(value) or not 500<=value<=3000: raise ValueError('rating_out_of_bounds')
            values[field]=value
        records.append({'tour':tour,'source_player_key':key,'name':name,'profile_url':profile,
                        'overall':values['elo'],'surface_blended':{s:values[k] for s,k in [('Hard','helo'),('Clay','celo'),('Grass','gelo')]}})
    if not minimum<=len(records)<=5000: raise ValueError('implausible_source_row_count')
    return {'tour':tour,'publication_date':published.isoformat(),'records':records}

def identities(root,tour,records,extra=None):
    """Unique exact/explicit names with OnCourt and Sackmann DOB agreement.

    Never initials or first-last fuzzy fallback. All ambiguity stays visible.
    """
    paths=[root/f'data/oncourt/players_{tour.lower()}.csv',root/f'data/sackmann/{tour.lower()}_players.csv',root/'data/tennis-props/player-name-aliases.csv']
    extra=extra or root/'config/tennis-elo-source-aliases.json'
    before={str(p.relative_to(root)).replace('\\','/'):sha(p) for p in paths}
    native=read_csv(paths[0]);archive=read_csv(paths[1]);aliases=read_csv(paths[2])
    natives=defaultdict(list);archives=defaultdict(list); byid={}
    for p in native:
        natives[norm(p['name'])].append(p);byid[p['id']]=p
    for p in archive: archives[norm(p.get('name_first','')+' '+p.get('name_last',''))].append(p)
    explicit=defaultdict(set)
    for a in aliases:
        if a.get('tour','').upper()!=tour:continue
        # Existing aliases are names, not permission to pick the first candidate.
        for src,dest in [('alias','player_name'),('player_name','alias')]:
            for p in natives.get(norm(a.get(src,'')),[]):explicit[norm(a.get(dest,''))].add(p['id'])
    if extra.exists():
        before[str(extra).replace('\\','/')]=sha(extra)
        for a in load(extra,[]):
            if a.get('tour')==tour:
                p=byid.get(str(a['native_id']))
                if not p or p['name']!=a['native_name'] or p['birthdate']!=a['birthdate'] or not a.get('evidence'):
                    raise ValueError('reviewed_alias_identity_changed')
                explicit[norm(a['source_name'])].add(p['id'])
    out=[];gaps=[];namecounts=Counter(norm(r['name']) for r in records)
    for r in records:
        key=norm(r['name']);pool={p['id']:p for p in natives.get(key,[])}
        if namecounts[key]>1:
            gaps.append({'source_player_key':r['source_player_key'],'name':r['name'],'reason':'source_name_homonym','rules':['source_name_homonym'],'native_candidates':[]});continue
        pool.update({pid:byid[pid] for pid in explicit.get(key,set())})
        candidates=list(pool.values()); ar=archives.get(key,[])
        # Duplicate archive IDs sometimes describe the same name/DOB/country.
        # They corroborate one identity; retain every ID, never merge histories.
        known_dobs={a['dob'] for a in ar if a.get('dob')}
        known_countries={a['ioc'] for a in ar if a.get('ioc')}
        corroborated=[a for a in ar if a.get('dob') and a.get('ioc')]
        if len(candidates)!=1 or len(known_dobs)!=1 or len(known_countries)!=1 or not corroborated:
            reasons=[]
            if not candidates:reasons.append('native_name_missing')
            if len(candidates)>1:reasons.append('native_full_name_ambiguous')
            if not ar:reasons.append('archive_name_missing')
            if not known_dobs:reasons.append('archive_dob_missing')
            if len(known_dobs)>1:reasons.append('archive_dob_conflict')
            if not known_countries:reasons.append('archive_country_missing')
            if len(known_countries)>1:reasons.append('archive_country_conflict')
            if not corroborated:reasons.append('no_complete_archive_identity')
            gaps.append({'source_player_key':r['source_player_key'],'name':r['name'],
                         'reason':'identity_ambiguous' if len(candidates)>1 or len(known_dobs)>1 or len(known_countries)>1 else 'name_or_archive_identity_missing',
                         'rules':reasons,
                         'native_candidates':[p['id'] for p in candidates]});continue
        p=candidates[0];a=corroborated[0];dob=p.get('birthdate','').replace('-','')
        if not dob or dob!=a.get('dob') or not p.get('country') or p['country']!=a.get('ioc'):
            rules=[]
            if not dob or dob!=a.get('dob'):rules.append('native_archive_dob_missing_or_conflicting')
            if not p.get('country') or p['country']!=a.get('ioc'):rules.append('native_archive_country_missing_or_conflicting')
            gaps.append({'source_player_key':r['source_player_key'],'name':r['name'],'reason':'identity_fields_disagree','rules':rules,'native_candidates':[p['id']]});continue
        out.append({**r,'oncourt_id':int(p['id']),'oncourt_name':p['name'],'sackmann_ids':sorted({int(a['player_id']) for a in corroborated}),
                    'unverified_archive_ids':sorted({int(a['player_id']) for a in ar if a not in corroborated}),
                    'birthdate':p['birthdate'],'mapping_method':'unique_exact_name_and_dob' if norm(p['name'])==key else 'explicit_alias_and_dob'})
    claims=Counter(r['oncourt_id'] for r in out)
    for r in out:
        if claims[r['oncourt_id']]>1:gaps.append({'source_player_key':r['source_player_key'],'name':r['name'],'reason':'native_id_claimed_twice','rules':['native_id_claimed_twice'],'native_candidates':[str(r['oncourt_id'])]})
    out=[r for r in out if claims[r['oncourt_id']]==1]
    for rel,h in before.items():
        if sha(root/rel)!=h:raise ValueError('identity_inputs_changed_during_read')
    return out,gaps,before

def snapshot_current(directory,now,*,require_last_attempt_ok=False):
    status=load(directory/'status.json',{})
    if require_last_attempt_ok and status.get('state')!='VALIDATED':raise ValueError('latest_attempt_not_validated')
    good=status.get('last_good')
    if not good: raise ValueError('no_validated_snapshot')
    path=directory/good['snapshot']
    if path.resolve().parent!=(directory/'snapshots').resolve():raise ValueError('invalid_snapshot_path')
    if sha(path)!=good['sha256']:raise ValueError('snapshot_hash_changed')
    data=load(path);when=utc(now)
    if data['version']!=VERSION or utc(data['observed_at'])>when:raise ValueError('snapshot_not_available_at_prediction')
    if not 0<=(when.date()-date.fromisoformat(data['publication_date'])).days<=MAX_AGE_DAYS:raise ValueError('snapshot_stale')
    return data

def collect(root,output,tour,**kwargs):
    try:return _collect(root,output,tour,**kwargs)
    except CollectorLocked:return {'tour':tour,'state':'SKIPPED','reason':'collector_locked','live_writes':False}

def _collect(root,output,tour,*,now=None,fetcher=fetch,minimum=MIN_ROWS,aliases=None,revalidate_local=False):
    now=now or datetime.now(timezone.utc);stamp=now.isoformat();directory=output/tour.lower()
    with lock(directory):
        previous=load(directory/'status.json',{});good=previous.get('last_good')
        # Reservation written before HTTP prevents crash/retry polling loops.
        if not revalidate_local and previous.get('last_attempt_at','')[:10]==now.date().isoformat():
            return {**previous,'skipped':'daily_attempt_already_reserved'}
        state={'version':VERSION,'tour':tour,'state':'RUNNING','last_attempt_at':stamp,'last_good':good,'live_writes':False}
        atomic(directory/'status.json',state)
        try:
            files=[p for p in directory.rglob('*') if p.is_file()]
            usage=sum(p.stat().st_size for p in files)
            state.update(store_bytes_before=usage,capacity_warning=usage>MAX_STORE_BYTES*.8)
            if usage>MAX_STORE_BYTES-MAX_BYTES:raise ValueError('evidence_capacity_reached')
            if revalidate_local:
                if not good:raise ValueError('no_cached_source_to_revalidate')
                oldpath=directory/good['snapshot']
                if oldpath.resolve().parent!=(directory/'snapshots').resolve() or sha(oldpath)!=good['sha256']:
                    raise ValueError('prior_snapshot_integrity_failed')
                old=load(oldpath)
                if not re.fullmatch(r'[a-f0-9]{64}',old['raw_sha256']):raise ValueError('invalid_raw_hash')
                raw=(directory/'raw'/(old['raw_sha256']+'.html')).read_bytes()
                if hashlib.sha256(raw).hexdigest()!=old['raw_sha256']:raise ValueError('cached_source_hash_changed')
            else:raw=fetcher(tour)
            observed=datetime.now(timezone.utc) if fetcher is fetch else now
            rawhash=hashlib.sha256(raw).hexdigest()
            immutable(directory/'raw'/(rawhash+'.html'),raw)
            parsed=parse(raw,tour,observed.isoformat(),minimum)
            parsedhash=digest(parsed)
            immutable(directory/'parsed'/(parsedhash+'.json'),encoded(parsed))
            mapped,gaps,identityhashes=identities(root,tour,parsed['records'],aliases)
            if good:
                oldpath=directory/good['snapshot']
                if oldpath.resolve().parent!=(directory/'snapshots').resolve() or sha(oldpath)!=good['sha256']:
                    raise ValueError('prior_snapshot_integrity_failed')
                old=load(oldpath)
                if parsed['publication_date']<old['publication_date']:raise ValueError('publication_date_regressed')
                if len(parsed['records'])<.8*old['source_row_count']:raise ValueError('source_coverage_dropped')
                if old['raw_sha256']==rawhash and old['identity_source_hashes']==identityhashes and old['parser_sha256']==sha(__file__):
                    # Do not rewrite the observation time of already-seen ratings.
                    state.update(state='VALIDATED',last_good=good,unchanged=True,source_row_count=old['source_row_count'],mapped_players=len(old['players']),gaps=len(old['gaps']))
                    atomic(directory/'status.json',state);return state
            if not mapped:raise ValueError('no_verified_identity_mapping')
            if good and len(mapped)<.8*len(old['players']):raise ValueError('identity_coverage_dropped')
            snapshot={'version':VERSION,'tour':tour,'source_url':URLS[tour],
                'publication_date':parsed['publication_date'],'source_update_date':parsed['publication_date'],'observed_at':observed.isoformat(),
                'availability_note':'New mapping/parser versions available only at this validation time.' if revalidate_local else 'First observed at retrieval; source date is not exact availability.',
                'raw_sha256':rawhash,'parsed_sha256':parsedhash,'parser_sha256':sha(__file__),'identity_source_hashes':identityhashes,
                'independent_page_count':'No separate total stated; complete HTML, contiguous ranks, row floor and previous snapshot checks apply.',
                'source_row_count':len(parsed['records']),'players':mapped,'gaps':gaps,
                'meaning':{'overall':'published_overall','surface_blended':'published_overall_surface_blend','I.hard':'Hard blended proxy; no separate indoor rating'},
                'timing':'Available from observed_at only; publication date is not a verified pre-match timestamp.',
                'live_writes':False}
            content=encoded(snapshot);filename=f"{parsed['publication_date']}-{hashlib.sha256(content).hexdigest()[:20]}.json"
            immutable(directory/'snapshots'/filename,content)
            good={'snapshot':'snapshots/'+filename,'sha256':hashlib.sha256(content).hexdigest(),'observed_at':snapshot['observed_at'],'publication_date':snapshot['publication_date']}
            state.update(state='VALIDATED',last_good=good,source_row_count=len(parsed['records']),mapped_players=len(mapped),gaps=len(gaps),unchanged=False)
            atomic(directory/'status.json',state);return state
        except Exception as exc:
            # Never print request headers, credentials, raw payloads or exception URLs.
            safe=str(exc) if isinstance(exc,ValueError) else type(exc).__name__
            state.update(state='FAILED',reason=safe,last_good=good)
            atomic(directory/'status.json',state);return state

def mark_interrupted(output,tour):
    try:return _mark_interrupted(output,tour)
    except CollectorLocked:return {'tour':tour,'state':'SKIPPED','reason':'collector_locked','live_writes':False}

def _mark_interrupted(output,tour):
    directory=output/tour.lower()
    with lock(directory):
        state=load(directory/'status.json',{})
        if state.get('state')=='RUNNING':
            state.update(state='FAILED',reason='collector_process_interrupted',interrupted_at=datetime.now(timezone.utc).isoformat())
            atomic(directory/'status.json',state)
        # Keep the attempt reservation to prevent a same-day retry storm.
        return state

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    p.add_argument('--output',type=Path)
    p.add_argument('--tour',choices=['ATP','WTA','both'],default='both')
    p.add_argument('--aliases',type=Path)
    p.add_argument('--mark-interrupted',action='store_true',help='After the scheduler kills a timed-out process, mark its reserved attempt failed without retrying.')
    p.add_argument('--revalidate-local',action='store_true',help='Revalidate cached evidence without another HTTP request; new mapping gets a new timestamp.')
    args=p.parse_args();output=args.output or args.root/'data/tennis-elo-source'
    tours=['ATP','WTA'] if args.tour=='both' else [args.tour]
    reports=[mark_interrupted(output,t) if args.mark_interrupted else collect(args.root,output,t,aliases=args.aliases,revalidate_local=args.revalidate_local) for t in tours]
    print(json.dumps(reports,indent=2));return 0 if args.mark_interrupted or all(r['state'] in ('VALIDATED','SKIPPED') for r in reports) else 1

if __name__=='__main__':sys.exit(main())
