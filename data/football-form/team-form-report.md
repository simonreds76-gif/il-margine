# Football Team Form Layer Report

Generated: 2026-04-28T10:27:22+00:00

## Outputs

- `data/football-form/team-match-base.csv`
- `data/football-form/team-rolling-form.csv`

## Summary

- Match rows: 21398
- Team-match rows: 42796
- Rolling-form rows: 42796
- Date range: 2014-08-08 to 2026-04-26
- Leagues: bundesliga, epl, la-liga, ligue-1, serie-a
- Team rows with xG: 2858 (6.7%)
- Team rows with market 1X2 strength: 42784 (100.0%)

## xG Overlay

```json
{
  "matched": 1561,
  "rows": 1561,
  "unmatched": 0,
  "with_xg": 1429
}
```

## League Coverage

| League | Team rows | Rows with xG | xG coverage |
| --- | ---: | ---: | ---: |
| bundesliga | 7290 | 496 | 6.8% |
| epl | 9036 | 676 | 7.5% |
| la-liga | 9018 | 532 | 5.9% |
| ligue-1 | 8416 | 546 | 6.5% |
| serie-a | 9036 | 608 | 6.7% |

## Notes

- Rolling features are causal: each row uses only prior matches for that team.
- EMA20 fields are causal with decay 0.93; newest prior match receives weight 1.0.
- League-relative fields include all-prior and trailing-12-month causal baselines; both exclude the current matchday.
- Current-match raw stats are included for backtests; model training must avoid using current_* as predictors for pre-match bets.
- Venue-split rolling shots, SOT, and corners are included so live models do not have to rebuild those histories separately.
- Opponent strength is currently a bookmaker 1X2 proxy from previous matches, not an Elo system.
- xG is overlaid where FBref data matches the Football-Data fixture key; older historical rows remain shots/corners only.
