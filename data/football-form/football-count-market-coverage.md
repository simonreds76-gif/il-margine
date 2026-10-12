# Football Count Market Coverage

Generated: 2026-10-12T15:00:39Z

This report measures what the configured odds feed actually exposes. A bookmaker offering a market on its website does not prove the aggregator returns it.

| Category | Status | Events | Paired O/U events | Pairing unknown | Competitions | Raw labels |
|---|---|---:|---:|---:|---:|---|
| team_fouls_total | MARKET_NAME_ONLY | 4 | 0 | 0 | 3 | Total Fouls Away, Total Fouls Home |
| match_fouls_total | MARKET_NAME_ONLY | 4 | 0 | 0 | 3 | Total Fouls |
| team_cards_total | PAIRED_PRICES_OBSERVED | 13 | 4 | 12 | 8 | Bookings Totals Away, Bookings Totals Home |
| match_cards_total | PAIRED_PRICES_OBSERVED | 13 | 4 | 12 | 8 | Bookings Totals, Number of Cards In Match |
| player_fouls_committed | MARKET_NAME_ONLY | 11 | 0 | 11 | 7 | Player Fouls |
| player_fouled | MARKET_NAME_ONLY | 11 | 0 | 11 | 7 | Player To Be Fouled |
| player_cards | MARKET_NAME_ONLY | 11 | 0 | 11 | 7 | Player Cards |

## Decision

- `PAIRED_PRICES_OBSERVED`: eligible for definition checks and a preregistered shadow-model experiment.
- `MARKET_NAME_ONLY`: the label was observed, but the legacy audit cannot prove usable paired prices.
- `NOT_OBSERVED`: not returned by the configured feed; do not assume it can be automated.
- Live staking remains blocked until count, settlement, real-price ROI and CLV gates pass.
