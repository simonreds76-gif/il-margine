"""Retain allowlisted inputs already loaded by the pricing call, without rereads.

This observes the loaded tables at the end of calculation, not an atomic DB
snapshot or a per-fixture execution trace. It never changes a forecast or fills
missing historical ratings. No network, environment capture, or model fitting.
"""
from datetime import date, datetime
import hashlib
import json
from pathlib import Path

MAX_TRACE_BYTES = 4_000_000
PLAYER_MAPS = (
    'atp_rank_by_player', 'surface_points_by_player', 'birthdate_by_player',
    'recent_activity_by_player', 'recent_results_by_player',
)
TOUR_MAPS = ('tour_to_surface', 'tour_name_by_id', 'tour_rank_by_id', 'tour_date_by_id')


def primitive(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return [primitive(x) for x in value]
    if isinstance(value, dict):
        return {str(k): primitive(v) for k, v in value.items()}
    raise TypeError('unsupported input-trace value')


def build_trace(root, rows, caller, now):
    model = Path(root) / 'scripts/oncourt-compute-fair-odds.py'
    if caller is None or Path(caller.f_code.co_filename).resolve() != model.resolve() or caller.f_code.co_name != 'main':
        return None
    state = caller.f_locals
    required = ('elo_lookup', 'elo_rows', 'stats', 'input_day', *PLAYER_MAPS, *TOUR_MAPS)
    missing = [k for k in required if k not in state]
    if missing:
        raise ValueError('missing loaded input tables: ' + ','.join(missing))
    players = {int(r[k]) for r in rows for k in ('player1_id', 'player2_id')}
    tours = {int(r['tour_id']) for r in rows}
    pairs = {(int(r[k]), r['surface']) for r in rows for k in ('player1_id', 'player2_id')}
    keys = pairs | {(p, 'Overall') for p in players}
    lookup = state['elo_lookup']
    h = hashlib.sha256()
    for key in sorted(lookup):
        h.update(json.dumps([*key, lookup[key]], separators=(',', ':'), allow_nan=False).encode())
        h.update(b'\n')
    raw = [dict(player_id=r.get('player_id'), surface=r.get('surface'), elo=r.get('elo'))
           for r in state['elo_rows'] if int(r['player_id']) in players]
    inputs = {k: {str(p): primitive(state[k][p]) for p in sorted(players) if p in state[k]} for k in PLAYER_MAPS}
    inputs.update({k: {str(t): primitive(state[k][t]) for t in sorted(tours) if t in state[k]} for k in TOUR_MAPS})
    # Only the stats fields read by confidence/class/sample gates are needed here.
    inputs['stats_match_counts'] = [dict(player_id=p, surface=s, present=(p, s) in state['stats'],
        match_count=state['stats'].get((p, s), {}).get('match_count')) for p, s in sorted(pairs)]
    value = dict(schema_version=1, kind='loaded_elo_rank_inputs_after_calculation',
        timing_status='not_an_atomic_database_snapshot_or_verified_prematch_capture',
        input_day=primitive(state['input_day']), observed_calendar_day=now.date().isoformat(),
        crossed_calendar_day=primitive(state['input_day']) != now.date().isoformat(),
        source_table='player_elo', rating_method_status='UNVERIFIED_NOT_INFERRED_FROM_VALUES',
        source_updated_at=None, elo_lookup_rows=len(lookup), elo_lookup_sha256=h.hexdigest(),
        raw_elo_rows=raw,
        elo_lookup=[dict(player_id=p, surface=s, present=(p, s) in lookup, value=lookup.get((p, s))) for p, s in sorted(keys)],
        lookup_coercion='_float(source elo, DEFAULT_ELO); absent lookup is distinct from null raw row',
        constants={k: primitive(caller.f_globals.get(k)) for k in ('DEFAULT_ELO', 'ELO_RELIABILITY_MIN')},
        loaded_inputs=inputs,
        not_captured=['per-fixture unrounded p_elo', 'per-fixture effective ratings/reliability/class intermediates'],
        model_sha256=hashlib.sha256(model.read_bytes()).hexdigest(),
        observer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    body = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    if len(body) > MAX_TRACE_BYTES:
        raise ValueError('loaded input trace exceeds bounded size')
    return body
