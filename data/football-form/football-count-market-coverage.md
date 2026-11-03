# Football Count Market Coverage

Generated: 2026-11-03T16:32:02Z

This report measures what the configured odds feed actually exposes. A bookmaker offering a market on its website does not prove the aggregator returns it.

| Category | Status | Events | Paired O/U events | Pairing unknown | Competitions | Raw labels |
|---|---|---:|---:|---:|---:|---|
| team_fouls_total | NOT_OBSERVED | 0 | 0 | 0 | 0 | - |
| match_fouls_total | NOT_OBSERVED | 0 | 0 | 0 | 0 | - |
| team_cards_total | NOT_OBSERVED | 0 | 0 | 0 | 0 | - |
| match_cards_total | MARKET_NAME_ONLY | 9 | 0 | 9 | 3 | Bookings Totals |
| player_fouls_committed | MARKET_NAME_ONLY | 11 | 0 | 11 | 4 | Player Fouls |
| player_fouled | MARKET_NAME_ONLY | 10 | 0 | 10 | 3 | Player To Be Fouled |
| player_cards | NOT_OBSERVED | 0 | 0 | 0 | 0 | - |

## Decision

- `PAIRED_PRICES_OBSERVED`: eligible for definition checks and a preregistered shadow-model experiment.
- `MARKET_NAME_ONLY`: the label was observed, but the legacy audit cannot prove usable paired prices.
- `NOT_OBSERVED`: not returned by the configured feed; do not assume it can be automated.
- Live staking remains blocked until count, settlement, real-price ROI and CLV gates pass.
