"""Private Air Control research alerts. Screens opportunity, never invents EV."""
from collections import Counter
from datetime import datetime, timezone, timedelta
from hashlib import sha256
from pathlib import Path
from statistics import median
from zoneinfo import ZoneInfo
import argparse
import json
import os
import requests
from aerial_data import ROOT, read, save, utc, number

VERSION = 'air-control-watch-v1'
POLICY = dict(player_matches=5, player_minutes=450, aerial_attempts=20,
              headers_per90=0.60, height_gap_cm=3, duel_gap_pp=10,
              player_duel_pct=55, corners=4, crosses=15,
              team_matches=3, defender_count=3, max_player_age_days=45,
              max_team_age_days=30, max_fixtures_per_run=3,
              max_players_per_fixture=3)


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def prior_matches(history, fixture, now):
    cutoff = min(now, utc(fixture['kickoff']))
    return sorted((m for m in history if m['id'] != fixture['id'] and utc(m['date']) < cutoff
                   and m['date'][:10] < fixture['kickoff'][:10]), key=lambda m: m['date'], reverse=True)


def player_stats(matches, player_id):
    rows = []
    for match in matches:
        for player in match['players']:
            if str(player['id']) == str(player_id) and number(player.get('minutes')) and player['minutes'] > 0:
                rows.append({**player, 'fixture_id': match['id'], 'date': match['date']})
        if len(rows) >= 10:
            break
    rows = rows[:10]
    headed = [p for p in rows if number(p.get('headed_shots')) and p['headed_shots'] >= 0]
    duels = [p for p in rows if number(p.get('aerials_won')) and number(p.get('aerials_attempted'))
             and 0 <= p['aerials_won'] <= p['aerials_attempted']]
    minutes = sum(p['minutes'] for p in headed)
    attempts = sum(p['aerials_attempted'] for p in duels)
    result = dict(matches=len(headed), minutes=minutes, latest=rows[0]['date'] if rows else None,
                  headers=sum(p['headed_shots'] for p in headed),
                  headers_per90=90 * sum(p['headed_shots'] for p in headed) / minutes if minutes else None,
                  header_hit_matches=sum(p['headed_shots'] > 0 for p in headed),
                  aerial_attempts=attempts, aerial_won=sum(p['aerials_won'] for p in duels),
                  duel_pct=100 * sum(p['aerials_won'] for p in duels) / attempts if attempts else None,
                  median_minutes=median(p['minutes'] for p in rows) if rows else None,
                  fixture_ids=[p['fixture_id'] for p in rows])
    for field in ('headed_sot', 'headed_goals', 'set_piece_headers'):
        valid = [p for p in headed if number(p.get(field)) and 0 <= p[field] <= p['headed_shots']]
        result[field] = dict(count=sum(p[field] for p in valid), matches=len(valid),
                             hit_matches=sum(p[field] > 0 for p in valid))
    return result


def team_stats(matches, team_id):
    rows = [m for m in matches if team_id in (m['home_id'], m['away_id'])][:5]
    result = {'latest': rows[0]['date'] if rows else None, 'fixture_ids': [r['id'] for r in rows]}
    for field in ('corners', 'crosses_attempted', 'headed_shots_against'):
        values = [d[field] for m in rows for d in m['delivery'] if d['team_id'] == team_id
                  and number(d.get(field)) and d[field] >= 0]
        result[field] = dict(average=sum(values)/len(values) if values else None, matches=len(values))
    return result


def fresh(date, now, days):
    return bool(date) and timedelta(0) <= now - utc(date) <= timedelta(days=days)


