"""Offline, identity-checked extraction of observed player targets; no imputation."""
from collections import Counter
from pathlib import Path
from hashlib import sha256
import json,math
from datetime import datetime, timezone
def _extract_stat_pair(stats, key):
    pairs = []
    for group in stats.get("Periods", {}).get("All", {}).get("stats", []):
        for item in group.get("stats", []):
            if item.get("key") != key:
                continue
            values = item.get("stats", [])
            if len(values) != 2 or any(count(v) is None for v in values):
                return None
            pairs.append(tuple(count(v) for v in values))
    return pairs[0] if pairs and len(set(pairs)) == 1 else None


def count(value):
    if value is None or isinstance(value,bool): return None
    try: x=float(value)
    except (ValueError,TypeError): return None
    return int(x) if math.isfinite(x) and x>=0 and x.is_integer() else None

def stat_values(player):
    values={}
    for group in player.get('stats',[]):
        for item in group.get('stats',{}).values():
            key=item.get('key')
            if not key: continue
            value=item.get('stat',{}).get('value')
            if key in values and values[key]!=value: raise ValueError('conflicting player stat: '+key)
            values[key]=value
    return values

def verified_shots(content, teams, known_players):
    """Only infer zero from a complete, reconciled and attributed event set."""
    shots=content.get('shotmap',{}).get('shots')
    totals=_extract_stat_pair(content.get('stats',{}),'total_shots')
    targets=_extract_stat_pair(content.get('stats',{}),'ShotsOnTarget')
    if not isinstance(shots,list) or not shots or totals is None or targets is None:
        return None,'missing_event_or_team_totals'
    actual=Counter();on_target=Counter();player_counts=Counter();player_sot=Counter();seen=set()
    for shot in shots:
        sid=shot.get('id');tid=count(shot.get('teamId'));pid=count(shot.get('playerId'))
        if sid is None or sid in seen: return None,'missing_or_duplicate_event_id'
        seen.add(sid)
        if tid not in teams or pid not in known_players or known_players[pid]!=tid:
            return None,'unattributed_shot'
        if shot.get('isOwnGoal'): continue
        event=shot.get('eventType')
        if event not in {'Goal','AttemptSaved','Miss','Post'}: return None,'unsupported_event_type'
        actual[tid]+=1;player_counts[pid]+=1
        # isOnTarget is a trajectory flag and also true for blocked attempts.
        if event=='Goal' or (event=='AttemptSaved' and not shot.get('isBlocked')):
            on_target[tid]+=1;player_sot[pid]+=1
    if tuple(actual[t] for t in teams)!=totals or tuple(on_target[t] for t in teams)!=targets:
        return None,'events_disagree_with_team_totals'
    return (player_counts,player_sot),'reconciled_event_totals'

