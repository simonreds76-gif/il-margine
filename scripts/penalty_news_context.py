"""Evidence-bound enrichment; no hierarchy decisions or guessed foul winners."""
import re


def clock(minute, added=0):
    # Keep 45+9 before minute 46, rather than treating it as minute 54.
    return int(minute or 0) + max(0, int(added or 0)) / 100


def incident_context(shot, commentary, notes):
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
    # Human commentary needs reviewed facts, pinned to the exact source text.
    note = notes.get(str(shot['id']))
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
