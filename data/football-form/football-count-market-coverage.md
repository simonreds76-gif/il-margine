# Football Count Market Coverage

Generated: 2026-10-27T14:35:46Z

This report measures what the configured odds feed actually exposes. A bookmaker offering a market on its website does not prove the aggregator returns it.

| Category | Status | Events | Paired O/U events | Pairing unknown | Competitions | Raw labels |
|---|---|---:|---:|---:|---:|---|
| team_fouls_total | MARKET_NAME_ONLY | 10 | 0 | 0 | 1 | Total Fouls Away, Total Fouls Home |
| match_fouls_total | MARKET_NAME_ONLY | 10 | 0 | 0 | 1 | Total Fouls |
| team_cards_total | MARKET_NAME_ONLY | 22 | 0 | 22 | 5 | Bookings Totals Away, Bookings Totals Home |
| match_cards_total | PAIRED_PRICES_OBSERVED | 32 | 10 | 22 | 6 | Bookings Totals, Number of Cards In Match |
| player_fouls_committed | MARKET_NAME_ONLY | 26 | 0 | 16 | 5 | Player Fouls |
| player_fouled | MARKET_NAME_ONLY | 16 | 0 | 16 | 4 | Player To Be Fouled |
| player_cards | MARKET_NAME_ONLY | 23 | 0 | 23 | 5 | Player Cards |

## Decision

- `PAIRED_PRICES_OBSERVED`: eligible for definition checks and a preregistered shadow-model experiment.
- `MARKET_NAME_ONLY`: the label was observed, but the legacy audit cannot prove usable paired prices.
- `NOT_OBSERVED`: not returned by the configured feed; do not assume it can be automated.
- Live staking remains blocked until count, settlement, real-price ROI and CLV gates pass.
