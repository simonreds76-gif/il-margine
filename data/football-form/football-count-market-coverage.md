# Football Count Market Coverage

Generated: 2026-08-21T15:16:26Z

This report measures what the configured odds feed actually exposes. A bookmaker offering a market on its website does not prove the aggregator returns it.

| Category | Status | Events | Paired O/U events | Pairing unknown | Competitions | Raw labels |
|---|---|---:|---:|---:|---:|---|
| team_fouls_total | NOT_OBSERVED | 0 | 0 | 0 | 0 | - |
| match_fouls_total | NOT_OBSERVED | 0 | 0 | 0 | 0 | - |
| team_cards_total | PAIRED_PRICES_OBSERVED | 31 | 30 | 28 | 9 | Bookings Totals Away, Bookings Totals Home, Team Cards Away, Team Cards Home |
| match_cards_total | PAIRED_PRICES_OBSERVED | 31 | 30 | 28 | 9 | Bookings Totals, Number of Cards In Match |
| player_fouls_committed | MARKET_NAME_ONLY | 24 | 0 | 22 | 6 | Player Fouls Committed |
| player_fouled | MARKET_NAME_ONLY | 23 | 0 | 21 | 6 | Player To Be Fouled |
| player_cards | MARKET_NAME_ONLY | 21 | 0 | 19 | 9 | Player Cards |

## Decision

- `PAIRED_PRICES_OBSERVED`: eligible for definition checks and a preregistered shadow-model experiment.
- `MARKET_NAME_ONLY`: the label was observed, but the legacy audit cannot prove usable paired prices.
- `NOT_OBSERVED`: not returned by the configured feed; do not assume it can be automated.
- Live staking remains blocked until count, settlement, real-price ROI and CLV gates pass.
