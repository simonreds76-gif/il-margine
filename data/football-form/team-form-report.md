# Football Team Form Layer Report

Generated: 2026-05-12T10:30:53+00:00

## Outputs

- `data/football-form/team-match-base.csv`
- `data/football-form/team-rolling-form.csv`

## Summary

- Match rows: 21498
- Team-match rows: 42996
- Rolling-form rows: 42996
- Date range: 2014-08-08 to 2026-05-11
- Leagues: bundesliga, epl, la-liga, ligue-1, serie-a
- Team rows with xG: 2944 (6.8%)
- Team rows with market 1X2 strength: 42984 (100.0%)

## xG Overlay

```json
{
  "matched": 1613,
  "rows": 1613,
  "unmatched": 0,
  "with_xg": 1472
}
```

## League Coverage

| League | Team rows | Rows with xG | xG coverage |
| --- | ---: | ---: | ---: |
| bundesliga | 7326 | 512 | 7.0% |
| epl | 9078 | 698 | 7.7% |
| la-liga | 9060 | 548 | 6.0% |
| ligue-1 | 8452 | 556 | 6.6% |
| serie-a | 9080 | 630 | 6.9% |

## Notes

- Rolling features are causal: each row uses only prior matches for that team.
- EMA20 fields are causal with decay 0.93; newest prior match receives weight 1.0.
- League-relative fields include all-prior and trailing-12-month causal baselines; both exclude the current matchday.
- Current-match raw stats are included for backtests; model training must avoid using current_* as predictors for pre-match bets.
- Venue-split rolling shots, SOT, and corners are included so live models do not have to rebuild those histories separately.
- Opponent strength is currently a bookmaker 1X2 proxy from previous matches, not an Elo system.
- xG is overlaid where FBref data matches the Football-Data fixture key; older historical rows remain shots/corners only.