def evaluate(payload, history, now):
    exclusions = Counter()
    output = []
    # An unchanged/stale public file is not permission to send old signals.
    if not fresh(payload.get('generated_at'), now, 0.125):
        return [], {'stale_snapshot': 1}
    for fixture in payload.get('fixtures', []):
        state = fixture.get('state')
        if state not in ('expected', 'confirmed'):
            exclusions['no_lineup'] += 1; continue
        kickoff = utc(fixture['kickoff'])
        if not now < kickoff <= now + timedelta(hours=30) or now >= utc(fixture['valid_until']):
            exclusions['expired_or_outside_window'] += 1; continue
        if not fresh(fixture.get('observed_at'), now, 2/24 if state == 'confirmed' else 30/24):
            exclusions['stale_lineup'] += 1; continue
        teams = fixture['teams']
        ids = [p['id'] for t in teams for p in t['players']]
        if len(teams) != 2 or any(len(t['players']) != 11 for t in teams) or len(set(ids)) != 22:
            exclusions['incomplete_lineup'] += 1; continue
        prior = prior_matches(history, fixture, now)
        candidates = []
        stats = {p['id']: player_stats(prior, p['id']) for t in teams for p in t['players']}
        for index, team in enumerate(teams):
            opponent = teams[1-index]
            defenders = [p for p in opponent['players'] if p['role'] == 'DEF']
            if len(defenders) < POLICY['defender_count'] or any(p['role'] == 'UNK' for p in opponent['players']):
                exclusions['defender_identity_coverage'] += 1; continue
            heights = [p['height_cm'] for p in defenders if number(p.get('height_cm'))]
            defence_height = sum(heights)/len(heights) if len(heights) == len(defenders) else None
            duel_defenders = [stats[p['id']] for p in defenders
                              if stats[p['id']]['aerial_attempts'] >= POLICY['aerial_attempts']
                              and fresh(stats[p['id']]['latest'], now, POLICY['max_player_age_days'])]
            defence_duel_pct = (100*sum(s['aerial_won'] for s in duel_defenders)/sum(s['aerial_attempts'] for s in duel_defenders)
                                if len(duel_defenders) >= POLICY['defender_count'] else None)
            supply = team_stats(prior, team['id'])
            defence = team_stats(prior, opponent['id'])
            if not fresh(supply['latest'], now, POLICY['max_team_age_days']):
                exclusions['stale_delivery_history'] += 1; continue
            supply_flags = [field for field, threshold in (('corners', POLICY['corners']), ('crosses_attempted', POLICY['crosses']))
                            if supply[field]['matches'] >= POLICY['team_matches'] and supply[field]['average'] >= threshold]
            if not supply_flags:
                exclusions['delivery_below_screen'] += 1; continue
            for player in team['players']:
                if player['role'] in ('GK', 'UNK'):
                    continue
                stat = stats[player['id']]
                if stat['matches'] < POLICY['player_matches'] or stat['minutes'] < POLICY['player_minutes'] or not fresh(stat['latest'], now, POLICY['max_player_age_days']):
                    exclusions['player_history_coverage'] += 1; continue
                if stat['headers_per90'] < POLICY['headers_per90'] or stat['median_minutes'] < 60:
                    exclusions['limited_heading_or_minutes'] += 1; continue
                height_gap = player['height_cm'] - defence_height if number(player.get('height_cm')) and defence_height is not None else None
                duel_gap = stat['duel_pct'] - defence_duel_pct if stat['aerial_attempts'] >= POLICY['aerial_attempts'] and defence_duel_pct is not None else None
                height_flag = height_gap is not None and height_gap >= POLICY['height_gap_cm']
                duel_flag = duel_gap is not None and duel_gap >= POLICY['duel_gap_pp'] and stat['duel_pct'] >= POLICY['player_duel_pct']
                if not height_flag and not duel_flag:
                    exclusions['no_supported_mismatch'] += 1; continue
                conceded = defence['headed_shots_against']
                concession_flag = fresh(defence['latest'], now, POLICY['max_team_age_days']) and conceded['matches'] >= 3 and conceded['average'] >= 3
                candidates.append(dict(player_id=player['id'], player=player['name'], team_id=team['id'], team=team['name'],
                    height_cm=player['height_cm'], defence_height_cm=defence_height, height_gap_cm=height_gap,
                    defence_duel_pct=defence_duel_pct, duel_gap_pp=duel_gap,
                    height_flag=height_flag, duel_flag=duel_flag, concession_flag=concession_flag,
                    supporting_factors=2+int(height_flag)+int(duel_flag)+int(concession_flag),
                    history=stat, delivery=supply, opposition=defence,
                    markets_to_check=['1+ headed shot'] + (['1+ headed shot on target'] if stat['headed_sot']['matches'] >= 5 and stat['headed_sot']['hit_matches'] >= 2 else [])
                        + (['headed goal'] if stat['headed_goals']['matches'] >= 5 and stat['headed_goals']['count'] >= 2 else []),
                    fair_odds=None, available_odds=None, ev=None))
        candidates.sort(key=lambda c: (-c['supporting_factors'], -c['history']['headers_per90'], -c['history']['minutes'], c['player_id']))
        if candidates:
            output.append(dict(fixture_id=fixture['id'], kickoff=fixture['kickoff'], stage=state,
                match=' v '.join(t['name'] for t in teams), observed_at=fixture['observed_at'], valid_until=fixture['valid_until'],
                lineup_ids=ids, snapshot_version=payload['version'], candidates=candidates[:POLICY['max_players_per_fixture']]))
    return sorted(output, key=lambda r: (r['stage'] != 'confirmed', r['kickoff'])), dict(exclusions)


