# Football Team Form Layer Report

Generated: 2026-04-25T10:02:13+00:00

## Outputs

- `data/football-form/team-match-base.csv`
- `data/football-form/team-rolling-form.csv`

## Summary

- Match rows: 21357
- Team-match rows: 42714
- Rolling-form rows: 42714
- Date range: 2014-08-08 to 2026-04-23
- Leagues: bundesliga, epl, la-liga, ligue-1, serie-a
- Team rows with xG: 2782 (6.5%)
- Team rows with market 1X2 strength: 42702 (100.0%)

## xG Overlay

```json
{
  "matched": 1520,
  "rows": 1520,
  "unmatched": 0,
  "with_xg": 1391
}
```

## League Coverage

| League | Team rows | Rows with xG | xG coverage |
| --- | ---: | ---: | ---: |
| bundesliga | 7272 | 480 | 6.6% |
| epl | 9024 | 664 | 7.4% |
| la-liga | 9000 | 516 | 5.7% |
| ligue-1 | 8398 | 528 | 6.3% |
| serie-a | 9020 | 594 | 6.6% |

## Notes

- Rolling features are causal: each row uses only prior matches for that team.
- Current-match raw stats are included for backtests; model training must avoid using current_* as predictors for pre-match bets.
- Venue-split rolling shots, SOT, and corners are included so live models do not have to rebuild those histories separately.
- Opponent strength is currently a bookmaker 1X2 proxy from previous matches, not an Elo system.
- xG is overlaid where FBref data matches the Football-Data fixture key; older historical rows remain shots/corners only.
