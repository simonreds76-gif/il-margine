# Football Team Form Layer Report

Generated: 2026-05-16T19:59:35+00:00

## Outputs

- `data/football-form/team-match-base.csv`
- `data/football-form/team-rolling-form.csv`

## Summary

- Match rows: 21511
- Team-match rows: 43022
- Rolling-form rows: 43022
- Date range: 2014-08-08 to 2026-05-14
- Leagues: bundesliga, epl, la-liga, ligue-1, serie-a
- Team rows with xG: 3053 (7.1%)
- Team rows with market 1X2 strength: 43010 (100.0%)

## xG Overlay

```json
{
  "matched": 1674,
  "rows": 1674,
  "unmatched": 0,
  "with_xg": 1527
}
```

## League Coverage

| League | Team rows | Rows with xG | xG coverage |
| --- | ---: | ---: | ---: |
| bundesliga | 7326 | 528 | 7.2% |
| epl | 9080 | 720 | 7.9% |
| la-liga | 9080 | 580 | 6.4% |
| ligue-1 | 8456 | 578 | 6.8% |
| serie-a | 9080 | 647 | 7.1% |

## Notes

- Rolling features are causal: each row uses only prior matches for that team.
- EMA20 fields are causal with decay 0.93; newest prior match receives weight 1.0.
- League-relative fields include all-prior and trailing-12-month causal baselines; both exclude the current matchday.
- Current-match raw stats are included for backtests; model training must avoid using current_* as predictors for pre-match bets.
- Venue-split rolling shots, SOT, and corners are included so live models do not have to rebuild those histories separately.
- Opponent strength is currently a bookmaker 1X2 proxy from previous matches, not an Elo system.
- xG is overlaid where FBref data matches the Football-Data fixture key; older historical rows remain shots/corners only.
