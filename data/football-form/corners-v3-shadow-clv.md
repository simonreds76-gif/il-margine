# Corners CLV Monitor: `corners_v3`

Generated: 2026-10-25T13:15:42Z
Picks input: `data/football-form/corners-v3-shadow-signals.csv`
Pinnacle input: `data/corners-ou/pinnacle-corners-odds.csv`

## Summary

- Picks: 143
- Active published picks: 143
- Settled: 123
- Open/pending: 20
- Settled PnL: -5.38u
- Picks with close: 143
- True-close coverage (<=120m): 71/131 (54.2%)
- Average true-close CLV: +1.26% (n=71)
- Hard-guard blocked: 0
- Average published-to-close CLV: +1.31%
- Allowed-league config valid: yes
- Allowed leagues: `bundesliga, epl, la-liga, ligue-1, serie-a`
- Config error: `-`

## Active Side Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over | 28 | 24 | 4 | 11-13-0 | -2.68u | -11.15% | +0.94% (n=24) |
| Under | 115 | 99 | 16 | 46-53-0 | -2.71u | -2.73% | +1.45% (n=99) |

## Active League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| bundesliga | 20 | 18 | 2 | 4-14-0 | -9.15u | -50.86% | +0.28% (n=18) |
| epl | 20 | 17 | 3 | 10-7-0 | +3.46u | +20.36% | +1.70% (n=17) |
| la-liga | 31 | 26 | 5 | 13-13-0 | +1.60u | +6.15% | +2.42% (n=26) |
| ligue-1 | 42 | 38 | 4 | 18-20-0 | -0.96u | -2.52% | +1.53% (n=38) |
| serie-a | 30 | 24 | 6 | 12-12-0 | -0.33u | -1.38% | +0.47% (n=24) |

## Active Side x League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over / epl | 2 | 1 | 1 | 1-0-0 | +0.98u | +98.00% | +0.00% (n=1) |
| Over / la-liga | 6 | 6 | 0 | 1-5-0 | -4.00u | -66.67% | +2.76% (n=6) |
| Over / ligue-1 | 2 | 2 | 0 | 1-1-0 | -0.17u | -8.70% | +0.18% (n=2) |
| Over / serie-a | 18 | 15 | 3 | 8-7-0 | +0.52u | +3.45% | +0.38% (n=15) |
| Under / bundesliga | 20 | 18 | 2 | 4-14-0 | -9.15u | -50.86% | +0.28% (n=18) |
| Under / epl | 18 | 16 | 2 | 9-7-0 | +2.48u | +15.51% | +1.80% (n=16) |
| Under / la-liga | 25 | 20 | 5 | 12-8-0 | +5.60u | +28.00% | +2.32% (n=20) |
| Under / ligue-1 | 40 | 36 | 4 | 17-19-0 | -0.79u | -2.18% | +1.60% (n=36) |
| Under / serie-a | 12 | 9 | 3 | 4-5-0 | -0.85u | -9.43% | +0.61% (n=9) |

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
