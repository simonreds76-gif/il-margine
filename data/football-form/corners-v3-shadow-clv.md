# Corners CLV Monitor: `corners_v3`

Generated: 2026-11-08T15:20:08Z
Picks input: `data/football-form/corners-v3-shadow-signals.csv`
Pinnacle input: `data/corners-ou/pinnacle-corners-odds.csv`

## Summary

- Picks: 228
- Active published picks: 228
- Settled: 190
- Open/pending: 38
- Settled PnL: -16.31u
- Picks with close: 164
- True-close coverage (<=120m): 88/219 (40.2%)
- Average true-close CLV: +1.20% (n=88)
- Hard-guard blocked: 0
- Average published-to-close CLV: +1.48%
- Allowed-league config valid: yes
- Allowed leagues: `bundesliga, epl, la-liga, ligue-1, serie-a`
- Config error: `-`

## Active Side Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over | 53 | 44 | 9 | 15-29-0 | -11.43u | -25.97% | +0.71% (n=31) |
| Under | 175 | 146 | 29 | 68-78-0 | -4.88u | -3.34% | +1.64% (n=132) |

## Active League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| bundesliga | 33 | 28 | 5 | 9-19-0 | -9.36u | -33.44% | +0.93% (n=23) |
| epl | 35 | 28 | 7 | 12-16-0 | -3.15u | -11.24% | +1.10% (n=24) |
| la-liga | 50 | 41 | 9 | 18-23-0 | -3.04u | -7.41% | +2.32% (n=34) |
| ligue-1 | 56 | 48 | 8 | 25-23-0 | +3.36u | +7.00% | +2.10% (n=47) |
| serie-a | 54 | 45 | 9 | 19-26-0 | -4.12u | -9.16% | +0.38% (n=35) |

## Active Side x League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over / epl | 7 | 6 | 1 | 1-5-0 | -4.02u | -67.00% | -1.28% (n=3) |
| Over / la-liga | 10 | 9 | 1 | 1-8-0 | -7.00u | -77.78% | +2.76% (n=6) |
| Over / ligue-1 | 3 | 2 | 1 | 1-1-0 | -0.17u | -8.70% | +0.18% (n=2) |
| Over / serie-a | 33 | 27 | 6 | 12-15-0 | -0.24u | -0.87% | +0.45% (n=20) |
| Under / bundesliga | 33 | 28 | 5 | 9-19-0 | -9.36u | -33.44% | +0.93% (n=23) |
| Under / epl | 28 | 22 | 6 | 11-11-0 | +0.87u | +3.96% | +1.44% (n=21) |
| Under / la-liga | 40 | 32 | 8 | 17-15-0 | +3.96u | +12.37% | +2.22% (n=28) |
| Under / ligue-1 | 53 | 46 | 7 | 24-22-0 | +3.54u | +7.68% | +2.19% (n=45) |
| Under / serie-a | 21 | 18 | 3 | 7-11-0 | -3.89u | -21.59% | +0.30% (n=15) |

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
