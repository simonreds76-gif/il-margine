# Corners CLV Monitor: `corners_v3`

Generated: 2026-09-01T14:27:13Z
Picks input: `data\football-form\corners-v3-shadow-signals.csv`
Pinnacle input: `data\corners-ou\pinnacle-corners-odds.csv`

## Summary

- Picks: 37
- Active published picks: 37
- Settled: 26
- Open/pending: 11
- Settled PnL: -4.92u
- Picks with close: 37
- True-close coverage (<=120m): 15/28 (53.6%)
- Average true-close CLV: +2.73% (n=15)
- Hard-guard blocked: 0
- Average published-to-close CLV: +1.49%
- Allowed-league config valid: yes
- Allowed leagues: `bundesliga, epl, la-liga, ligue-1, serie-a`
- Config error: `-`

## Active Side Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over | 9 | 6 | 3 | 2-4-0 | -2.14u | -35.65% | -2.11% (n=6) |
| Under | 28 | 20 | 8 | 8-12-0 | -2.78u | -13.90% | +3.30% (n=20) |

## Active League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| bundesliga | 3 | 2 | 1 | 0-2-0 | -2.00u | -100.00% | +0.23% (n=2) |
| epl | 5 | 2 | 3 | 1-1-0 | +0.06u | +3.00% | +1.80% (n=2) |
| la-liga | 8 | 6 | 2 | 4-2-0 | +2.96u | +49.33% | +6.49% (n=6) |
| ligue-1 | 12 | 9 | 3 | 2-7-0 | -4.59u | -50.97% | +2.40% (n=9) |
| serie-a | 9 | 7 | 2 | 3-4-0 | -1.35u | -19.31% | -1.59% (n=7) |

## Active Side x League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over / la-liga | 2 | 1 | 1 | 0-1-0 | -1.00u | -100.00% | +0.00% (n=1) |
| Over / ligue-1 | 1 | 1 | 0 | 0-1-0 | -1.00u | -100.00% | +0.00% (n=1) |
| Over / serie-a | 6 | 4 | 2 | 2-2-0 | -0.14u | -3.48% | -3.16% (n=4) |
| Under / bundesliga | 3 | 2 | 1 | 0-2-0 | -2.00u | -100.00% | +0.23% (n=2) |
| Under / epl | 5 | 2 | 3 | 1-1-0 | +0.06u | +3.00% | +1.80% (n=2) |
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
