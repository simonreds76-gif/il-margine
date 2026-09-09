"""Daily comparison snapshots. No synthetic quotes, selections or network calls."""
from __future__ import annotations
import csv
import hashlib
import json
import math
import runpy
import unicodedata
from datetime import datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from goalscorer_penalty_utils import penalty_transfer_info, best_name_match

ROOT = Path(__file__).resolve().parents[1]
LEAGUES = {'serie-a':'Serie A','epl':'Premier League','la-liga':'La Liga','bundesliga':'Bundesliga','ligue-1':'Ligue 1'}

def norm(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(value or '')).lower() if c.isalnum())

def fingerprint(fixture):
    content = [fixture.get('lineup_type','')]
    for side in ('home','away'):
        content += [sorted(norm(n) for n in fixture.get(side+'_players', [])), fixture.get(side+'_formation','')]
    return hashlib.sha256(json.dumps(content,sort_keys=True).encode()).hexdigest()[:20]

def read_json(path, fallback=None):
    try: return json.loads(Path(path).read_text(encoding='utf-8-sig'))
    except (OSError, ValueError): return fallback if fallback is not None else {}

def number(value):
    if value is None or isinstance(value,bool) or value == '': return None
    try: n=float(value)
    except (TypeError,ValueError): return None
    return n if math.isfinite(n) else None

def instant(value):
    try:
        dt=datetime.fromisoformat(str(value).replace('Z','+00:00'))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except (ValueError,TypeError): return None

def fixture_key(f):
    return (str(f.get('match_date',''))[:10],norm(f.get('home_team')),norm(f.get('away_team')))

def confirmed_signatures(path):
    return {fixture_key(f):fingerprint(f) for f in read_json(path).get('fixtures',[]) if f.get('lineup_type')=='standard'}

def has_new_confirmed(before, path):
    now=datetime.now(timezone.utc)
    return any(f.get('lineup_type')=='standard' and before.get(fixture_key(f))!=fingerprint(f)
               and (instant(f.get('kickoff_utc')) or now-timedelta(days=1))>now
               for f in read_json(path).get('fixtures',[]))

def seed_lineup_context(odds_rows, lineup_map):
    """Identity-only inputs permit pricing without a market. Never become odds rows."""
    result=list(odds_rows)
    seen={(r['match_date'],norm(r['home_team']),norm(r['away_team']),norm(r['player_name'])) for r in result}
    for key,f in lineup_map.items():
        if not key[0]: continue
        for side in ('home','away'):
            keepers={norm(e.get('name')) for e in f.get(side+'_starters',[]) if e.get('role_group')=='GK'}
            for name in f.get(side+'_players',[]):
                identity=(*fixture_key(f),norm(name))
                if identity in seen or norm(name) in keepers: continue
                result.append(dict(match_date=f['match_date'],home_team=f['home_team'],away_team=f['away_team'],
                    player_name=name,player_team=f[side+'_team'],bookmaker='',competition='',
                    odds_decimal=0.0,implied_prob=0.0,captured_at='',kickoff_at=f.get('kickoff_utc',''),
                    source='lineup_context_only',notes='',board_context_only=True))
                seen.add(identity)
    return sorted(result,key=lambda r:(r['match_date'],r['home_team'],r['away_team'],r.get('captured_at','')))

