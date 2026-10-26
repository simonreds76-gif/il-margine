# Corners CLV Monitor: `corners_v3`

Generated: 2026-10-26T15:16:48Z
Picks input: `data/football-form/corners-v3-shadow-signals.csv`
Pinnacle input: `data/corners-ou/pinnacle-corners-odds.csv`

## Summary

- Picks: 146
- Active published picks: 146
- Settled: 131
- Open/pending: 15
- Settled PnL: -5.10u
- Picks with close: 146
- True-close coverage (<=120m): 83/143 (58.0%)
- Average true-close CLV: +1.29% (n=83)
- Hard-guard blocked: 0
- Average published-to-close CLV: +1.33%
- Allowed-league config valid: yes
- Allowed leagues: `bundesliga, epl, la-liga, ligue-1, serie-a`
- Config error: `-`

## Active Side Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over | 30 | 26 | 4 | 12-14-0 | -2.46u | -9.45% | +1.04% (n=26) |
| Under | 116 | 105 | 11 | 49-56-0 | -2.64u | -2.52% | +1.41% (n=105) |

## Active League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| bundesliga | 20 | 19 | 1 | 5-14-0 | -8.30u | -43.68% | +0.48% (n=19) |
| epl | 21 | 18 | 3 | 10-8-0 | +2.46u | +13.68% | +1.71% (n=18) |
| la-liga | 31 | 29 | 2 | 15-14-0 | +2.81u | +9.69% | +2.12% (n=29) |
| ligue-1 | 42 | 38 | 4 | 18-20-0 | -0.96u | -2.52% | +1.53% (n=38) |
| serie-a | 32 | 27 | 5 | 13-14-0 | -1.11u | -4.11% | +0.58% (n=27) |

## Active Side x League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over / epl | 3 | 1 | 2 | 1-0-0 | +0.98u | +98.00% | +0.00% (n=1) |
| Over / la-liga | 6 | 6 | 0 | 1-5-0 | -4.00u | -66.67% | +2.76% (n=6) |
| Over / ligue-1 | 2 | 2 | 0 | 1-1-0 | -0.17u | -8.70% | +0.18% (n=2) |
| Over / serie-a | 19 | 17 | 2 | 9-8-0 | +0.74u | +4.34% | +0.59% (n=17) |
| Under / bundesliga | 20 | 19 | 1 | 5-14-0 | -8.30u | -43.68% | +0.48% (n=19) |
| Under / epl | 18 | 17 | 1 | 9-8-0 | +1.48u | +8.72% | +1.81% (n=17) |
| Under / la-liga | 25 | 23 | 2 | 14-9-0 | +6.81u | +29.61% | +1.96% (n=23) |
| Under / ligue-1 | 40 | 36 | 4 | 17-19-0 | -0.79u | -2.18% | +1.60% (n=36) |
| Under / serie-a | 13 | 10 | 3 | 4-6-0 | -1.85u | -18.49% | +0.55% (n=10) |

## Required Fields

- `current_model_would_have_priced` must be true for publication while canonical-only evidence is below threshold.
- `time_to_kickoff_hours` records publication timing so CLV can be interpreted by lead time.
- `published_to_close_clv` tracks the taken/published Pinnacle price versus close.
- `close_lag_minutes` records how far the selected close snapshot was from kickoff; `true_close=true` requires <=120 minutes.
- `model_to_close_clv` tracks the model-implied probability versus close.
- `confidence_guard_applied=true` means the row must not be treated as a published pick.

## De-Promotion Rules

- Pause `corners_v3` if 30-day rolling CLV is below 0 with at least 50 settled picks.
- Pause corners v0 if rolling 90-day production Brier exceeds 1.05x the pre-promotion backtest Brier.

## Re-Promotion Rules After A Pause

- Re-run the original full-window and last-90 Brier/log-loss gates.
- Document the specific cause of the pause: negative CLV drift or Brier calibration drift.
- Ship a documented data/model/scope change before re-enabling; do not simply re-enable because variance looks nicer.
- Wait at least 14 days after the pause before attempting re-promotion.
