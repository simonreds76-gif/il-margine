# Corners CLV Monitor: `corners_v3`

Generated: 2026-11-25T18:43:39Z
Picks input: `data/football-form/corners-v3-shadow-signals.csv`
Pinnacle input: `data/corners-ou/pinnacle-corners-odds.csv`

## Summary

- Picks: 276
- Active published picks: 276
- Settled: 261
- Open/pending: 15
- Settled PnL: -23.66u
- Picks with close: 164
- True-close coverage (<=120m): 88/262 (33.6%)
- Average true-close CLV: +1.20% (n=88)
- Hard-guard blocked: 0
- Average published-to-close CLV: +1.48%
- Allowed-league config valid: yes
- Allowed leagues: `bundesliga, epl, la-liga, ligue-1, serie-a`
- Config error: `-`

## Active Side Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over | 60 | 59 | 1 | 19-40-0 | -7.38u | -12.51% | +0.71% (n=31) |
| Under | 216 | 202 | 14 | 86-116-0 | -16.28u | -8.06% | +1.64% (n=132) |

## Active League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| bundesliga | 42 | 39 | 3 | 15-24-0 | -4.57u | -11.73% | +0.93% (n=23) |
| epl | 48 | 44 | 4 | 15-29-0 | -11.65u | -26.47% | +1.10% (n=24) |
| la-liga | 62 | 58 | 4 | 22-36-0 | -4.81u | -8.29% | +2.32% (n=34) |
| ligue-1 | 62 | 61 | 1 | 30-31-0 | +0.74u | +1.22% | +2.10% (n=47) |
| serie-a | 62 | 59 | 3 | 23-36-0 | -3.37u | -5.72% | +0.38% (n=35) |

## Active Side x League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over / epl | 9 | 9 | 0 | 1-8-0 | -7.02u | -78.00% | -1.28% (n=3) |
| Over / la-liga | 12 | 12 | 0 | 2-10-0 | -3.50u | -29.17% | +2.76% (n=6) |
| Over / ligue-1 | 4 | 4 | 0 | 1-3-0 | -2.17u | -54.35% | +0.18% (n=2) |
| Over / serie-a | 35 | 34 | 1 | 15-19-0 | +5.31u | +15.63% | +0.45% (n=20) |
| Under / bundesliga | 42 | 39 | 3 | 15-24-0 | -4.57u | -11.73% | +0.93% (n=23) |
| Under / epl | 39 | 35 | 4 | 14-21-0 | -4.63u | -13.22% | +1.44% (n=21) |
| Under / la-liga | 50 | 46 | 4 | 20-26-0 | -1.31u | -2.85% | +2.22% (n=28) |
| Under / ligue-1 | 58 | 57 | 1 | 29-28-0 | +2.92u | +5.12% | +2.19% (n=45) |
| Under / serie-a | 27 | 25 | 2 | 8-17-0 | -8.69u | -34.75% | +0.30% (n=15) |

## Required Fields

- `current_model_would_have_priced` must be true for publication while canonical-only evidence is below threshold.
- `time_to_kickoff_hours` records publication timing so CLV can be interpreted by lead time.
- `published_to_close_clv` compares the original recorded bookmaker price with the Pinnacle close; the execution bookmaker and price are stored separately.
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
