"""Evidence-bound enrichment; no hierarchy decisions or guessed foul winners."""
import re
import unicodedata


def folded(value):
    value = (value or '').lower().translate(str.maketrans({'ø': 'o', 'ł': 'l', 'đ': 'd', 'ß': 'ss'}))
    return ''.join(c for c in unicodedata.normalize('NFKD', value) if not unicodedata.combining(c))


def mentioned(name, text):
    # Use a complete surname/name token, never a substring such as Son in Johnson.
    parts = folded(name).split()
    aliases = [folded(name)] + ([parts[-1]] if parts and len(parts[-1]) >= 4 else [])
    return any(re.search(r'(?<!\w)' + re.escape(alias) + r'(?!\w)', folded(text)) for alias in aliases)


def narrative_context(shot, window, content, penalties):
    """Cross-check prose with the same fixture's player totals and participants.

    A sole penalty won by a sole credited player is unambiguous only when their
    team took exactly one penalty. Multi-penalty totals cannot assign an incident.
    No free-form AI claims, reviewed notes, hierarchy or external API are required.
    """
    candidates = [e for e in window if e.get('IncidentCode') in ('highlight', 'var', 'penalty won', 'penalty lost')]
    awards = [e for e in candidates if re.search(r'penalty (?:to|given|awarded)|\bPENALTY!|penalised for handball', e.get('Description', ''), re.I)]
    if awards:
        award_clock = clock(awards[0].get('Elapsed'), awards[0].get('ElapsedPlus'))
        candidates = [e for e in candidates if clock(e.get('Elapsed'), e.get('ElapsedPlus')) >= award_clock - 2]
    text = ' '.join(e.get('Description', '') for e in candidates)
    if not re.search(r'\bpenalty\b|penalised for handball', text, re.I):
        return None
    roster = list(content.get('playerStats', {}).values())
    winners = []
    for p in roster:
        stats = [s for g in p.get('stats', []) for s in g.get('stats', {}).values()]
        count = next((s.get('stat', {}).get('value') for s in stats if s.get('key') == 'penalties_won'), 0)
        if p.get('teamId') == shot['teamId'] and count:
            winners.append((p, count))
    team_penalties = [s for s in penalties if s.get('teamId') == shot['teamId']]
    if len(team_penalties) == 1 and len(winners) == 1 and winners[0][1] == 1:
        winner = winners[0][0]['name']
        if mentioned(winner, text) and re.search(r'foul|bundl|drag|brought down|tripp', text, re.I):
            sentence = f'{winner} won the penalty after being fouled in the area.'
            # Names appearing in a passage alone do not prove who committed it.
            return {'type': 'foul', 'wonBy': winner, 'concededBy': None, 'sentence': sentence,
                    'evidenceIds': [e['MessageId'] for e in candidates], 'method': 'narrative_crosschecked',
                    'crosscheck': {'playerId': winners[0][0]['id'], 'penaltiesWon': 1, 'teamPenalties': 1}}
    # Explicit handball discussion tied to the awarded attempt, not an arbitrary foul.
    hand = [e for e in candidates if re.search(r'handball|raised\s+\w*\s*hand|off (?:his|her|the) hand', e.get('Description', ''), re.I)]
    if hand and not winners:
        hand_text = ' '.join(e.get('Description', '') for e in hand)
        if re.search(r'no handball|not (?:a )?handball|handball (?:appeal|claim).*?(?:dismiss|reject)|no penalty|penalty.*?overturned', text, re.I):
            return None
        defenders = [p['name'] for p in roster if p.get('teamId') != shot['teamId'] and p.get('teamId') and mentioned(p['name'], hand_text)]
        defender = defenders[0] if len(defenders) == 1 else None
        # Require exactly one opposing participant, or leave the detail unavailable.
        if defender:
            return {'type': 'handball', 'wonBy': None, 'concededBy': defender,
                    'sentence': f'The referee awarded the penalty following a VAR review of a handball by {defender}.' if any(e.get('IncidentCode') == 'var' or 'VAR' in e.get('Description', '') for e in candidates) else f'The penalty followed a handball by {defender}.',
                    'evidenceIds': [e['MessageId'] for e in candidates], 'method': 'narrative_crosschecked'}
    return None


def clock(minute, added=0):
    # Keep 45+9 before minute 46, rather than treating it as minute 54.
    return int(minute or 0) + max(0, int(added or 0)) / 100