def build_board(root=ROOT, now=None):
    now=now or datetime.now(timezone.utc)
    fixtures=[]
    kits={norm(k):v for k,v in read_json(root/'data/goalscorer/team-kit-colors.json').items() if isinstance(v,dict)}
    logos=read_json(root/'data/goalscorer/team-logo-map.json').get('leagues',{})
    team_key = runpy.run_path(str(ROOT/'scripts/goalscorer-model.py'))['_team_key']
    def price_key(row):
        return (str(row.get('match_date') or '')[:10], norm(team_key(row.get('home_team') or '')),
                norm(team_key(row.get('away_team') or '')), norm(team_key(row.get('player_team') or '')),
                norm(row.get('canonical_player_name') or row.get('player_name')))
    raw_quotes=[]
    archive=root/'data/goalscorer/goalscorer-odds-history.csv'
    if archive.exists():
        with archive.open(encoding='utf-8-sig',newline='') as handle:
            raw_quotes=[r for r in csv.DictReader(handle) if norm(r.get('bookmaker'))=='bet365'
                        and str(r.get('match_date') or '')[:10]>= (now-timedelta(hours=4)).date().isoformat()]
    for league,label in LEAGUES.items():
        prefix='' if league=='serie-a' else league+'-'
        lineup_payload=read_json(root/'data/goalscorer'/f'{prefix}confirmed-lineups.json')
        out=root/'data/goalscorer'/(league if league!='serie-a' else '')
        forecast_payload=read_json(out/'fair-odds-player-forecasts.json')
        forecasts={}
        for r in forecast_payload.get('players',[]):
            forecasts[price_key(r)]=r
        quotes={}
        try:
            with (out/'goalscorer-live-comparison.csv').open(encoding='utf-8-sig',newline='') as handle:
                for r in csv.DictReader(handle):
                    if norm(r.get('bookmaker'))!='bet365': continue
                    key=price_key(r)
                    if (r.get('captured_at') or '')>(quotes.get(key,{}).get('captured_at') or ''): quotes[key]=r
        except OSError: pass
        # A real quote is still useful when model identity/history is missing.
        for r in raw_quotes:
            key=price_key(r)
            if (r.get('captured_at') or '')>(quotes.get(key,{}).get('captured_at') or ''): quotes[key]=r
        hierarchy=read_json(root/'data/goalscorer'/f'{league}-penalty-takers.json')
        hierarchy={norm(k):v for k,v in hierarchy.items() if isinstance(v,dict)}
        for f in lineup_payload.get('fixtures',[]):
            kickoff=instant(f.get('kickoff_utc'))
            if not kickoff or not now-timedelta(hours=4)<=kickoff<=now+timedelta(days=3): continue
            teams=[]
            for side in ('home','away'):
                team=f.get(side+'_team','')
                names=f.get(side+'_players',[])
                entries={norm(e.get('name')):e for e in f.get(side+'_starters',[])}
                starters=[dict(entries.get(norm(n),{}),name=n) for n in names]
                duty=penalty_transfer_info(hierarchy.get(norm(team)),names)
                players=[]
                for index,e in enumerate(starters):
                    name=e.get('name','')
                    key=price_key(dict(f,player_team=team,player_name=name))
                    model=forecasts.get(key,{})
                    quote=quotes.get(key,{})
                    if not quote:
                        same_team={k[-1]:v for k,v in quotes.items() if k[:-1]==key[:-1]}
                        # Use the same ambiguity-rejecting name matcher as the model.
                        match=best_name_match(name,[v.get('canonical_player_name') or v.get('player_name','') for v in same_team.values()])
                        quote=next((v for v in same_team.values() if match and match==(v.get('canonical_player_name') or v.get('player_name'))),{})
                    p=number(model.get('probability'))
                    valid=model.get('lineup_fingerprint')==fingerprint(f) and model.get('allocation_status') in {'confirmed_roster','expected_roster','estimated_roster'} and model.get('method') in {'model','fallback'}
                    limited=bool(model.get('limited_data') or model.get('context_only_prior') or model.get('method')=='fallback')
                    if not valid or model.get('trust_tier') == 'T3' or p is None or not 0<p<1: p=None
                    odds=number(quote.get('odds_decimal'))
                    if odds is not None and odds<=1: odds=None
                    capture=instant(quote.get('captured_at'))
                    changed=instant(f.get('changed_at'))
                    fresh=bool(capture and timedelta(0)<=now-capture<=timedelta(minutes=65) and (not changed or capture>=changed))
                    model_time=instant(model.get('generated_at') or forecast_payload.get('generated_at'))
                    if model_time and model_time>=kickoff: p=None
                    reason = None if p else ('Goalkeepers are not priced by this outfield model.' if e.get('role_group')=='GK' else
                        'Player history could not be matched.' if not model else
                        'The squad could not be fully resolved.' if model.get('allocation_status')=='incomplete_roster' else
                        'Waiting for a forecast matching the latest lineup.')
                    active=best_name_match(name,[duty.get('active_taker','')]) is not None
                    players.append(dict(id=str(e.get('player_id') or norm(name)),name=name,number=e.get('shirt_number'),
                        role=e.get('role_group') or '',lineIndex=e.get('line_index'),positionId=e.get('position_id'),
                        photoUrl=f"https://images.fotmob.com/image_resources/playerimages/{e['player_id']}.png" if str(e.get('player_id','')).isdigit() else None,
                        modelProbability=p,fairOdds=round(1/p,2) if p else None,bookmakerOdds=odds,
                        priceCapturedAt=quote.get('captured_at') or None,priceFresh=fresh,
                        gapPp=round(100*(p-1/odds),2) if p and odds and fresh and kickoff>now and not limited else None,
                        modelEvPct=round(100*(p*odds-1),2) if p and odds and fresh and kickoff>now and not limited else None,
                        expectedMinutes=number(model.get('expected_minutes')),penaltyActive=active,
                        penaltyInheritedFrom=duty.get('inherited_from') if active and duty.get('penalty_transfer') else None,
                        modelVersion=model.get('model_version'),modelGeneratedAt=model_time.isoformat() if model_time else None,
                        pricingStatus=('limited_data' if limited else 'available') if p else 'goalkeeper_unpriced' if e.get('role_group')=='GK' else 'awaiting_model',
                        pricingReason=('Estimate uses limited player history or a positional baseline; no value gap is published.' if limited and p else reason),
                        bookmakerStatus='quoted' if odds else 'not_in_feed',
                        bookmakerReason=None if odds else 'No matched Bet365 anytime-goalscorer quote in the latest captured feed.',
                        historyMatches=model.get('history_matches'), rateBasis=model.get('rate_basis')))
                team_logos=logos.get(league,{}).get('teams',{})
                logo=next((v.get('logo_path') for k,v in team_logos.items() if norm(k)==norm(team) or norm(v.get('fotmob_name'))==norm(team)),None)
                kit=kits.get(norm(team),{})
                teams.append(dict(name=team,formation=f.get(side+'_formation',''),players=players,logoPath=logo,
                    primaryColor=kit.get('primary'),secondaryColor=kit.get('secondary'),
                    substitutes=f.get(side+'_subs',[]),activePenaltyTaker=duty.get('active_taker') or None,
                    penaltyInheritedFrom=duty.get('inherited_from') if duty.get('penalty_transfer') else None,
                    lineupComplete=len(players)==11 and len({norm(p['name']) for p in players})==11))
            fixtures.append(dict(id=f'{league}-{f.get("fotmob_match_id") or "-".join(fixture_key(f))}',league=league,competition=label,
                kickoffUtc=kickoff.isoformat(),date=kickoff.astimezone(ZoneInfo('Europe/London')).date().isoformat(),
                lineupStatus='confirmed' if f.get('lineup_type')=='standard' else 'expected' if f.get('lineup_type')=='predicted' else 'pending',
                lineupObservedAt=f.get('observed_at'),lineupChangedAt=f.get('changed_at'),teams=teams))
    return dict(schemaVersion=1,generatedAt=now.isoformat(),referenceBookmaker='Bet365',
                leaguesCovered=list(LEAGUES.values()),fixtures=sorted(fixtures,key=lambda f:f['kickoffUtc']))

