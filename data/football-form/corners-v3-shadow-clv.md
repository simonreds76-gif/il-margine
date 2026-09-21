# Corners CLV Monitor: `corners_v3`

Generated: 2026-09-21T15:09:20Z
Picks input: `data/football-form/corners-v3-shadow-signals.csv`
Pinnacle input: `data/corners-ou/pinnacle-corners-odds.csv`

## Summary

- Picks: 77
- Active published picks: 77
- Settled: 69
- Open/pending: 8
- Settled PnL: -2.58u
- Picks with close: 77
- True-close coverage (<=120m): 35/77 (45.5%)
- Average true-close CLV: +1.21% (n=35)
- Hard-guard blocked: 0
- Average published-to-close CLV: +1.28%
- Allowed-league config valid: yes
- Allowed leagues: `bundesliga, epl, la-liga, ligue-1, serie-a`
- Config error: `-`

## Active Side Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over | 17 | 17 | 0 | 8-9-0 | -1.63u | -9.60% | -0.36% (n=17) |
| Under | 60 | 52 | 8 | 24-28-0 | -0.95u | -1.82% | +1.94% (n=52) |

## Active League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| bundesliga | 9 | 8 | 1 | 2-6-0 | -3.18u | -39.75% | +0.98% (n=8) |
| epl | 11 | 8 | 3 | 5-3-0 | +1.93u | +24.08% | +1.23% (n=8) |
| la-liga | 18 | 16 | 2 | 10-6-0 | +5.19u | +32.44% | +3.00% (n=16) |
| ligue-1 | 23 | 22 | 1 | 7-15-0 | -6.65u | -30.25% | +2.28% (n=22) |
| serie-a | 16 | 15 | 1 | 8-7-0 | +0.14u | +0.91% | -1.41% (n=15) |

## Active Side x League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over / la-liga | 6 | 6 | 0 | 1-5-0 | -4.00u | -66.67% | +2.76% (n=6) |
| Over / ligue-1 | 1 | 1 | 0 | 0-1-0 | -1.00u | -100.00% | +0.00% (n=1) |
| Over / serie-a | 10 | 10 | 0 | 7-3-0 | +3.37u | +33.68% | -2.27% (n=10) |
| Under / bundesliga | 9 | 8 | 1 | 2-6-0 | -3.18u | -39.75% | +0.98% (n=8) |
| Under / epl | 11 | 8 | 3 | 5-3-0 | +1.93u | +24.08% | +1.23% (n=8) |
| Under / la-liga | 12 | 10 | 2 | 9-1-0 | +9.19u | +91.90% | +3.14% (n=10) |
| Under / ligue-1 | 22 | 21 | 1 | 7-14-0 | -5.65u | -26.92% | +2.39% (n=21) |
| Under / serie-a | 6 | 5 | 1 | 1-4-0 | -3.23u | -64.62% | +0.29% (n=5) |

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
