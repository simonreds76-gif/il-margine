# Corners CLV Monitor: `corners_v3`

Generated: 2026-09-07T10:44:52Z
Picks input: `data/football-form/corners-v3-shadow-signals.csv`
Pinnacle input: `data/corners-ou/pinnacle-corners-odds.csv`

## Summary

- Picks: 37
- Active published picks: 37
- Settled: 28
- Open/pending: 9
- Settled PnL: -3.15u
- Picks with close: 37
- True-close coverage (<=120m): 15/36 (41.7%)
- Average true-close CLV: +2.73% (n=15)
- Hard-guard blocked: 0
- Average published-to-close CLV: +2.50%
- Allowed-league config valid: yes
- Allowed leagues: `bundesliga, epl, la-liga, ligue-1, serie-a`
- Config error: `-`

## Active Side Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over | 9 | 7 | 2 | 3-4-0 | -1.19u | -16.96% | -2.08% (n=7) |
| Under | 28 | 21 | 7 | 9-12-0 | -1.96u | -9.33% | +3.31% (n=21) |

## Active League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| bundesliga | 3 | 2 | 1 | 0-2-0 | -2.00u | -100.00% | +0.23% (n=2) |
| epl | 5 | 3 | 2 | 2-1-0 | +0.88u | +29.33% | +2.38% (n=3) |
| la-liga | 8 | 6 | 2 | 4-2-0 | +2.96u | +49.33% | +6.49% (n=6) |
| ligue-1 | 12 | 9 | 3 | 2-7-0 | -4.59u | -50.97% | +2.40% (n=9) |
| serie-a | 9 | 8 | 1 | 4-4-0 | -0.40u | -5.00% | -1.63% (n=8) |

## Active Side x League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over / la-liga | 2 | 1 | 1 | 0-1-0 | -1.00u | -100.00% | +0.00% (n=1) |
| Over / ligue-1 | 1 | 1 | 0 | 0-1-0 | -1.00u | -100.00% | +0.00% (n=1) |
| Over / serie-a | 6 | 5 | 1 | 3-2-0 | +0.81u | +16.26% | -2.91% (n=5) |
| Under / bundesliga | 3 | 2 | 1 | 0-2-0 | -2.00u | -100.00% | +0.23% (n=2) |
| Under / epl | 5 | 3 | 2 | 2-1-0 | +0.88u | +29.33% | +2.38% (n=3) |
| Under / la-liga | 6 | 5 | 1 | 4-1-0 | +3.96u | +79.20% | +7.79% (n=5) |
| Under / ligue-1 | 11 | 8 | 3 | 2-6-0 | -3.59u | -44.84% | +2.70% (n=8) |
| Under / serie-a | 3 | 3 | 0 | 1-2-0 | -1.21u | -40.43% | +0.49% (n=3) |

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
