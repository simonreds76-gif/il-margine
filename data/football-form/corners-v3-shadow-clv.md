# Corners CLV Monitor: `corners_v3`

Generated: 2026-09-25T13:52:34Z
Picks input: `data/football-form/corners-v3-shadow-signals.csv`
Pinnacle input: `data/corners-ou/pinnacle-corners-odds.csv`

## Summary

- Picks: 77
- Active published picks: 77
- Settled: 77
- Open/pending: 0
- Settled PnL: -2.11u
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
| Under | 60 | 60 | 0 | 28-32-0 | -0.48u | -0.79% | +1.74% (n=60) |

## Active League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| bundesliga | 9 | 9 | 0 | 2-7-0 | -4.18u | -46.44% | -0.13% (n=9) |
| epl | 11 | 11 | 0 | 6-5-0 | +1.29u | +11.69% | +3.07% (n=11) |
| la-liga | 18 | 18 | 0 | 12-6-0 | +7.44u | +41.33% | +2.07% (n=18) |
| ligue-1 | 23 | 23 | 0 | 7-16-0 | -7.65u | -33.28% | +2.16% (n=23) |
| serie-a | 16 | 16 | 0 | 9-7-0 | +1.00u | +6.24% | -1.32% (n=16) |

## Active Side x League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over / la-liga | 6 | 6 | 0 | 1-5-0 | -4.00u | -66.67% | +2.76% (n=6) |
| Over / ligue-1 | 1 | 1 | 0 | 0-1-0 | -1.00u | -100.00% | +0.00% (n=1) |
| Over / serie-a | 10 | 10 | 0 | 7-3-0 | +3.37u | +33.68% | -2.27% (n=10) |
| Under / bundesliga | 9 | 9 | 0 | 2-7-0 | -4.18u | -46.44% | -0.13% (n=9) |
| Under / epl | 11 | 11 | 0 | 6-5-0 | +1.29u | +11.69% | +3.07% (n=11) |
| Under / la-liga | 12 | 12 | 0 | 11-1-0 | +11.44u | +95.33% | +1.72% (n=12) |
| Under / ligue-1 | 22 | 22 | 0 | 7-15-0 | -6.65u | -30.25% | +2.26% (n=22) |
| Under / serie-a | 6 | 6 | 0 | 2-4-0 | -2.37u | -39.48% | +0.25% (n=6) |

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
