# Corners CLV Monitor: `corners_v3`

Generated: 2026-10-22T13:51:57Z
Picks input: `data/football-form/corners-v3-shadow-signals.csv`
Pinnacle input: `data/corners-ou/pinnacle-corners-odds.csv`

## Summary

- Picks: 119
- Active published picks: 119
- Settled: 119
- Open/pending: 0
- Settled PnL: -1.38u
- Picks with close: 119
- True-close coverage (<=120m): 60/119 (50.4%)
- Average true-close CLV: +1.04% (n=60)
- Hard-guard blocked: 0
- Average published-to-close CLV: +1.24%
- Allowed-league config valid: yes
- Allowed leagues: `bundesliga, epl, la-liga, ligue-1, serie-a`
- Config error: `-`

## Active Side Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over | 23 | 23 | 0 | 11-12-0 | -1.68u | -7.29% | +0.66% (n=23) |
| Under | 96 | 96 | 0 | 46-50-0 | +0.29u | +0.31% | +1.38% (n=96) |

## Active League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| bundesliga | 17 | 17 | 0 | 4-13-0 | -8.15u | -47.97% | +0.39% (n=17) |
| epl | 17 | 17 | 0 | 10-7-0 | +3.46u | +20.36% | +1.70% (n=17) |
| la-liga | 25 | 25 | 0 | 13-12-0 | +2.60u | +10.40% | +2.16% (n=25) |
| ligue-1 | 37 | 37 | 0 | 18-19-0 | +0.04u | +0.11% | +1.48% (n=37) |
| serie-a | 23 | 23 | 0 | 12-11-0 | +0.67u | +2.91% | +0.16% (n=23) |

## Active Side x League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over / epl | 1 | 1 | 0 | 1-0-0 | +0.98u | +98.00% | +0.00% (n=1) |
| Over / la-liga | 6 | 6 | 0 | 1-5-0 | -4.00u | -66.67% | +2.76% (n=6) |
| Over / ligue-1 | 2 | 2 | 0 | 1-1-0 | -0.17u | -8.70% | +0.18% (n=2) |
| Over / serie-a | 14 | 14 | 0 | 8-6-0 | +1.52u | +10.84% | -0.13% (n=14) |
| Under / bundesliga | 17 | 17 | 0 | 4-13-0 | -8.15u | -47.97% | +0.39% (n=17) |
| Under / epl | 16 | 16 | 0 | 9-7-0 | +2.48u | +15.51% | +1.80% (n=16) |
| Under / la-liga | 19 | 19 | 0 | 12-7-0 | +6.60u | +34.74% | +1.98% (n=19) |
| Under / ligue-1 | 35 | 35 | 0 | 17-18-0 | +0.21u | +0.61% | +1.55% (n=35) |
| Under / serie-a | 9 | 9 | 0 | 4-5-0 | -0.85u | -9.43% | +0.61% (n=9) |

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
