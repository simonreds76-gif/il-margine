# Corners CLV Monitor: `corners_v3`

Generated: 2026-09-17T13:32:27Z
Picks input: `data/football-form/corners-v3-shadow-signals.csv`
Pinnacle input: `data/corners-ou/pinnacle-corners-odds.csv`

## Summary

- Picks: 71
- Active published picks: 71
- Settled: 57
- Open/pending: 14
- Settled PnL: -3.19u
- Picks with close: 71
- True-close coverage (<=120m): 19/57 (33.3%)
- Average true-close CLV: +1.83% (n=19)
- Hard-guard blocked: 0
- Average published-to-close CLV: +1.80%
- Allowed-league config valid: yes
- Allowed leagues: `bundesliga, epl, la-liga, ligue-1, serie-a`
- Config error: `-`

## Active Side Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over | 16 | 15 | 1 | 6-9-0 | -3.19u | -21.30% | +0.01% (n=15) |
| Under | 55 | 42 | 13 | 20-22-0 | +0.00u | +0.00% | +2.52% (n=42) |

## Active League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| bundesliga | 7 | 5 | 2 | 0-5-0 | -5.00u | -100.00% | +2.48% (n=5) |
| epl | 11 | 7 | 4 | 5-2-0 | +2.93u | +41.80% | +2.27% (n=7) |
| la-liga | 17 | 14 | 3 | 8-6-0 | +2.96u | +21.14% | +4.03% (n=14) |
| ligue-1 | 22 | 18 | 4 | 7-11-0 | -2.65u | -14.74% | +2.02% (n=18) |
| serie-a | 14 | 13 | 1 | 6-7-0 | -1.43u | -10.97% | -1.15% (n=13) |

## Active Side x League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over / la-liga | 6 | 6 | 0 | 1-5-0 | -4.00u | -66.67% | +2.76% (n=6) |
| Over / ligue-1 | 1 | 1 | 0 | 0-1-0 | -1.00u | -100.00% | +0.00% (n=1) |
| Over / serie-a | 9 | 8 | 1 | 5-3-0 | +1.80u | +22.56% | -2.05% (n=8) |
| Under / bundesliga | 7 | 5 | 2 | 0-5-0 | -5.00u | -100.00% | +2.48% (n=5) |
| Under / epl | 11 | 7 | 4 | 5-2-0 | +2.93u | +41.80% | +2.27% (n=7) |
| Under / la-liga | 11 | 8 | 3 | 7-1-0 | +6.96u | +87.00% | +4.98% (n=8) |
| Under / ligue-1 | 21 | 17 | 4 | 7-10-0 | -1.65u | -9.73% | +2.14% (n=17) |
| Under / serie-a | 5 | 5 | 0 | 1-4-0 | -3.23u | -64.62% | +0.29% (n=5) |

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