def record_daily_board(payload, root=ROOT):
    """Freeze the first fresh official comparison per player, including negative EV.

    These are unit-stake evaluation records, not recommendations or placed bets.
    They stay separate from the previous top-five selection policy.
    """
    for league in LEAGUES:
        path=root/'data/goalscorer'/f'fair-odds-daily-{league}.csv'
        rows=[]
        if path.exists():
            with path.open(encoding='utf-8-sig',newline='') as handle: rows=list(csv.DictReader(handle))
        seen={(r['date'],r['match'],r['team'],r['player']) for r in rows}
        added=0
        for f in payload['fixtures']:
            if f['league']!=league or f['lineupStatus']!='confirmed': continue
            for team in f['teams']:
                if not team['lineupComplete']: continue
                for p in team['players']:
                    if p.get('gapPp') is None: continue
                    key=(f['date'],f"{f['teams'][0]['name']} vs {f['teams'][1]['name']}",team['name'],p['name'])
                    if key in seen: continue
                    rows.append(dict(date=key[0],match=key[1],team=key[2],player=key[3],kickoff=f['kickoffUtc'],
                        home_team=f['teams'][0]['name'],away_team=f['teams'][1]['name'],competition=f['competition'],
                        signal_type='fair_odds_daily_board',tracking_tier='first_official_comparison',
                        player_id=p['id'],market_player_name=p['name'],model_p_atgs=p['modelProbability'],
                        model_fair_odds=p['fairOdds'],model_version=p['modelVersion'],model_calibration_version='raw',
                        best_bookmaker='Bet365',best_bookmaker_odds=p['bookmakerOdds'],ev=p['modelEvPct']/100,
                        captured_at=p['priceCapturedAt'],compared_at=p['modelGeneratedAt'],recorded_at=payload['generatedAt'],
                        recommended_stake_units='0',evaluation_stake_units='1',public_action='comparison_only',
                        public_policy_reason='daily_first_official_v1',super_sub_contract_verified='0',
                        super_sub_tracking_policy='bet365_automatic_20260909',
                        settled='',goals_scored='',bet_outcome='',settled_at='',pnl_units='',settlement_note=''))
                    seen.add(key);added+=1
        if added:
            path.parent.mkdir(parents=True,exist_ok=True)
            fields=list(dict.fromkeys(k for row in rows for k in row))
            with path.open('w',encoding='utf-8',newline='') as handle:
                writer=csv.DictWriter(handle,fieldnames=fields);writer.writeheader();writer.writerows(rows)

def write_board(output=None, record=True):
    output=output or ROOT/'public/fair-odds-lab/daily-board.json'
    payload=build_board()
    if record: record_daily_board(payload)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
    print(f'Daily Lab: {len(payload["fixtures"])} fixtures -> {output}')

if __name__=='__main__': write_board()
