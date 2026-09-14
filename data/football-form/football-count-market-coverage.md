# Football Count Market Coverage

Generated: 2026-09-14T15:03:48Z

This report measures what the configured odds feed actually exposes. A bookmaker offering a market on its website does not prove the aggregator returns it.

| Category | Status | Events | Paired O/U events | Pairing unknown | Competitions | Raw labels |
|---|---|---:|---:|---:|---:|---|
| team_fouls_total | NOT_OBSERVED | 0 | 0 | 0 | 0 | - |
| match_fouls_total | NOT_OBSERVED | 0 | 0 | 0 | 0 | - |
| team_cards_total | PAIRED_PRICES_OBSERVED | 18 | 5 | 17 | 8 | Bookings Totals Away, Bookings Totals Home |
| match_cards_total | PAIRED_PRICES_OBSERVED | 21 | 8 | 17 | 8 | Bookings Totals, Number of Cards In Match |
| player_fouls_committed | MARKET_NAME_ONLY | 19 | 0 | 13 | 7 | Player Fouls |
| player_fouled | MARKET_NAME_ONLY | 14 | 0 | 8 | 7 | Player To Be Fouled |
| player_cards | MARKET_NAME_ONLY | 24 | 0 | 18 | 8 | Player Cards |

## Decision

- `PAIRED_PRICES_OBSERVED`: eligible for definition checks and a preregistered shadow-model experiment.
- `MARKET_NAME_ONLY`: the label was observed, but the legacy audit cannot prove usable paired prices.
- `NOT_OBSERVED`: not returned by the configured feed; do not assume it can be automated.
- Live staking remains blocked until count, settlement, real-price ROI and CLV gates pass.
