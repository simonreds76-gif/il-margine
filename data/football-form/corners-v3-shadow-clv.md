# Corners CLV Monitor: `corners_v3`

Generated: 2026-11-03T16:32:39Z
Picks input: `data/football-form/corners-v3-shadow-signals.csv`
Pinnacle input: `data/corners-ou/pinnacle-corners-odds.csv`

## Summary

- Picks: 209
- Active published picks: 209
- Settled: 182
- Open/pending: 27
- Settled PnL: -16.83u
- Picks with close: 164
- True-close coverage (<=120m): 88/187 (47.1%)
- Average true-close CLV: +1.20% (n=88)
- Hard-guard blocked: 0
- Average published-to-close CLV: +1.48%
- Allowed-league config valid: yes
- Allowed leagues: `bundesliga, epl, la-liga, ligue-1, serie-a`
- Config error: `-`

## Active Side Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over | 44 | 42 | 2 | 15-27-0 | -9.43u | -22.45% | +0.71% (n=31) |
| Under | 165 | 140 | 25 | 64-76-0 | -7.40u | -5.29% | +1.65% (n=131) |

## Active League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| bundesliga | 31 | 27 | 4 | 8-19-0 | -10.33u | -38.27% | +0.93% (n=23) |
| epl | 34 | 26 | 8 | 10-16-0 | -5.54u | -21.30% | +1.15% (n=23) |
| la-liga | 48 | 39 | 9 | 18-21-0 | -1.04u | -2.67% | +2.32% (n=34) |
| ligue-1 | 49 | 48 | 1 | 25-23-0 | +3.36u | +7.00% | +2.10% (n=47) |
| serie-a | 47 | 42 | 5 | 18-24-0 | -3.28u | -7.81% | +0.38% (n=35) |

## Active Side x League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over / epl | 6 | 6 | 0 | 1-5-0 | -4.02u | -67.00% | -1.28% (n=3) |
| Over / la-liga | 9 | 8 | 1 | 1-7-0 | -6.00u | -75.00% | +2.76% (n=6) |
| Over / ligue-1 | 2 | 2 | 0 | 1-1-0 | -0.17u | -8.70% | +0.18% (n=2) |
| Over / serie-a | 27 | 26 | 1 | 12-14-0 | +0.76u | +2.94% | +0.45% (n=20) |
| Under / bundesliga | 31 | 27 | 4 | 8-19-0 | -10.33u | -38.27% | +0.93% (n=23) |
| Under / epl | 28 | 20 | 8 | 9-11-0 | -1.52u | -7.59% | +1.51% (n=20) |
| Under / la-liga | 39 | 31 | 8 | 17-14-0 | +4.96u | +16.00% | +2.22% (n=28) |
| Under / ligue-1 | 47 | 46 | 1 | 24-22-0 | +3.54u | +7.68% | +2.19% (n=45) |
| Under / serie-a | 20 | 16 | 4 | 6-10-0 | -4.05u | -25.29% | +0.30% (n=15) |

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
