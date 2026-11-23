# Football Team Form Layer Report

Generated: 2026-11-23T20:17:54+00:00

## Outputs

- `data/football-form/team-match-base.csv`
- `data/football-form/team-rolling-form.csv`

## Summary

- Match rows: 22134
- Team-match rows: 44268
- Rolling-form rows: 44268
- Date range: 2014-08-08 to 2026-11-22
- Leagues: bundesliga, epl, la-liga, ligue-1, serie-a
- Team rows with xG: 40327 (91.1%)
- Team rows with market 1X2 strength: 44256 (100.0%)

## xG Overlay

```json
{
  "matched": 22134,
  "rows": 22134,
  "unmatched": 0,
  "with_xg": 20170
}
```

## League Coverage

| League | Team rows | Rows with xG | xG coverage |
| --- | ---: | ---: | ---: |
| bundesliga | 7524 | 6472 | 86.0% |
| epl | 9338 | 9150 | 98.0% |
| la-liga | 9376 | 7595 | 81.0% |
| ligue-1 | 8672 | 8220 | 94.8% |
| serie-a | 9358 | 8890 | 95.0% |

## Notes

- Rolling features are causal: each row uses only prior matches for that team.
- EMA20 fields are causal with decay 0.93; newest prior match receives weight 1.0.
- League-relative fields include all-prior and trailing-12-month causal baselines; both exclude the current matchday.
- Current-match raw stats are included for backtests; model training must avoid using current_* as predictors for pre-match bets.
- Venue-split rolling shots, SOT, and corners are included so live models do not have to rebuild those histories separately.
- Opponent strength is currently a bookmaker 1X2 proxy from previous matches, not an Elo system.
- Understat xG is overlaid where it matches the Football-Data fixture key; older historical rows remain shots/corners only.
