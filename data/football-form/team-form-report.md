# Football Team Form Layer Report

Generated: 2026-10-24T12:43:40+00:00

## Outputs

- `data/football-form/team-match-base.csv`
- `data/football-form/team-rolling-form.csv`

## Summary

- Match rows: 21935
- Team-match rows: 43870
- Rolling-form rows: 43870
- Date range: 2014-08-08 to 2026-10-21
- Leagues: bundesliga, epl, la-liga, ligue-1, serie-a
- Team rows with xG: 40187 (91.6%)
- Team rows with market 1X2 strength: 43858 (100.0%)

## xG Overlay

```json
{
  "matched": 21935,
  "rows": 21935,
  "unmatched": 0,
  "with_xg": 20100
}
```

## League Coverage

| League | Team rows | Rows with xG | xG coverage |
| --- | ---: | ---: | ---: |
| bundesliga | 7452 | 6442 | 86.4% |
| epl | 9260 | 9130 | 98.6% |
| la-liga | 9298 | 7573 | 81.4% |
| ligue-1 | 8600 | 8206 | 95.4% |
| serie-a | 9260 | 8836 | 95.4% |

## Notes

- Rolling features are causal: each row uses only prior matches for that team.
- EMA20 fields are causal with decay 0.93; newest prior match receives weight 1.0.
- League-relative fields include all-prior and trailing-12-month causal baselines; both exclude the current matchday.
- Current-match raw stats are included for backtests; model training must avoid using current_* as predictors for pre-match bets.
- Venue-split rolling shots, SOT, and corners are included so live models do not have to rebuild those histories separately.
- Opponent strength is currently a bookmaker 1X2 proxy from previous matches, not an Elo system.
- Understat xG is overlaid where it matches the Football-Data fixture key; older historical rows remain shots/corners only.
