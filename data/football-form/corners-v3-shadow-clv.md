# Corners CLV Monitor: `corners_v3`

Generated: 2026-09-20T13:06:19Z
Picks input: `data/football-form/corners-v3-shadow-signals.csv`
Pinnacle input: `data/corners-ou/pinnacle-corners-odds.csv`

## Summary

- Picks: 77
- Active published picks: 77
- Settled: 60
- Open/pending: 17
- Settled PnL: -6.19u
- Picks with close: 77
- True-close coverage (<=120m): 30/71 (42.3%)
- Average true-close CLV: +1.77% (n=30)
- Hard-guard blocked: 0
- Average published-to-close CLV: +1.33%
- Allowed-league config valid: yes
- Allowed leagues: `bundesliga, epl, la-liga, ligue-1, serie-a`
- Config error: `-`

## Active Side Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over | 17 | 15 | 2 | 6-9-0 | -3.19u | -21.30% | +0.01% (n=15) |
| Under | 60 | 45 | 15 | 20-25-0 | -3.00u | -6.66% | +2.27% (n=45) |

## Active League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| bundesliga | 9 | 6 | 3 | 0-6-0 | -6.00u | -100.00% | +1.61% (n=6) |
| epl | 11 | 8 | 3 | 5-3-0 | +1.93u | +24.08% | +1.23% (n=8) |
| la-liga | 18 | 14 | 4 | 8-6-0 | +2.96u | +21.14% | +4.03% (n=14) |
| ligue-1 | 23 | 19 | 4 | 7-12-0 | -3.65u | -19.23% | +2.18% (n=19) |
| serie-a | 16 | 13 | 3 | 6-7-0 | -1.43u | -10.97% | -1.15% (n=13) |

## Active Side x League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over / la-liga | 6 | 6 | 0 | 1-5-0 | -4.00u | -66.67% | +2.76% (n=6) |
| Over / ligue-1 | 1 | 1 | 0 | 0-1-0 | -1.00u | -100.00% | +0.00% (n=1) |
| Over / serie-a | 10 | 8 | 2 | 5-3-0 | +1.80u | +22.56% | -2.05% (n=8) |
| Under / bundesliga | 9 | 6 | 3 | 0-6-0 | -6.00u | -100.00% | +1.61% (n=6) |
| Under / epl | 11 | 8 | 3 | 5-3-0 | +1.93u | +24.08% | +1.23% (n=8) |
| Under / la-liga | 12 | 8 | 4 | 7-1-0 | +6.96u | +87.00% | +4.98% (n=8) |
| Under / ligue-1 | 22 | 18 | 4 | 7-11-0 | -2.65u | -14.74% | +2.30% (n=18) |
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
