"""Exact paper quote joins with explicit names, round and tournament-edition checks."""
import csv
from datetime import datetime, timedelta, timezone
from functools import lru_cache
import math
from pathlib import Path
import re
import unicodedata
from tennis_price_identity import canonical_price_name


def normal(value):
    text = unicodedata.normalize('NFKD', str(value or '')).encode('ascii','ignore').decode().lower()
    return canonical_price_name(' '.join(re.findall(r'[a-z0-9]+', text)))


def utc(value):
    try:
        stamp = datetime.fromisoformat(str(value).replace('Z','+00:00'))
        return stamp.astimezone(timezone.utc) if stamp.tzinfo else None
    except (ValueError, TypeError): return None


def tournament(value):
    # Remove only the local numbered Challenger edition suffix. Its date/ID
    # still has to match below; arbitrary numbers in names remain meaningful.
    text = normal(value)
    text = re.sub(r'\b\d+\s+challenger\b', 'challenger', text)
    aliases = {'ningboo':'ningbo'}
    return {aliases.get(t,t) for t in text.split()} - {'atp','challenger','masters','1000','500','250','qualifying','qualification'}


@lru_cache(maxsize=4)
def recent_raw_quotes(paths):
    result=[]
    for name,stamp in paths:
        with Path(name).open(encoding='utf-8-sig',newline='') as f: result.extend(csv.DictReader(f))
    return result


def gap_reason(root,row,now=None):
    now=now or datetime.now(timezone.utc)
    folder=Path(root)/'data/pinnacle-history'
    paths=sorted([p for d in [now,now-timedelta(days=1)] for p in folder.glob(f'pinnacle-history-{d:%Y%m%d}-*.csv')],reverse=True)[:64]
    raw=recent_raw_quotes(tuple((str(p),p.stat().st_mtime_ns) for p in paths))
    pair={normal(row.get('player1')),normal(row.get('player2'))}
    event=tournament(row.get('event_key') or row.get('tour_name'))
    same=[q for q in raw if {normal(q.get('player1_name')),normal(q.get('player2_name'))}==pair
          and event<=tournament(q.get('league_name')) and utc(q.get('captured_at')) and utc(q['captured_at'])<=now]
    if not same:return 'no_bookmaker_quote_in_saved_window'
    latest=max(same,key=lambda q:utc(q['captured_at']))
    start=utc(latest.get('kickoff_iso'))
    if start and start<=now:return 'scheduled_start_passed_not_prematch'
    if now-utc(latest['captured_at'])>timedelta(hours=2):return 'quote_stale'
    return 'quote_ineligible_or_identity_unverified'


@lru_cache(maxsize=8)
def tables(folder, tour_stamp, today_stamp):
    def read(name):
        with (Path(folder)/name).open(encoding='utf-8-sig',newline='') as f: return list(csv.DictReader(f))
    return {r['id']:r for r in read('tours_atp.csv')}, read('today_atp.csv')


def edition_valid(root, row, quote, require_current_fixture=True):
    folder = Path(root)/'data/oncourt'
    tours, fixtures = tables(str(folder), (folder/'tours_atp.csv').stat().st_mtime_ns,
                            (folder/'today_atp.csv').stat().st_mtime_ns)
    tour = tours.get(str(row.get('tour_id')), {})
    start = utc(quote.get('kickoff_iso'))
    try: edition = datetime.fromisoformat(tour['date'][:10]).date()
    except (KeyError,ValueError): return False
    if not start or not edition - timedelta(days=3) <= start.date() <= edition + timedelta(days=13): return False
    league = str(quote.get('league',''))
    if (row.get('official_category') == 'Challenger') != (league == 'Challenger'): return False
    key = (str(row['tour_id']),str(row['round_id']),frozenset([str(row['player1_id']),str(row['player2_id'])]))
    exact = [f for f in fixtures if (f['tour_id'],f['round_id'],frozenset([f['player1_id'],f['player2_id']])) == key]
    if require_current_fixture and len(exact) != 1: return False
    if require_current_fixture and (exact[0].get('result','').strip() or str(exact[0].get('live','')).strip() not in ('','0')): return False
    match = re.search(r'\b(R1|R32|R16|QF|SF|Final|Q1|Q2|Q3)\b',quote.get('league_name',''),re.I)
    rounds = {'r1':'4','r32':'4','r16':'5','qf':'9','sf':'10','final':'12','q1':'1','q2':'2','q3':'3'}
    if match and rounds[match.group().lower()] != str(row['round_id']): return False
    # Another edition containing the same pair and round in this time window
    # cannot be selected merely by stripping the local edition number.
    for f in fixtures:
        if f['tour_id'] == key[0] or f['round_id'] != key[1]: continue
        if frozenset([f['player1_id'],f['player2_id']]) != key[2]: continue
        other = tours.get(f['tour_id'], {})
        try: other_day = datetime.fromisoformat(other['date'][:10]).date()
        except (KeyError,ValueError): continue
        if abs((other_day-start.date()).days) <= 13 and tournament(other.get('name')) == tournament(tour.get('name')):
            return False
    return True


def match_quote(root, row, available, require_current_fixture=True):
    names = [normal(row.get('player1')), normal(row.get('player2'))]
    event = tournament(row.get('event_key') or row.get('tour_name'))
    if not all(names) or len(set(names)) != 2 or not event: return None,'missing_identity'
    candidates = [q for q in available if {normal(q.get('player1_name')),normal(q.get('player2_name'))} == set(names)
                  and event <= tournament(q.get('league_name'))]
    if not candidates: return None,gap_reason(root,row) if require_current_fixture else 'no_recorded_preforecast_quote'
    candidates = [q for q in candidates if edition_valid(root,row,q,require_current_fixture)]
    if not candidates: return None,'edition_or_round_unverified'
    newest = max(utc(q['captured_at']) for q in candidates)
    candidates = [q for q in candidates if utc(q['captured_at']) == newest]
    if len({q['kickoff_iso'] for q in candidates}) != 1: return None,'ambiguous_start'
    aligned = []
    for q in candidates:
        reverse = normal(q['player1_name']) != names[0]
        try: a,b = float(q['odds2' if reverse else 'odds1']),float(q['odds1' if reverse else 'odds2'])
        except (KeyError,TypeError,ValueError): return None,'invalid_price'
        if not all(math.isfinite(v) and v>1 for v in (a,b)): return None,'invalid_price'
        aligned.append((a,b))
    if len(set(aligned)) != 1: return None,'conflicting_prices'
    a,b=aligned[0];q=candidates[0]
    return dict(odds1=a,odds2=b,market_p1=(1/a)/(1/a+1/b),captured_at=q['captured_at'],
                kickoff_iso=q['kickoff_iso'],bookmaker='Pinnacle',league_name=q['league_name'],
                capture_mode=q.get('capture_mode'),actual_start_verified=False,
                identity_method='exact_pair_round_dated_edition_v1',tour_id=str(row['tour_id']),
                round_id=str(row['round_id']),player1_id=str(row['player1_id']),player2_id=str(row['player2_id'])),None
