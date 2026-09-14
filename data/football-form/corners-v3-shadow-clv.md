# Corners CLV Monitor: `corners_v3`

Generated: 2026-09-14T15:04:21Z
Picks input: `data/football-form/corners-v3-shadow-signals.csv`
Pinnacle input: `data/corners-ou/pinnacle-corners-odds.csv`

## Summary

- Picks: 59
- Active published picks: 59
- Settled: 52
- Open/pending: 7
- Settled PnL: -5.89u
- Picks with close: 59
- True-close coverage (<=120m): 17/52 (32.7%)
- Average true-close CLV: +2.13% (n=17)
- Hard-guard blocked: 0
- Average published-to-close CLV: +1.98%
- Allowed-league config valid: yes
- Allowed leagues: `bundesliga, epl, la-liga, ligue-1, serie-a`
- Config error: `-`

## Active Side Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over | 15 | 13 | 2 | 5-8-0 | -3.25u | -25.04% | +0.12% (n=13) |
| Under | 44 | 39 | 5 | 17-22-0 | -2.63u | -6.76% | +2.74% (n=39) |

## Active League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| bundesliga | 6 | 5 | 1 | 0-5-0 | -5.00u | -100.00% | +2.48% (n=5) |
| epl | 8 | 6 | 2 | 4-2-0 | +2.10u | +35.00% | +2.58% (n=6) |
| la-liga | 14 | 11 | 3 | 6-5-0 | +2.15u | +19.55% | +5.21% (n=11) |
| ligue-1 | 18 | 18 | 0 | 7-11-0 | -2.65u | -14.74% | +2.02% (n=18) |
| serie-a | 13 | 12 | 1 | 5-7-0 | -2.49u | -20.72% | -1.09% (n=12) |

## Active Side x League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over / la-liga | 6 | 5 | 1 | 1-4-0 | -3.00u | -60.00% | +3.21% (n=5) |
| Over / ligue-1 | 1 | 1 | 0 | 0-1-0 | -1.00u | -100.00% | +0.00% (n=1) |
| Over / serie-a | 8 | 7 | 1 | 4-3-0 | +0.74u | +10.64% | -2.08% (n=7) |
| Under / bundesliga | 6 | 5 | 1 | 0-5-0 | -5.00u | -100.00% | +2.48% (n=5) |
| Under / epl | 8 | 6 | 2 | 4-2-0 | +2.10u | +35.00% | +2.58% (n=6) |
| Under / la-liga | 8 | 6 | 2 | 5-1-0 | +5.15u | +85.83% | +6.88% (n=6) |
| Under / ligue-1 | 17 | 17 | 0 | 7-10-0 | -1.65u | -9.73% | +2.14% (n=17) |
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
