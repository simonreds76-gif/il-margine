"""Research-only Grosvenor headed-goal quotes from already fetched responses.

No network, model pricing, selections, settlement or notifications. Never feed
these contracts to Skyline's headed-shots-on-target model. Written brand rules
have not been verified: prices are observations, not executable model signals.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import timedelta
from pathlib import Path

from football_team_names import football_form_team_key
from player_name_matching import fold_name_text
from tennis_grosvenor import BASE, scaled, utc

CRITERION = 1001159730
LABEL = 'To score from a header'
BOOK = 'Grosvenor'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=False).encode()).hexdigest()


def read(path, default):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return default


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(f'.{os.getpid()}.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    temp.replace(path)


def full_name(value):
    return re.sub('[^a-z0-9]', '', fold_name_text(str(value)).casefold())


def player_mapping(target, player, participant_id, aerial, registry, captured_at=None):
    """Only exact full names unique across BOTH exact-fixture rosters.

    Provider player/team IDs are retained as evidence, never treated as our IDs.
    A missing roster does not invalidate the bookmaker's named quote.
    """
    result = dict(mapping_status='unmatched', player_id=None, team_id=None,
                  lineup_status='unknown', lineup_observed_at=None)
    when = utc(target.get('date') or target.get('startTime'))
    options = []
    for fixture in aerial.get('fixtures', []):
        teams = fixture.get('teams', [])
        if (len(teams) == 2 and utc(fixture.get('kickoff')) == when
                and [football_form_team_key(t.get('name', '')) for t in teams]
                == [football_form_team_key(target.get(s, '')) for s in ('home', 'away')]):
            options.append(fixture)
    if len(options) != 1:
        result['mapping_status'] = 'ambiguous_fixture' if options else 'no_roster'
        return result
    fixture = options[0]
    matches = [(p, t) for t in fixture['teams'] for p in t.get('players', [])
               if full_name(p.get('name', '')) == full_name(player)]
    if len(matches) != 1 or not matches[0][0].get('id') or not matches[0][1].get('id'):
        result['mapping_status'] = 'ambiguous_player' if matches else 'unmatched'
        return result
    p, team = matches[0]
    key = f'Kambi:{participant_id}'
    old = registry.get(key)
    if old and (old.get('conflict') or old['player_id'] != str(p['id'])):
        registry[key] = {**old, 'conflict': True}
        result['mapping_status'] = 'identity_conflict'
        return result
    registry[key] = dict(player_id=str(p['id']))
    result.update(mapping_status='matched', player_id=str(p['id']), team_id=str(team['id']))
    observed = fixture.get('observed_at')
    captured = utc(captured_at)
    if utc(observed) and captured and when and utc(observed) <= captured < when:
        result.update(lineup_status=fixture.get('state', 'unknown'), lineup_observed_at=observed)
    return result


def extract(raw, target, captured_at):
    """Caller has verified competition, oriented teams and exact kickoff.
    Check event identity again; reject unrelated occurrence markets and drift.
    Return state rows (including suspended/rejected) plus explicit diagnostics.
    """
    from football_grosvenor import matches
    now = utc(captured_at)
    events = [e for e in raw.get('events', []) if now and matches(e, target, now)]
    if len(events) != 1 or not isinstance(raw.get('betOffers'), list):
        return None, ['invalid_or_started_event']
    event = events[0]
    rows, issues = [], []
    for offer in raw['betOffers']:
        c = offer.get('criterion') or {}
        if c.get('id') != CRITERION and c.get('englishLabel') != LABEL:
            continue
        errors = []
        if c.get('id') != CRITERION or c.get('englishLabel') != LABEL:
            errors.append('criterion_drift')
        if (c.get('lifetime') != 'FULL_TIME' or offer.get('betOfferType', {}).get('id') != 127
                or str(offer.get('eventId')) != str(event['id'])
                or 'OFFERED_PREMATCH' not in offer.get('tags', []) or not offer.get('id')):
            errors.append('wrong_contract')
        outcomes = offer.get('outcomes') or []
        if len(outcomes) != 1:
            issues.append(dict(offer_id=offer.get('id'), reasons=['unexpected_outcome_count'], raw_offer=offer))
            continue
        o = outcomes[0]
        if (o.get('type') != 'OT_YES' or o.get('line') != 1000 or not o.get('participant')
                or not o.get('participantId') or not o.get('id')
                or str(o.get('betOfferId')) != str(offer.get('id'))):
            errors.append('wrong_outcome')
        changed = utc(o.get('changedDate'))
        if not changed or changed > now:
            errors.append('invalid_source_time')
        status = o.get('status')
        price = scaled(o.get('odds'), price=True)
        if status not in ('OPEN', 'SUSPENDED', 'CLOSED') or (status == 'OPEN' and price is None):
            errors.append('invalid_price_or_status')
        if offer.get('status', 'OPEN') not in ('OPEN', 'SUSPENDED', 'CLOSED'):
            errors.append('invalid_offer_status')
        state = 'REJECTED' if errors else offer.get('status', status)
        if state == 'OPEN' and status != 'OPEN':
            state = status
        row = dict(key=f'{BOOK}:{event["id"]}:{offer.get("id")}:{o.get("id")}',
                   bookmaker=BOOK, platform='Kambi', event_id=str(target['id']),
                   source_event_id=str(event['id']), source_offer_id=str(offer.get('id')),
                   source_outcome_id=str(o.get('id')), source_participant_id=str(o.get('participantId')),
                   source_team_reference=o.get('eventParticipantId'), home=target['home'], away=target['away'],
                   kickoff=event['start'], player=o.get('participant'), market='1+ headed goal',
                   settlement_rules='unverified', status=state, odds=price if state == 'OPEN' else None,
                   source_updated_at=o.get('changedDate'), captured_at=captured_at,
                   source_url=f'{BASE}/betoffer/event/{event["id"]}.json',
                   raw_offer=offer, rejection_reasons=errors)
        rows.append(row)
        if errors:
            issues.append(dict(offer_id=offer.get('id'), reasons=errors))
    keys = [r['key'] for r in rows]
    if len(set(keys)) != len(keys):
        return None, ['duplicate_contract_ids']
    return rows, issues


def current_quotes(state, now):
    """Fresh prematch research quotes only; no stale-price resurrection."""
    return [q for q in state.get('quotes', {}).values()
            if q['status'] == 'OPEN' and utc(q.get('last_seen_at')) and utc(q.get('kickoff'))
            and timedelta(0) <= now-utc(q['last_seen_at']) <= timedelta(hours=2)
            and now < utc(q['kickoff']) and q.get('mapping_status') != 'identity_conflict']


def retain(directory, captures, *, now, aerial=None):
    """Batch once per existing collector. Historical rows are append-only.
    Latest state retains 7 days; history shards preserve prices/raw contracts.
    Replaying a payload (even with a new capture time) appends no price rows.
    """
    path = Path(directory)/'headed-goal-quotes.json'
    state = read(path, dict(schema_version=1, quotes={}, events={}, player_registry={}))
    before = digest(state)
    added = []
    for capture in captures:
        raw, target, at = capture['raw'], capture['target'], capture['captured_at']
        rows, issues = extract(raw, target, at)
        if rows is None:
            continue
        from football_grosvenor import matches
        sid = str(next(e['id'] for e in raw['events'] if matches(e, target, utc(at))))
        event_key = f'{BOOK}:{sid}'
        prior = state['events'].get(event_key, {})
        # A reused cached response is not a new observation.
        if prior.get('observed_at') and utc(at) <= utc(prior['observed_at']):
            continue
        payload_hash = digest(raw)
        seen = {r['key'] for r in rows}
        for row in rows:
            previous = state['quotes'].get(row['key'], {})
            row.update(player_mapping(target, row['player'], row['source_participant_id'], aerial or {}, state['player_registry'], at))
            row.update(first_seen_at=previous.get('first_seen_at', at), last_seen_at=at,
                       last_checked_at=at, payload_sha256=payload_hash)
            # Identity mapping is metadata, not a price change. Retain the last
            # accepted price fingerprint across temporary non-observations.
            fingerprint = digest([row['status'], row['odds'], row['rejection_reasons']])
            if fingerprint != previous.get('last_price_fingerprint'):
                record = {**row, 'record_id': digest([row['key'], at, fingerprint])}
                added.append(record)
            row['last_price_fingerprint'] = fingerprint
            state['quotes'][row['key']] = row
        for key, old in state['quotes'].items():
            if key.startswith(event_key+':') and key not in seen:
                old.update(status='NOT_OBSERVED', last_checked_at=at)
        state['events'][event_key] = dict(event_id=str(target['id']), observed_at=at,
            payload_sha256=payload_hash, seen_contract_ids=sorted(seen), issues=issues)
    # If a provider ID conflicts, invalidate every associated mapping.
    for q in state['quotes'].values():
        if state['player_registry'].get('Kambi:'+q['source_participant_id'], {}).get('conflict'):
            q.update(mapping_status='identity_conflict', player_id=None, team_id=None)
    # Never erase append-only evidence. Bound only the current-state view.
    state['quotes'] = {k:q for k,q in state['quotes'].items()
                       if utc(q['last_seen_at']) and now-utc(q['last_seen_at']) < timedelta(days=7)}
    state['events'] = {k:e for k,e in state['events'].items()
                       if utc(e['observed_at']) and now-utc(e['observed_at']) < timedelta(days=7)}
    history = Path(directory)/'headed-goal-quote-history'
    for day in sorted({r['captured_at'][:10] for r in added}):
        shard = history/(day+'.jsonl')
        existing = shard.read_text(encoding='utf-8').splitlines() if shard.exists() else []
        ids = {json.loads(line)['record_id'] for line in existing if line.strip()}
        history.mkdir(parents=True, exist_ok=True)
        # History first, latest second; record IDs make crash retries idempotent.
        with shard.open('a', encoding='utf-8') as stream:
            for row in added:
                if row['captured_at'][:10] == day and row['record_id'] not in ids:
                    stream.write(json.dumps(row, ensure_ascii=False, separators=(',', ':'))+'\n')
                    ids.add(row['record_id'])
    if digest(state) != before:
        state.update(generated_at=now.isoformat(), purpose='Headed goal quotes only; NOT headed shot on target. Settlement rules unverified. No model, bets or alerts.')
        save(path, state)
    return dict(price_or_status_changes=len(added), current_quotes=len(current_quotes(state, now)),
                mapped_quotes=sum(q.get('mapping_status') == 'matched' for q in current_quotes(state, now)),
                rules='unverified', paper_selections=0)
