"""Bookmaker-contract settlement, separate from named-player model accuracy."""
from skyline_model import utc, valid


def evidence(page, row, players, lineup_ok):
    content = page.get('content') or {}
    feed = (content.get('matchFacts') or {}).get('events') or {}
    events = feed.get('events')
    result = dict(complete=False, substitutions=[], roster={})
    if not lineup_ok or feed.get('ongoing') is not False or not isinstance(events, list):
        return result
    active = {p['id']:p for p in players}
    for side, tid in [('homeTeam', row['home_id']), ('awayTeam', row['away_id'])]:
        squad = (content.get('lineup') or {}).get(side) or {}
        if not isinstance(squad.get('subs'), list): return result
        for bucket in ('starters', 'subs'):
            for p in squad.get(bucket, []):
                pid = str(p.get('id'))
                if pid in result['roster'] or pid=='None': return result
                result['roster'][pid] = dict(team_id=tid, starter=bucket=='starters',
                    played=True if pid in active else False if bucket=='subs' and not p.get('performance') else None)
    for e in events:
        if not isinstance(e, dict): return result
        if e.get('type') != 'Substitution': continue
        swap = e.get('swap')
        if type(e.get('isHome')) is not bool or not valid(e.get('time')): return result
        if not isinstance(swap, list) or len(swap)!=2: return result
        pin, pout = [str(p.get('id')) for p in swap]
        tid = row['home_id'] if e['isHome'] else row['away_id']
        if pin==pout or any(result['roster'].get(pid, {}).get('team_id')!=tid for pid in (pin,pout)): return result
        added = e.get('overloadTime') or 0
        if not valid(added) or not 0 < e['time'] <= 90 or added < 0: return result
        result['substitutions'].append(dict(player_in=pin, player_out=pout, team_id=tid,
                                            time=[e['time'], added]))
    ins = [e['player_in'] for e in result['substitutions']]
    outs = [e['player_out'] for e in result['substitutions']]
    if len(ins)!=len(set(ins)) or len(outs)!=len(set(outs)): return result
    # Every observed substitute appearance must have an explicit incoming event.
    if any(not p['starter'] and p['id'] not in ins for p in players): return result
    result['complete'] = True
    return result


def settle(record, match, now):
    """None = missing/ambiguous evidence, never convert it to a losing bet."""
    quote = record.get('quote', {})
    contract = quote.get('contract')
    if contract not in ('paddy_named_player_v1', 'paddy_super_sub_v1'): return None
    pid, tid = record['player_id'], record['team_id']
    rows = {p['id']:p for p in match['players'] if p.get('team_id')==tid}
    p = rows.get(pid)
    proof = match.get('settlement_evidence', {})
    def outcome(status, own=None, chain=None, reason=''):
        return dict(status=status, headed_sot=own, model_status=('win' if own>=1 else 'loss')
                    if own is not None and p and p.get('starter') is True else None,
                    minutes=p.get('minutes') if p else None, contract=contract,
                    substitution_chain=chain or [pid], reason=reason,
                    source_sha256=match.get('source_sha256'), settled_at=now.isoformat())
    if not p:
        member = proof.get('roster', {}).get(pid, {})
        if proof.get('complete') and member.get('team_id')==tid and member.get('played') is False:
            return outcome('void', reason='No participation in completed match')
        return None
    def count(player):
        s,h = player.get('headed_sot'), player.get('headed_shots')
        return s if valid(s) and valid(h) and 0<=s<=h else None
    own = count(p)
    if own is None: return None
    if own>=1: return outcome('win', own, reason='Named player recorded headed SOT')
    if contract=='paddy_named_player_v1':
        return outcome('loss', own, reason='Named player participated; no headed SOT')
    if not proof.get('complete'): return None
    chain = [pid]; last_time = [-1, 0]
    while True:
        swaps = [s for s in proof['substitutions'] if s['player_out']==chain[-1]]
        if not swaps: return outcome('loss', own, chain, 'Complete substitution chain; no headed SOT')
        if len(swaps)!=1: return None
        sub = swaps[0]; incoming = sub['player_in']
        if sub['team_id']!=tid or sub['time']<=last_time or incoming in chain: return None
        player = rows.get(incoming)
        if not player or player.get('starter') is not False: return None
        sot = count(player)
        if sot is None: return None
        chain.append(incoming)
        if sot>=1: return outcome('win', own, chain, 'Super Sub replacement recorded headed SOT')
        last_time = sub['time']


def best_quote(quotes):
    """Price ranking uses only the named-player event; no invented promo uplift.

    Super Sub includes the named-player outcome. Its extra coverage is recorded
    for settlement but never used to increase the probability or selection EV.
    """
    eligible = [q for q in quotes if q.get('market')=='1+ headed shot on target']
    return max(eligible, key=lambda q:(q['odds'], q['captured_at'], q['bookmaker'])) if eligible else None
