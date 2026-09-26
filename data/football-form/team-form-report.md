# Football Team Form Layer Report

Generated: 2026-09-26T13:09:28+00:00

## Outputs

- `data/football-form/team-match-base.csv`
- `data/football-form/team-rolling-form.csv`

## Summary

- Match rows: 21839
- Team-match rows: 43678
- Rolling-form rows: 43678
- Date range: 2014-08-08 to 2026-09-20
- Leagues: bundesliga, epl, la-liga, ligue-1, serie-a
- Team rows with xG: 39963 (91.5%)
- Team rows with market 1X2 strength: 43666 (100.0%)

## xG Overlay

```json
{
  "matched": 21839,
  "rows": 21839,
  "unmatched": 0,
  "with_xg": 19988
}
```

## League Coverage

| League | Team rows | Rows with xG | xG coverage |
| --- | ---: | ---: | ---: |
| bundesliga | 7416 | 6410 | 86.4% |
| epl | 9220 | 9090 | 98.6% |
| la-liga | 9258 | 7493 | 80.9% |
| ligue-1 | 8564 | 8170 | 95.4% |
| serie-a | 9220 | 8800 | 95.4% |

## Notes

- Rolling features are causal: each row uses only prior matches for that team.
- EMA20 fields are causal with decay 0.93; newest prior match receives weight 1.0.
- League-relative fields include all-prior and trailing-12-month causal baselines; both exclude the current matchday.
- Current-match raw stats are included for backtests; model training must avoid using current_* as predictors for pre-match bets.
- Venue-split rolling shots, SOT, and corners are included so live models do not have to rebuild those histories separately.
- Opponent strength is currently a bookmaker 1X2 proxy from previous matches, not an Elo system.
- Understat xG is overlaid where it matches the Football-Data fixture key; older historical rows remain shots/corners only.
