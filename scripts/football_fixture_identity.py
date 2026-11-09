"""Paper-count fixture identity. Never use price, line or a new date as a new bet.

The five covered domestic leagues play one home leg per ordered pair per season.
That key remains valid when providers change event IDs or kickoff dates. Verified
canonical Odds-API event IDs additionally bridge a reschedule across seasons.
Cups/other competitions get no season-wide join. Original rows are never edited.
"""
import csv
from collections import defaultdict
from datetime import date
from functools import lru_cache
from pathlib import Path
from football_team_names import football_form_team_key as team_key

TOP_FIVE={'epl','serie-a','la-liga','bundesliga','ligue-1'}
ALIASES={'premier-league':'epl','england-premier-league':'epl','laliga':'la-liga',
         'spain-la-liga':'la-liga','ligue-1':'ligue-1','serie-a':'serie-a'}
# These adapters retain target Odds-API event_id; source_event_id is NOT this ID.
CANONICAL_SOURCES={'odds_api_io','moviodds_bet365','grosvenor_direct'}

def fixture(row):
    day=str(row.get('match_date') or row.get('kickoff_at') or row.get('kickoff_utc') or '')[:10]
    league=str(row.get('league_slug') or row.get('league') or row.get('competition') or '').lower().replace(' ','-')
    league=ALIASES.get(league,league)
    home,away=team_key(row.get('home_team')),team_key(row.get('away_team'))
    try: date.fromisoformat(day)
    except ValueError: return None
    return (day,league,home,away) if league and home and away and home!=away else None

class FixtureIndex:
    def __init__(self, quotes=()):
        self.events=defaultdict(set); self.fixtures=defaultdict(set)
        for row in quotes:
            key=fixture(row); event=str(row.get('event_id') or '')
            if not key or not event or row.get('source') not in CANONICAL_SOURCES: continue
            self.events[event].add(key[1:]); self.fixtures[key].add(event)

    def keys(self,row):
        key=fixture(row)
        if not key: return {('legacy',str(row.get('match_id') or row.get('contract_id') or row.get('pick_id') or ''))}
        day,league,home,away=key; keys={('dated',*key)}
        if league in TOP_FIVE:
            played=date.fromisoformat(day); season=played.year-(played.month<7)
            keys.add(('league-home-leg',season,league,home,away))
        for event in self.fixtures.get(key,()):
            # A provider reusing one ID for different teams cannot merge fixtures.
            if len(self.events[event])==1: keys.add(('odds-api',event,league,home,away))
        return keys

    def first_only(self,existing,fresh):
        seen=set().union(*(self.keys(r) for r in existing)) if existing else set()
        output=list(existing)
        for row in fresh:
            keys=self.keys(row)
            if not keys & seen: output.append(row)
            seen.update(keys)
        return output

@lru_cache(maxsize=1)
def archive_index(root):
    rows=[]
    for rel in ('data/team-shots/team-shots-odds-history.csv','data/corners-ou/bet365-corners-odds-history.csv'):
        path=Path(root)/rel
        if path.exists():
            with path.open(encoding='utf-8-sig',newline='') as f: rows.extend(csv.DictReader(f))
    return FixtureIndex(rows)
