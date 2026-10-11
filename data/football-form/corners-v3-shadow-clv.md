# Corners CLV Monitor: `corners_v3`

Generated: 2026-10-11T14:58:12Z
Picks input: `data/football-form/corners-v3-shadow-signals.csv`
Pinnacle input: `data/corners-ou/pinnacle-corners-odds.csv`

## Summary

- Picks: 97
- Active published picks: 97
- Settled: 79
- Open/pending: 18
- Settled PnL: -4.11u
- Picks with close: 97
- True-close coverage (<=120m): 51/94 (54.3%)
- Average true-close CLV: +0.80% (n=51)
- Hard-guard blocked: 0
- Average published-to-close CLV: +1.15%
- Allowed-league config valid: yes
- Allowed leagues: `bundesliga, epl, la-liga, ligue-1, serie-a`
- Config error: `-`

## Active Side Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over | 22 | 17 | 5 | 8-9-0 | -1.63u | -9.60% | -0.36% (n=17) |
| Under | 75 | 62 | 13 | 28-34-0 | -2.48u | -4.00% | +1.65% (n=62) |

## Active League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| bundesliga | 13 | 10 | 3 | 2-8-0 | -5.18u | -51.80% | -0.17% (n=10) |
| epl | 13 | 11 | 2 | 6-5-0 | +1.29u | +11.69% | +3.07% (n=11) |
| la-liga | 21 | 18 | 3 | 12-6-0 | +7.44u | +41.33% | +2.07% (n=18) |
| ligue-1 | 30 | 24 | 6 | 7-17-0 | -8.65u | -36.06% | +2.01% (n=24) |
| serie-a | 20 | 16 | 4 | 9-7-0 | +1.00u | +6.24% | -1.32% (n=16) |

## Active Side x League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over / epl | 1 | 0 | 1 | 0-0-0 | +0.00u | - | - (n=0) |
| Over / la-liga | 6 | 6 | 0 | 1-5-0 | -4.00u | -66.67% | +2.76% (n=6) |
| Over / ligue-1 | 2 | 1 | 1 | 0-1-0 | -1.00u | -100.00% | +0.00% (n=1) |
| Over / serie-a | 13 | 10 | 3 | 7-3-0 | +3.37u | +33.68% | -2.27% (n=10) |
| Under / bundesliga | 13 | 10 | 3 | 2-8-0 | -5.18u | -51.80% | -0.17% (n=10) |
| Under / epl | 12 | 11 | 1 | 6-5-0 | +1.29u | +11.69% | +3.07% (n=11) |
| Under / la-liga | 15 | 12 | 3 | 11-1-0 | +11.44u | +95.33% | +1.72% (n=12) |
| Under / ligue-1 | 28 | 23 | 5 | 7-16-0 | -7.65u | -33.28% | +2.10% (n=23) |
| Under / serie-a | 7 | 6 | 1 | 2-4-0 | -2.37u | -39.48% | +0.25% (n=6) |

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