def extract(payload, source_hash):
    page=payload.get('props',{}).get('pageProps',{})
    general=page.get('general',{});content=page.get('content',{})
    if general.get('finished') is not True: raise ValueError('unfinished match')
    lineup=content.get('lineup',{});players=content.get('playerStats',{})
    if str(lineup.get('matchId'))!=str(general.get('matchId')): raise ValueError('match ID mismatch')
    sot=_extract_stat_pair(content.get('stats',{}),'ShotsOnTarget')
    goals={int(t['id']):count(t.get('score')) for t in page.get('header',{}).get('teams',[])}
    shots=content.get('shotmap',{}).get('shots');rows=[];seen=set()
    known_players={int(p['id']):int(lineup[s]['id']) for s in ('homeTeam','awayTeam') for group in ('starters','subs') for p in lineup.get(s,{}).get(group,[]) if count(p.get('id'))}
    verified,event_status=verified_shots(content,[int(general[s]['id']) for s in ('homeTeam','awayTeam')],known_players)
    for idx,side in enumerate(('homeTeam','awayTeam')):
        team=lineup.get(side,{})
        if count(team.get('id'))!=count(general.get(side,{}).get('id')): raise ValueError('team ID mismatch')
        if len(team.get('starters',[]))!=11: raise ValueError('incomplete starting XI')
        opponent=general['awayTeam' if idx==0 else 'homeTeam']
        for started,key in ((True,'starters'),(False,'subs')):
            for person in team.get(key,[]):
                pid=count(person.get('id'))
                if not pid or pid in seen: raise ValueError('missing or duplicate player ID')
                seen.add(pid);player=players.get(str(pid),{})
                if not player: continue
                if count(player.get('id'))!=pid or count(player.get('teamId'))!=count(team['id']): raise ValueError('player/team mismatch')
                stats=stat_values(player);minutes=count(stats.get('minutes_played'))
                if minutes is None: continue # unused bench players are not zero-count appearances
                if minutes>130: raise ValueError('invalid minutes')
                is_keeper=player.get('isGoalkeeper') is True
                saves=count(stats.get('saves')) if is_keeper else None
                conceded=count(stats.get('goals_conceded')) if is_keeper else None
                event_saves=None
                if is_keeper and verified is not None:
                    attempts=[s for s in shots if str(s.get('eventType')).lower()=='attemptsaved' and not s.get('isBlocked') and not s.get('isSavedOffLine')]
                    if all(count(s.get('keeperId')) for s in attempts):
                        event_saves=sum(count(s.get('keeperId'))==pid for s in attempts)
                proxy=(count(sot[1-idx])-goals[int(opponent['id'])]) if is_keeper and sot and count(sot[1-idx]) is not None and goals.get(int(opponent['id'])) is not None else None
                explicit_shots=count(stats.get('total_shots'));explicit_sot=count(stats.get('ShotsOnTarget'))
                event_shots=verified[0][pid] if verified is not None else None
                event_sot=verified[1][pid] if verified is not None else None
                conflict=any(a is not None and b is not None and a!=b for a,b in ((explicit_shots,event_shots),(explicit_sot,event_sot),(saves,event_saves)))
                rows.append({'match_id':general['matchId'],'kickoff':general.get('matchTimeUTCDate'),'league':general.get('leagueName'),
                    'team_id':team['id'],'team':team['name'],'opponent_id':opponent['id'],'player_id':pid,'player':player.get('name'),
                    'started':started,'is_goalkeeper':is_keeper,'minutes':minutes,'shots':explicit_shots,
                    # Published position codes are retained without guessing their meaning.
                    # These describe the completed match, not known pre-match roles.
                    'lineup_position_id':count(person.get('positionId')),
                    'usual_position_id':count(person.get('usualPlayingPositionId')),
                    'team_formation':team.get('formation'),
                    'shots_on_target':explicit_sot,'verified_event_shots':event_shots,'verified_event_sot':event_sot,
                    'shot_evidence_status':event_status,'target_conflict':conflict,'saves':saves,'goals_conceded':conceded,
                    'event_saves':event_saves,'team_sot_minus_goals_proxy':proxy,
                    'proxy_comparable_full_match':bool(is_keeper and started and minutes==90),
                    'lineup_source':lineup.get('source'),'stat_source':'FotMob published player totals; upstream identity not independently established',
                    'source_sha256':source_hash})
    return rows

def archive_observed_targets(payload, folder, expected_match_id):
    """Append compact observed targets from an already fetched settlement payload.

    This is not a new download or a training action. A corrected source creates
    another immutable version. Identical targets do not grow the archive merely
    because a page's unrelated presentation data changed.
    """
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    rows = extract(payload, sha256(raw).hexdigest())
    if not rows or any(str(r["match_id"]) != str(expected_match_id) for r in rows):
        raise ValueError("requested match identity mismatch or no appearances")
    if any(r["target_conflict"] for r in rows):
        raise ValueError("explicit player totals disagree with reconciled events")
    rows.sort(key=lambda r: (r["team_id"], r["player_id"]))
    stable = [{k: v for k, v in r.items() if k != "source_sha256"} for r in rows]
    target_hash = sha256(json.dumps(stable, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    folder = Path(folder) / str(int(expected_match_id))
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (target_hash + ".json")
    packet = {
        "schema_version": 1, "observed_at": datetime.now(timezone.utc).isoformat(),
        "source": "FotMob", "source_url": f"https://www.fotmob.com/match/{int(expected_match_id)}",
        "source_payload_sha256": sha256(raw).hexdigest(), "targets_sha256": target_hash,
        "use": "post-match research targets; not prematch features, not model training approval",
        "source_independence": "player totals and events are the same published source",
        "rows": rows,
    }
    try:
        with path.open("x", encoding="utf-8") as handle:
            json.dump(packet, handle, sort_keys=True, separators=(",", ":"), allow_nan=False)
            handle.write("\n")
    except FileExistsError:
        existing = json.loads(path.read_bytes())
        existing_rows = [{k: v for k, v in r.items() if k != "source_sha256"} for r in existing.get("rows", [])]
        if existing.get("targets_sha256") != target_hash or existing_rows != stable:
            raise ValueError("existing target archive failed integrity check")
        return {"status": "unchanged", "match_id": int(expected_match_id), "appearances": len(rows), "targets_sha256": target_hash}
    return {"status": "saved", "match_id": int(expected_match_id), "appearances": len(rows), "targets_sha256": target_hash}
