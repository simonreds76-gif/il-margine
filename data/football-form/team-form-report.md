# Football Team Form Layer Report

Generated: 2026-05-23T09:46:06+00:00

## Outputs

- `data/football-form/team-match-base.csv`
- `data/football-form/team-rolling-form.csv`

## Summary

- Match rows: 21558
- Team-match rows: 43116
- Rolling-form rows: 43116
- Date range: 2014-08-08 to 2026-05-19
- Leagues: bundesliga, epl, la-liga, ligue-1, serie-a
- Team rows with xG: 3139 (7.3%)
- Team rows with market 1X2 strength: 43104 (100.0%)

## xG Overlay

```json
{
  "matched": 1721,
  "rows": 1721,
  "unmatched": 0,
  "with_xg": 1570
}
```

## League Coverage

| League | Team rows | Rows with xG | xG coverage |
| --- | ---: | ---: | ---: |
| bundesliga | 7344 | 544 | 7.4% |
| epl | 9100 | 740 | 8.1% |
| la-liga | 9100 | 596 | 6.5% |
| ligue-1 | 8472 | 594 | 7.0% |
| serie-a | 9100 | 665 | 7.3% |

## Notes

- Rolling features are causal: each row uses only prior matches for that team.
- EMA20 fields are causal with decay 0.93; newest prior match receives weight 1.0.
- League-relative fields include all-prior and trailing-12-month causal baselines; both exclude the current matchday.
- Current-match raw stats are included for backtests; model training must avoid using current_* as predictors for pre-match bets.
- Venue-split rolling shots, SOT, and corners are included so live models do not have to rebuild those histories separately.
- Opponent strength is currently a bookmaker 1X2 proxy from previous matches, not an Elo system.
- xG is overlaid where FBref data matches the Football-Data fixture key; older historical rows remain shots/corners only.