def number_text(value, digits=1):
    return f'{value:.{digits}f}' if number(value) else 'unavailable'


def message(row, removed=()):
    kickoff = utc(row['kickoff']).astimezone(ZoneInfo('Europe/London'))
    lines = ['AIR CONTROL | PRIVATE WATCHLIST', row['match'],
             f"{kickoff:%d %b %H:%M %Z} | {'CONFIRMED XI' if row['stage']=='confirmed' else 'EXPECTED XI: recheck when confirmed'}"]
    if removed:
        lines += ['Earlier names withdrawn: '+', '.join(removed)]
    for c in row['candidates']:
        h=c['history']; supply=c['delivery']
        lines += ['', f"{c['player']} ({c['team']})", f"Headed shots: {h['headers']} in {h['matches']} appearances / {h['minutes']:.0f} mins; {h['headers_per90']:.2f} per 90.",
                  f"At least one header in {h['header_hit_matches']}/{h['matches']}; median minutes {h['median_minutes']:.0f}."]
        if c['height_flag']:
            lines += [f"Height: {c['height_cm']:.0f}cm vs opposing defenders' mean {c['defence_height_cm']:.1f}cm (+{c['height_gap_cm']:.1f}cm)."]
        if c['duel_flag']:
            lines += [f"Aerial duels won: {h['duel_pct']:.0f}% from {h['aerial_attempts']:.0f} attempts vs defenders' pooled {c['defence_duel_pct']:.0f}%."]
        lines += [f"Team supply: {number_text(supply['corners']['average'])} corners, {number_text(supply['crosses_attempted']['average'])} crosses per match ({len(supply['fixture_ids'])} matches)."]
        if c['concession_flag']:
            lines += [f"Opponent conceded {c['opposition']['headed_shots_against']['average']:.1f} headers per match."]
        for key, label in (('headed_sot','Headed shots on target'),('headed_goals','Headed goals')):
            m=h[key]
            lines += [f"{label}: {m['count']} in {m['matches']} covered appearances." if m['matches'] else f'{label}: historical breakdown unavailable.']
        lines += ['Inspect: '+', '.join(c['markets_to_check'])+'.']
    lines += ['', 'Research shortlist, not a priced bet. Defender comparison is a pool, not an assumed marker. No fair odds or EV until the exact market price and probability are verified.',
              'https://ilmargine.bet/fair-odds-lab/aerial']
    return '\n'.join(lines)


def settle(ledger, history):
    matches = {m['id']: m for m in history}
    for record in ledger:
        match=matches.get(record['fixture_id'])
        if not match or utc(match['date']) < utc(record['captured_at']):
            continue
        for candidate in record['candidates']:
            player=next((p for p in match['players'] if str(p['id'])==candidate['player_id']),None)
            candidate['outcomes']={key: player.get(key) if player and number(player.get(key)) else None
                                   for key in ('minutes','headed_shots','headed_sot','headed_goals')}
            candidate['result_status']='settled_counts' if player and number(player.get('headed_shots')) else 'outcome_unavailable'
        record['result_source_date']=match['date']


