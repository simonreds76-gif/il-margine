"""GK-only source incident gate. Preserve quotes; never relabel disputed bets.

2026-11-06: the cached MoviOdds 177703 board attached the 4+ price to
3+ for two keepers. Its live-fetch ladder also disagreed with Bet365.com.
Poll freshness and agreement between fields from that same feed are not
independent contract verification. Re-enabling requires a reviewed fix.
"""
from datetime import datetime, timezone

INCIDENT_START = datetime(2026, 11, 6, 15, 58, tzinfo=timezone.utc)
MOVIODDS_GK_HOLD = True
REASON = 'moviodds_gk_contract_price_unverified_20261106'


def current_quote_issue(row):
    """Gate current quotes, including older boards that lost source metadata."""
    if not MOVIODDS_GK_HOLD:
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