def incident_context(shot, commentary, notes=None, content=None, penalties=None):
    events = commentary.get('Events', [])
    target = clock(shot.get('min'), shot.get('minAdded'))
    attempts = [e for e in events if e.get('IncidentCode') in ('PSG', 'PS', 'PM', 'post')
                and clock(e.get('Elapsed'), e.get('ElapsedPlus')) == target
                and any(p.get('Id') == shot['playerId'] for p in e.get('Players', []))]
    if len(attempts) != 1:
        return None
    window = []
    for e in events[events.index(attempts[0]) + 1:]:
        if e.get('IncidentCode') == 'penalty save' and clock(e.get('Elapsed'), e.get('ElapsedPlus')) == target:
            continue
        if e.get('IncidentCode') in ('PSG', 'PS', 'PM', 'post', 'penalty save'):
            break
        if target - clock(e.get('Elapsed'), e.get('ElapsedPlus')) > 6:
            break
        window.append(e)
    won = [e for e in window if e.get('IncidentCode') == 'penalty won']
    lost = [e for e in window if e.get('IncidentCode') == 'penalty lost']
    if len(lost) == 1 and any(p.get('TeamId') != shot['teamId'] for p in lost[0].get('Players', []) if p.get('TeamId')):
        loss = re.fullmatch(r'Penalty conceded by (.+?) \((.+?)\) (after a foul|with a handball) in the penalty area\.', lost[0].get('Description', ''))
        if loss:
            defender, _, kind = loss.groups()
            if kind == 'with a handball' and not won:
                return {'type': 'handball', 'wonBy': None, 'concededBy': defender,
                        'sentence': f'The penalty was awarded for a handball by {defender}.',
                        'evidenceIds': [lost[0]['MessageId']], 'method': 'structured_commentary'}
            if kind == 'after a foul' and len(won) == 1:
                win = re.fullmatch(r'Penalty (.+?)\. (.+?) draws a foul in the penalty area\.', won[0].get('Description', ''))
                if win and any(p.get('TeamId') == shot['teamId'] for p in won[0].get('Players', [])):
                    return {'type': 'foul', 'wonBy': win[2], 'concededBy': defender,
                            'sentence': f'{win[2]} won the penalty after a foul by {defender} inside the area.',
                            'evidenceIds': [won[0]['MessageId'], lost[0]['MessageId']], 'method': 'structured_commentary'}
    automatic = narrative_context(shot, window, content or {}, penalties or [])
    if automatic:
        return automatic
    # Backwards-compatible evidence reader, unused by the automated collector.
    note = (notes or {}).get(str(shot['id']))
    if note:
        evidence = {e['MessageId']: e.get('Description', '') for e in events}
        window_ids = {e['MessageId'] for e in window}
        if window_ids.intersection(note['evidence']) and all(evidence.get(k) == v for k, v in note['evidence'].items()):
            return {k: v for k, v in note.items() if k != 'evidence'} | {'evidenceIds': list(note['evidence']), 'method': 'reviewed_commentary'}
    return None


def match_context(content, shot, teams, penalties):
    player = content.get('playerStats', {}).get(str(shot['playerId']), {})
    stats = {s.get('key'): s.get('stat', {}).get('value') for group in player.get('stats', []) for s in group.get('stats', {}).values()}
    values = {'minutes': stats.get('minutes_played'), 'goals': stats.get('goals'), 'shots': stats.get('total_shots'), 'onTarget': stats.get('ShotsOnTarget'), 'chances': stats.get('chances_created')}
    keeper = content.get('playerStats', {}).get(str(shot.get('keeperId')), {}).get('name')
    events = content.get('matchFacts', {}).get('events', {}).get('events', [])
    exact = [e for e in events if str((e.get('shotmapEvent') or {}).get('id')) == str(shot['id'])]
    moment = None
    if len(exact) == 1:
        e = exact[0]
        if isinstance(e.get('newScore'), list) and len(e['newScore']) == 2:
            before, after = [e.get('homeScore'), e.get('awayScore')], e['newScore']
            if all(type(v) is int for v in before + after):
                moment = {'before': before, 'after': after}
    sentences = []
    if all(type(values[k]) in (int, float) for k in ('minutes', 'shots', 'onTarget', 'goals')):
        v = values
        sentences.append(f"{shot.get('fullName') or shot['playerName']} finished with {v['goals']} {'goal' if v['goals'] == 1 else 'goals'} and {v['shots']} {'shot' if v['shots'] == 1 else 'shots'}, including {v['onTarget']} on target, in {v['minutes']} minutes.")
    team_pens = [p for p in penalties if p.get('teamId') == shot['teamId']]
    if len(team_pens) > 1:
        converted = sum(p.get('eventType') == 'Goal' for p in team_pens)
        names = list(dict.fromkeys(p.get('fullName') or p.get('playerName') for p in sorted(team_pens, key=lambda p: clock(p.get('min'), p.get('minAdded')))))
        quantity = 'both' if len(team_pens) == 2 else f'all {len(team_pens)}'
        sentences.append(f"{next(t['name'] for t in teams if t['id'] == shot['teamId'])} took {len(team_pens)} penalties in the match and converted {converted}. " + (f"{names[0]} took {quantity}." if len(names) == 1 else f"The attempts were shared by {' and '.join(names)}."))
    return values, keeper, moment, sentences
