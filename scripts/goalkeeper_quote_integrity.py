"""GK-only source incident gate. Preserve quotes; never relabel disputed bets.

2026-11-06: the cached MoviOdds 177703 board attached the 4+ price to
3+ for two keepers. Its live-fetch ladder also disagreed with Bet365.com.
The repaired adapter requires exact contract and price agreement between the
cached board and a fresh full-match fetch, checked against visible Bet365
ladders. That reconciliation is not independent bookmaker attestation.
Unverified current quotes and affected historical bets remain held.
"""
from datetime import datetime, timezone, timedelta
import json
import math
import unicodedata

INCIDENT_START = datetime(2026, 11, 6, 15, 58, tzinfo=timezone.utc)
MOVIODDS_GK_HOLD = True  # Require verification; not a blanket source disable.
REASON = 'moviodds_gk_contract_price_unverified_20261106'
VERIFICATION_VERSION = 'moviodds_gk_atomic_v1'


def verified_quote(row):
    """Proof binds the exact recorded contract to two separately read responses.

    This is source reconciliation, not independent bookmaker attestation. The
    adapter is separately checked against the visible Bet365 ladder. Never
    carry a proof over when a player, line, price or capture timestamp changes.
    """
    try:
        raw = row.get('quote_verification')
        proof = json.loads(raw) if isinstance(raw, str) else raw
        if not isinstance(proof, dict) or proof.get('version') != VERIFICATION_VERSION or proof.get('site') != 'com':
            return False
        name = lambda v: ''.join(c for c in unicodedata.normalize('NFKD', str(v or '')).casefold() if c.isalnum())
        bound_names={name(proof['player'])}
        if proof.get('resolved_goalkeeper'):bound_names.add(name(proof['resolved_goalkeeper']))
        if (str(row.get('event_id')) != proof['event_id']
                or name(row.get('player') or row.get('goalkeeper')) not in bound_names
                or str(row.get('side')).casefold() != 'over'
                or float(row['line']) != proof['line']
                or not math.isclose(float(row.get('odds_decimal') or row.get('odds')), proof['odds_decimal'], abs_tol=.000051, rel_tol=0)
                or not proof['fixture_id'] or not proof['sel_id'] or proof['market_id'] not in ('177703','177769')):
            return False
        stamps = [datetime.fromisoformat(str(v).replace('Z','+00:00')) for v in
                  (proof['board_polled_at'],proof['live_polled_at'],proof['verified_at'],row['captured_at'])]
        board,live,verified,captured=stamps
        return bool(all(d.tzinfo for d in stamps) and captured == min(board,live)
                    and all(timedelta(seconds=-30)<=verified-d<=timedelta(minutes=10) for d in (board,live))
                    and math.isfinite(proof['line']) and proof['line']>=.5 and proof['line']%1==.5
                    and math.isfinite(proof['odds_decimal']) and proof['odds_decimal']>1)
    except (ValueError, TypeError, KeyError, OverflowError):
        return False


def bind_resolved_keeper(price_row, canonical_player):
    """Retain the raw name and the existing exact-fixture resolver's result.

    The source proof is checked BEFORE binding. No new fuzzy name matching is
    introduced here; the caller has already resolved a unique lineup keeper.
    """
    raw=price_row.get('quote_verification','')
    if not canonical_player or not verified_quote(price_row):return raw
    proof=json.loads(raw) if isinstance(raw,str) else dict(raw)
    proof['resolved_goalkeeper']=canonical_player
    return json.dumps(proof,separators=(',',':'))


def current_quote_issue(row):
    """Gate current quotes, including older boards that lost source metadata."""
    if not MOVIODDS_GK_HOLD:
        return None
    if verified_quote(row):
        return None
    source = str(row.get('source') or '')
    if source.startswith('moviodds_bet365'):
        return REASON
    # Bet365 is currently supplied only by this route. Legacy candidate CSVs
    # did not retain provenance; absence cannot be used to bypass the hold.
    if str(row.get('bookmaker') or 'Bet365').casefold() == 'bet365':
        return REASON
    return None


def recorded_quote_issue(row):
    """Hold affected-period selections separately, not older settled history."""
    if str(row.get('bookmaker') or 'Bet365').casefold() != 'bet365':
        return None
    if verified_quote(row):
        return None
    try:
        captured = datetime.fromisoformat(str(row.get('captured_at') or '').replace('Z', '+00:00'))
        if captured.tzinfo and captured >= INCIDENT_START:
            return REASON
    except ValueError:
        pass
    return None


def annotate_records(rows):
    return [{**row, 'integrity_status':'quote_quarantined', 'quarantine_reason':reason}
            if (reason := recorded_quote_issue(row)) else dict(row) for row in rows]
