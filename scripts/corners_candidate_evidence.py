"""Append-only Corners v3 opportunity evidence; no odds calls or model changes.

Replays the unchanged scorer at the publisher's cutoff, verifies its entire
corners board, and retains rejected opportunities as well as selected ones.
This is an evidence archive, not a new betting strategy.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
import sys
import platform
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from football_fixture_identity import FixtureIndex
from football_count_results import count_result_index, exact_result, count

ROOT = Path(__file__).resolve().parents[1]
RELATIVE = Path('data/football-form/corners-candidate-evidence-v1')
INPUTS = ('data/football-form/team-match-base.csv',
          'data/team-shots/understat/corner-event-features.csv',
          'data/corners-ou/pinnacle-corners-odds.csv',
          'data/corners-ou/bet365-corners-odds-history.csv')
CODE = ('scripts/publish-football-vnext-shadow.py',
        'scripts/publish-football-research-picks.py', 'scripts/football_counts.py',
        'scripts/football_best_prices.py', 'scripts/football_market.py',
        'scripts/football_fixture_identity.py', 'scripts/football_team_names.py',
        'scripts/team_shots_ema20_features.py', 'scripts/corners_candidate_evidence.py',
        'scripts/backtest-football-form-layer.py', 'scripts/football_form_integrity.py',
        'scripts/settlement_utils.py',
        'config/corners-evidence-rules.json',
        'data/corners-ou/corners-v3-params.json', 'data/corners-ou/corners-v3-lock.json')


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False,
                      default=lambda x: x.isoformat() if isinstance(x, datetime) else str(x)).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def read_json(path, default=None):
    return json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else default


def rows(path):
    if not path.exists():
        return []
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_bytes(encoded(value) + b'\n')
    temporary.replace(path)


def retain(path, value):
    """Never rewrite an existing evidence object, including its first-seen time."""
    if path.exists():
        return False
    atomic(path, value)
    return True


def publisher(root):
    spec = importlib.util.spec_from_file_location('_corners_evidence_publisher',
                                                root / CODE[0])
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def stable_fixture(row):
    keys = FixtureIndex().keys(row)
    legs = [key for key in keys if key[0] == 'league-home-leg']
    if len(legs) != 1:
        return None
    return '|'.join(map(str, legs[0]))


def candidate_key(row):
    return (row['kickoff_utc'], row['league'], row['home_team'], row['away_team'],
            str(float(row['line'])), row['bookmaker'], row['side'])


def board_parity(actual, replay):
    """CSV formatting is ignored; every published field and row must agree."""
    a = {candidate_key(r): r for r in actual}
    b = {candidate_key(r): r for r in replay}
    if len(a) != len(actual) or len(b) != len(replay) or set(a) != set(b):
        raise ValueError('candidate_board_identity_or_count_mismatch')
    for key in a:
        for field, expected in b[key].items():
            # Publication time is stamped after selection, unlike pure scorer.
            if field == 'published_at_utc':
                continue
            if str(a[key].get(field, '')) != str(expected):
                raise ValueError('candidate_board_parity_mismatch:' + field)
    return len(a)


def quote_groups(raw, V, cutoff):
    """Keep unsupported lines and incomplete pairs as explicit exclusions."""
    grouped = defaultdict(dict)
    dropped = Counter()
    for original in raw:
        row = dict(original)
        kickoff = V.PUB.parse_dt(row.get('kickoff_iso') or row.get('kickoff_at'))
        captured = V.PUB.parse_dt(row.get('captured_at'))
        if not kickoff or not captured:
            dropped['missing_quote_time'] += 1
            continue
        if kickoff <= cutoff:
            continue
        league = V.PUB.league_slug(row.get('league') or row.get('competition') or '')
        home = V.PUB.clean_display_team(row.get('home_team', '').strip())
        away = V.PUB.clean_display_team(row.get('away_team', '').strip())
        side = str(row.get('side') or '').lower()
        line = V.PUB.pf(row.get('line'))
        book = row.get('bookmaker') or 'Pinnacle'
        market = row.get('market') or 'MATCH_CORNERS'
        if not home or not away or side not in {'over', 'under'} or line is None or not math.isfinite(line):
            dropped['malformed_quote'] += 1
            continue
        if market not in {'MATCH_CORNERS', 'MATCH_CORNERS_ALT'}:
            dropped['other_market'] += 1
            continue
        key = (V.PUB.fmt_dt(kickoff), league, home, away, str(float(line)), book)
        odds = V.PUB.pf(row.get('odds_decimal'))
        item = dict(raw=row, captured_at=captured.isoformat(), kickoff=kickoff.isoformat(),
                    odds=odds if odds is not None and math.isfinite(odds) else None, line=line, side=side)
        previous = grouped[key].get(side)
        if previous is None or captured > V.PUB.parse_dt(previous['captured_at']):
            grouped[key][side] = item
        elif captured == V.PUB.parse_dt(previous['captured_at']):
            # Same contract/time with conflicting prices or market identities
            # cannot be resolved by whichever CSV row happened to come first.
            fields = ('odds_decimal','market','market_id','selection_id','event_id','source_event_id')
            if any(str(previous['raw'].get(f,'')) != str(row.get(f,'')) for f in fields):
                previous.setdefault('ambiguous_same_capture', []).append(row)
    return grouped, dict(dropped)


def price_reasons(pair, cutoff):
    reasons = []
    if set(pair) != {'over', 'under'}:
        reasons.append('incomplete_same_book_pair')
    for quote in pair.values():
        if quote.get('ambiguous_same_capture'):
            reasons.append('ambiguous_same_book_market_snapshot')
        age = (cutoff - datetime.fromisoformat(quote['captured_at'])).total_seconds()
        if not 0 <= age <= 600:
            reasons.append('quote_not_fresh_10m')
        if not quote['odds'] or not math.isfinite(quote['odds']) or quote['odds'] <= 1:
            reasons.append('invalid_decimal_price')
        if not math.isclose(quote['line'] % 1, .5, abs_tol=1e-9):
            reasons.append('unsupported_line_requires_push_distribution')
    if len(pair) == 2 and pair['over']['captured_at'] != pair['under']['captured_at']:
        reasons.append('different_pair_observation_times')
    if set(pair) == {'over', 'under'} and all(q['odds'] and q['odds'] > 1 for q in pair.values()):
        overround = sum(1/q['odds'] for q in pair.values())
        if not .99 <= overround <= 1.30:
            reasons.append('implausible_pair_overround')
    for quote in pair.values():
        raw = quote['raw']
        if str(raw.get('in_play', '')).lower() in {'true', '1'} or str(raw.get('suspended', '')).lower() in {'true', '1'}:
            reasons.append('in_play_or_suspended')
    return sorted(set(reasons))


def forecast_context(key, V, by_team, by_league, events, params, cache):
    kickoff, league, home, away = key[:4]
    day = V.PUB.parse_dt(kickoff).date()
    fixture = (day, league, V.PUB.team_key(home), V.PUB.team_key(away))
    if fixture in cache:
        return cache[fixture]
    if league not in V.TOP_FIVE:
        return {'unavailable': 'unsupported_competition'}
    form = {}
    for venue, team, opponent in [('home', home, away), ('away', away, home)]:
        form[venue] = V.PUB.live_form_row(by_team=by_team, by_league=by_league,
            league=league, fixture_date=day, team=team, opponent=opponent,
            venue=venue, home=home, away=away, baseline_cache={})
    if any(v is None for v in form.values()):
        result = {'unavailable': 'missing_team_history', 'form': form}
    else:
        states = V.latest_event_states(events, params, before=day)
        hs, aws = states[(league, V.PUB.team_key(home))], states[(league, V.PUB.team_key(away))]
        result = {'form': form, 'home_event_state': asdict(hs), 'away_event_state': asdict(aws),
                  'home_event_matches': hs.matches, 'away_event_matches': aws.matches}
        if min(hs.matches, aws.matches) < int(params['event_min_history']):
            result['unavailable'] = 'insufficient_event_history'
        else:
            feature = V.corners_features(form['home'], form['away'], hs, aws, params)
            if feature is None:
                result['unavailable'] = 'missing_corner_features'
            else:
                league_mean, values = feature
                result.update(league_mean=league_mean, feature_names=params['feature_names'],
                    features=values, mean=V.predict_corners_mean(league_mean, values, params),
                    alpha=params['alpha'], distribution='negative_binomial_nb2')
        # Dates are retained as coverage, not falsely called first-seen times.
        result['history_dates'] = {side: [r.get('date') for r in by_team.get((league, V.PUB.team_key(team)), [])
            if (played := V.PUB.parse_date(r.get('date'))) is not None and played < day]
            for side, team in [('home', home), ('away', away)]}
        result['event_dates'] = [r.get('date') for r in events
            if V.PUB.league_slug(r.get('league', '')) == league
            and {V.PUB.team_key(r.get('home_team')), V.PUB.team_key(r.get('away_team'))}
                & {V.PUB.team_key(home), V.PUB.team_key(away)}
            and (played := V.PUB.parse_date(r.get('date'))) is not None and played < day]
    cache[fixture] = result
    return result


def collect(root=ROOT, now=None, output=None, publisher_output_dir=None):
    now = now or datetime.now(timezone.utc)
    output = output or root / RELATIVE
    output.mkdir(parents=True, exist_ok=True)
    registration = read_json(output / 'registration.json')
    if registration is None:
        registration = dict(schema_version=1, registered_at=now.isoformat(),
            purpose='all Corners v3 opportunities, including no-bets; evidence only',
            cohort='first verified fresh pre-match observation per fixture/line/book',
            fixture_identity='ordered home/away top-five domestic league leg per season; provider IDs retained when present',
            quote_max_age_seconds=600, pair_policy='identical same-book observation timestamps',
            settlement='regulation-time match corners; half-lines only; no assumed abandonment result',
            actual_stake=0, new_alerts=False, historical_backfill=False,
            limitation='No price coverage means no ROI; all raw available quotes and exclusions retained.')
        retain(output / 'registration.json', registration)
    board_dir = publisher_output_dir or root / 'data/football-form'
    health = read_json(board_dir / 'count-input-identity-health.json', {})
    V = publisher(root)
    cutoff = V.PUB.parse_dt(health.get('generated_at'))
    if cutoff is None or not 0 <= (now - cutoff).total_seconds() <= 600:
        raise ValueError('publisher_cutoff_missing_or_stale')
    board_path = board_dir / 'football-counts-vnext-candidates.csv'
    board_hash = file_hash(board_path)
    ledger_path = root / 'data/football-form/corners-v3-shadow-signals.csv'
    ledger_hash = file_hash(ledger_path)
    source_hashes = {p: file_hash(root / p) for p in INPUTS}
    model_hashes = {p: file_hash(root / p) for p in CODE}
    if any(v is None for p, v in source_hashes.items() if p != INPUTS[3]):
        raise ValueError('required_source_missing')
    manifest_id = digest(model_hashes)
    retain(output / 'models' / (manifest_id + '.json'), dict(hashes=model_hashes,
        files={p: (root / p).read_text(encoding='utf-8-sig') for p in CODE if (root / p).exists()}))
    base, events = rows(root / INPUTS[0]), rows(root / INPUTS[1])
    raw = rows(root / INPUTS[2]) + rows(root / INPUTS[3])
    params, lock = V.load_json(V.CORNERS_PARAMS), V.load_json(V.CORNERS_LOCK)
    by_team, by_league = V.PUB.build_base_indexes(base)
    selected, candidates = V.score_corners(by_team=by_team, by_league=by_league,
        odds_rows=raw, event_rows=events, params=params, lock=lock, now=cutoff)
    actual = [r for r in rows(board_path)
              if r.get('model') == 'corners_v3']
    parity = board_parity(actual, candidates)
    if (source_hashes != {p: file_hash(root / p) for p in INPUTS}
            or file_hash(board_path) != board_hash or file_hash(ledger_path) != ledger_hash):
        raise ValueError('inputs_changed_during_capture')
    lookup = {candidate_key(r): r for r in candidates}
    selected_keys = {candidate_key(r) for r in selected}
    ledger = rows(ledger_path)
    groups, malformed = quote_groups(raw, V, cutoff)
    rules = read_json(root / 'config/corners-evidence-rules.json', {})
    primary = {}
    for key, pair in groups.items():
        if not price_reasons(pair, cutoff):
            fixture_book = (*key[:4], key[-1])
            score = (abs(1/pair['over']['odds'] - 1/pair['under']['odds']), float(key[4]))
            if fixture_book not in primary or score < primary[fixture_book][0]:
                primary[fixture_book] = (score, key[4])
    cache = {}
    added = 0
    reasons_count = Counter()
    fresh = 0
    for key, pair in groups.items():
        kickoff, league, home, away, line, book = key
        identity = dict(kickoff_utc=kickoff, match_date=kickoff[:10], league=league,
                        home_team=home, away_team=away)
        fixture_id = stable_fixture(identity)
        context = forecast_context(key, V, by_team, by_league, events, params, cache)
        blocked = price_reasons(pair, cutoff)
        if not fixture_id:
            blocked.append('unresolved_fixture_scope')
        if book not in rules.get('bookmakers', {}):
            blocked.append('bookmaker_rules_unverified')
        if context.get('unavailable'):
            blocked.append(context['unavailable'])
        if cutoff < datetime.fromisoformat(registration['registered_at']):
            blocked.append('before_archive_registration')
        if now >= V.PUB.parse_dt(kickoff):
            blocked.append('observed_after_start')
        if any(str(d or '')[:10] >= now.date().isoformat()
               for d in context.get('history_dates', {}).get('home', []) + context.get('history_dates', {}).get('away', [])):
            blocked.append('same_day_input_availability_unverified')
        forecasts = {}
        for side in pair:
            candidate = lookup.get((*key, side))
            if candidate is None:
                continue
            full = V.prob_over(float(line), context['mean'], distribution='negative_binomial', alpha=context['alpha'])
            probability = full if side == 'over' else 1-full
            if abs(probability-float(candidate['model_implied_prob'])) > 0.00000051:
                raise ValueError('full_precision_feature_replay_failed')
            decision = 'selected_this_scan' if (*key, side) in selected_keys else 'no_bet'
            no_bet = [s for s in candidate.get('blocked_reason', '').split(';') if s]
            if not no_bet and decision == 'no_bet':
                no_bet.append('fixture_selection_cap')
            old = [r for r in ledger if stable_fixture(r) == fixture_id]
            if any(r.get('published_at_utc', '') < V.PUB.fmt_dt(cutoff) for r in old):
                decision = 'no_bet'
                no_bet.append('already_recorded_fixture')
            forecasts[side] = dict(p=probability, p_push=0.0, candidate=candidate, decision=decision,
                selected_by_scan_rule=(*key, side) in selected_keys,
                no_bet_reasons=no_bet, retained_first_selection=old,
                new_selection_this_scan=any(r.get('published_at_utc') == V.PUB.fmt_dt(cutoff)
                                          and r.get('pick_id') == candidate['pick_id'] for r in old))
        if set(forecasts) != {'over', 'under'}:
            blocked.append('no_complete_model_forecast_pair')
        market = None
        if set(pair) == {'over', 'under'} and all(q['odds'] and q['odds'] > 1 for q in pair.values()):
            o, u = 1/pair['over']['odds'], 1/pair['under']['odds']
            market = dict(over=o/(o+u), under=u/(o+u), overround=o+u-1,
                          method='proportional_same_book', coherent=not price_reasons(pair, cutoff))
        blocked = sorted(set(blocked))
        reasons_count.update(blocked)
        contract = '|'.join([fixture_id or '|'.join(key[:4]), 'match_corners_90m', line, book])
        context_id = digest(context)
        retain(output / 'inputs' / (context_id + '.json'), context)
        # Exclude observation wall clock from identity, preserving retry idempotence.
        body = dict(schema_version=1, contract_id=contract, fixture_id=fixture_id,
            fixture=identity, bookmaker=book, line=float(line), market='match_corners_90m',
            line_type='half' if math.isclose(float(line)%1,.5) else 'integer' if float(line).is_integer() else 'quarter_or_other',
            primary_line=(primary.get((*key[:4], book), (None, None))[1] == line),
            primary_line_policy='closest paired implied probabilities, then lower line; fixed without outcomes',
            pair=pair, forecasts=forecasts, market_probabilities=market,
            context_id=context_id, model_manifest_id=manifest_id,
            research_eligible=not blocked, exclusion_reasons=blocked,
            provenance='same_scan_scorer_replay_with_full_candidate_board_parity',
            quote_label='recorded quote; not certified executable',
            quote_metadata_gaps={s: [f for f in ('event_id', 'market_id', 'selection_id', 'in_play', 'suspended')
                                    if f not in q['raw']] for s,q in pair.items()},
            kickoff_provenance='bookmaker archive kickoff, not independently confirmed actual start',
            bookmaker_rules=rules.get('bookmakers', {}).get(book))
        record_id = digest(body)
        record = dict(body, record_id=record_id, observed_at=now.isoformat(),
            publisher_cutoff=cutoff.isoformat(), source_hashes=source_hashes,
            candidate_board_sha256=board_hash, selection_ledger_sha256=ledger_hash,
            parity_tolerance='exact published fields; unrounded probability within 5.1e-7 of six-decimal board',
            python_version=platform.python_version(),
            source_observed_at=now.isoformat(), source_availability_before_observation='not inferred')
        added += retain(output / 'observations' / (record_id + '.json'), record)
        fresh += not blocked
    status = dict(schema_version=1, state='ACTIVE' if fresh else 'NO_ELIGIBLE_NEW_OPPORTUNITIES',
        checked_at=now.isoformat(), publisher_cutoff=cutoff.isoformat(),
        parity_candidates=parity, available_book_line_pairs=len(groups),
        new_observations=added, eligible_pairs_this_scan=fresh,
        exclusions=dict(reasons_count), malformed_quote_counts=malformed,
        latest_quote_at=max((r.get('captured_at', '') for r in raw), default=None),
        real_stake=0, formula_changes=False, requests=0)
    universe = {}
    for key in groups:
        universe.setdefault('|'.join(key[:4]), []).append({'bookmaker':key[-1], 'line':key[4]})
    # Existing discovery can show fixtures with no corners prices at all.
    for raw_fixture in rows(root / 'data/team-shots/team-shots-upcoming.v2-nb-raw.csv'):
        kickoff = V.PUB.parse_dt(raw_fixture.get('kickoff_utc') or raw_fixture.get('kickoff_at') or raw_fixture.get('kickoff_iso'))
        if kickoff and kickoff > cutoff:
            ident = '|'.join([V.PUB.fmt_dt(kickoff), raw_fixture.get('league',''),
                              raw_fixture.get('home_team',''), raw_fixture.get('away_team','')])
            universe.setdefault(ident, [])
    receipt = dict(status, candidate_board_sha256=board_hash, source_hashes=source_hashes,
                   fixture_universe=universe, universe_scope='existing saved bookmaker/football discovery, not guaranteed complete league schedule')
    retain(output / 'runs' / (digest({'cutoff':cutoff,'board':board_hash,'inputs':source_hashes}) + '.json'), receipt)
    return status


def first_and_latest(output):
    observations = [read_json(p) for p in (output / 'observations').glob('*.json')]
    first, latest = {}, {}
    for row in sorted(observations, key=lambda r: (r['observed_at'], r['record_id'])):
        if row['research_eligible']:
            first.setdefault(row['contract_id'], row)
            latest[row['contract_id']] = row
    return first, latest


def pending_result_fixtures(root, now):
    """No-bets share the existing bounded result queue, not a new downloader."""
    output = root / RELATIVE
    first, latest = first_and_latest(output)
    results = count_result_index(root, now) if first else {}
    pending = {}
    for contract in first:
        record = latest[contract]
        fixture = record['fixture']
        kickoff = datetime.fromisoformat(fixture['kickoff_utc'].replace('Z','+00:00'))
        if (now-kickoff).total_seconds() < 10800:
            continue
        result = exact_result(fixture, results, now)
        if result and count(result.get('total_corners')) is not None:
            continue
        pending.setdefault(record['fixture_id'], dict(fixture, result='pending',
            pick_id='corners-evidence|' + record['fixture_id']))
    return list(pending.values())


def settle(root, output, now):
    """Separate immutable result observations; never edit issued ledgers."""
    results = count_result_index(root, now)
    first, latest = first_and_latest(output)
    added = 0
    pending = 0
    for contract, row in first.items():
        schedule = latest[contract]
        result = exact_result(schedule['fixture'], results, now)
        if result is None or result.get('total_corners') is None:
            pending += 1
            continue
        if result.get('source') not in {'football-data', 'fotmob_verified_fulltime', 'fotmob', 'api-football'}:
            pending += 1
            continue
        # Explicit incomplete/abandoned status is never interpreted as a loss.
        match_status = result.get('status') or result.get('match_status')
        if match_status and str(match_status).lower() not in {'ft', 'finished', 'fulltime', 'full_time'}:
            pending += 1
            continue
        total = count(result['total_corners'])
        home_count, away_count = count(result.get('home_corners')), count(result.get('away_corners'))
        if total is None or home_count is None or away_count is None or home_count+away_count != total:
            pending += 1
            continue
        evidence = root / result['evidence_path']
        body = dict(contract_id=contract, forecast_record_id=row['record_id'],
            schedule_evidence_record_id=schedule['record_id'], resolved_fixture=schedule['fixture'],
            total_corners=total, over_won=total > row['line'],
            home_corners=result.get('home_corners'), away_corners=result.get('away_corners'),
            match_status=match_status or 'completed_result_source_contract',
            result_source=result['source'], evidence_path=result['evidence_path'],
            evidence_sha256=file_hash(evidence))
        # A changed source file or later fetch of the same count is not a new result.
        result_id = digest({k:v for k,v in body.items() if k not in {'evidence_sha256','schedule_evidence_record_id'}})
        added += retain(output / 'results' / (result_id + '.json'),
                        dict(body, observed_at=now.isoformat(), provider_observed_at=result['observed_at']))
    return dict(first_eligible_contracts=len(first), pending=pending, new_result_observations=added,
                independent_fixtures=len({r['fixture_id'] for r in first.values()}),
                result_conflicts_policy='multiple differing observations require review; no silent rewrite')


def refresh(root=ROOT, now=None, output=None, settle_only=False, publisher_output_dir=None):
    now = now or datetime.now(timezone.utc)
    output = output or root / RELATIVE
    failure = None
    try:
        status = dict(state='SETTLEMENT_ONLY', checked_at=now.isoformat()) if settle_only else collect(root, now, output, publisher_output_dir)
    except Exception as exc:
        failure = exc
        status = dict(state='CAPTURE_ERROR', checked_at=now.isoformat(), reason=str(exc))
    try:
        status['settlement'] = settle(root, output, now)
    except Exception as exc:
        failure = failure or exc
        status['settlement'] = dict(state='ERROR', reason=str(exc))
    atomic(output / 'capture-status.json', status)
    if failure:
        raise failure
    return status


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--settlement-only', action='store_true')
    parser.add_argument('--publisher-output-dir', type=Path, help='Isolated validation board; never promotes replay to the production archive')
    arguments = parser.parse_args()
    if arguments.publisher_output_dir and not arguments.output:
        parser.error('isolated publisher output requires a separate --output evidence directory')
    print(json.dumps(refresh(output=arguments.output, settle_only=arguments.settlement_only,
                             publisher_output_dir=arguments.publisher_output_dir), indent=2))
