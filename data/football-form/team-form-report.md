# Football Team Form Layer Report

Generated: 2026-11-01T09:42:20+00:00

## Outputs

- `data/football-form/team-match-base.csv`
- `data/football-form/team-rolling-form.csv`

## Summary

- Match rows: 21993
- Team-match rows: 43986
- Rolling-form rows: 43986
- Date range: 2014-08-08 to 2026-10-29
- Leagues: bundesliga, epl, la-liga, ligue-1, serie-a
- Team rows with xG: 40327 (91.7%)
- Team rows with market 1X2 strength: 43974 (100.0%)

## xG Overlay

```json
{
  "matched": 21993,
  "rows": 21993,
  "unmatched": 0,
  "with_xg": 20170
}
```

## League Coverage

| League | Team rows | Rows with xG | xG coverage |
| --- | ---: | ---: | ---: |
| bundesliga | 7470 | 6472 | 86.6% |
| epl | 9280 | 9150 | 98.6% |
| la-liga | 9318 | 7595 | 81.5% |
| ligue-1 | 8618 | 8220 | 95.4% |
| serie-a | 9300 | 8890 | 95.6% |

## Notes

- Rolling features are causal: each row uses only prior matches for that team.
- EMA20 fields are causal with decay 0.93; newest prior match receives weight 1.0.
- League-relative fields include all-prior and trailing-12-month causal baselines; both exclude the current matchday.
- Current-match raw stats are included for backtests; model training must avoid using current_* as predictors for pre-match bets.
- Venue-split rolling shots, SOT, and corners are included so live models do not have to rebuild those histories separately.
- Opponent strength is currently a bookmaker 1X2 proxy from previous matches, not an Elo system.
- Understat xG is overlaid where it matches the Football-Data fixture key; older historical rows remain shots/corners only.