def send(text, token, chat):
    # Destination is exclusively the existing private Ops channel, never the
    # public tip channel. Do not log a requests exception containing bot URLs.
    try:
        response=requests.post(f'https://api.telegram.org/bot{token}/sendMessage',
            json={'chat_id':chat,'text':text,'disable_web_page_preview':True},timeout=20)
        body=response.json()
        if response.status_code==200 and body.get('ok') is True:
            return body['result']['message_id']
    except (requests.RequestException, ValueError, KeyError):
        pass
    return None


def run(root=ROOT, now=None, transmit=False, sender=send):
    now=now or datetime.now(timezone.utc)
    directory=root/'data/aerial/alerts'
    payload=read(root/'public/fair-odds-lab/aerial.json',{})
    history=read(root/'data/aerial/history.json.gz',{}).get('matches',[])
    rows, exclusions=evaluate(payload,history,now)
    state=read(directory/'state.json',{'schema_version':1,'fixtures':{}})
    ledger=read(directory/'ledger.json',[])
    settle(ledger,history)
    captures={(r['fixture_id'],r['stage']) for r in ledger}
    for row in rows:
        if transmit and (row['fixture_id'],row['stage']) not in captures:
            ledger.append({**row,'version':VERSION,'policy':POLICY,'captured_at':now.isoformat(),
                           'evidence_hash':digest(row),'cohort':'prospective_research_no_stake'})
    token=os.environ.get('OPS_ALERT_TELEGRAM_BOT_TOKEN','').strip()
    chat=os.environ.get('OPS_ALERT_TELEGRAM_CHAT_ID','').strip()
    ready=[]
    for row in rows:
        prior=state['fixtures'].get(row['fixture_id'],{})
        if prior.get(row['stage']):
            continue
        removed=[name for pid,name in prior.get('players',{}).items() if pid not in {c['player_id'] for c in row['candidates']}]
        ready.append((row,removed))
    # A confirmed XI can invalidate an earlier expected shortlist altogether.
    rows_ids={r['fixture_id'] for r in rows}
    for f in payload.get('fixtures',[]):
        prior=state['fixtures'].get(f['id'],{})
        if f['id'] not in rows_ids and f.get('state')=='confirmed' and prior.get('expected') and not prior.get('confirmed') \
                and now < utc(f['kickoff']) and now < utc(f['valid_until']) and fresh(payload.get('generated_at'),now,0.125):
            ready.append((dict(fixture_id=f['id'],kickoff=f['kickoff'],stage='confirmed',match=' v '.join(t['name'] for t in f['teams']),candidates=[]),list(prior.get('players',{}).values())))
    sent=[]
    previews=[]
    for row,removed in ready[:POLICY['max_fixtures_per_run']]:
        text=message(row,removed)
        # Never truncate a player's evidence or drop the pricing limitation.
        while len(text)>3900 and len(row['candidates'])>1:
            row={**row,'candidates':row['candidates'][:-1]}; text=message(row,removed)
        previews.append(text)
        if transmit and token and chat:
            receipt=sender(text,token,chat)
            if receipt is not None:
                previous=state['fixtures'].setdefault(row['fixture_id'],{})
                previous.update({row['stage']:now.isoformat(),'message_id':receipt,
                    'players':{c['player_id']:c['player'] for c in row['candidates']},'kickoff':row['kickoff']})
                sent.append({'fixture_id':row['fixture_id'],'stage':row['stage'],'message_id':receipt})
                save(directory/'state.json',state)
    report=dict(version=VERSION,generated_at=now.isoformat(),policy=POLICY,shortlist=rows,exclusions=exclusions,
                status='sent' if sent else 'no_new_qualifiers' if not ready else 'credentials_missing' if transmit and (not token or not chat) else 'delivery_failed' if transmit else 'preview',
                sent=sent,prospective_captures=len(ledger),telegram_previews=previews,
                roi=None,roi_reason='Research counts only; no captured market prices or real stakes.')
    save(directory/'ledger.json',ledger);save(directory/'latest.json',report)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--send',action='store_true');parser.add_argument('--root',type=Path,default=ROOT)
    args=parser.parse_args();report=run(args.root,transmit=args.send)
    print(json.dumps({k:report[k] for k in ('status','prospective_captures','sent','exclusions')}))
    if not args.send:
        print('\n\n'.join(report['telegram_previews']))
    if report['status'] in ('credentials_missing','delivery_failed'):
        raise SystemExit(1)
