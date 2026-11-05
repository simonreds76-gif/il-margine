# Corners CLV Monitor: `corners_v3`

Generated: 2026-11-05T16:32:40Z
Picks input: `data/football-form/corners-v3-shadow-signals.csv`
Pinnacle input: `data/corners-ou/pinnacle-corners-odds.csv`

## Summary

- Picks: 214
- Active published picks: 214
- Settled: 186
- Open/pending: 28
- Settled PnL: -16.40u
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
| Over | 47 | 44 | 3 | 15-29-0 | -11.43u | -25.97% | +0.71% (n=31) |
| Under | 167 | 142 | 25 | 66-76-0 | -4.97u | -3.50% | +1.64% (n=132) |

## Active League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| bundesliga | 32 | 27 | 5 | 8-19-0 | -10.33u | -38.27% | +0.93% (n=23) |
| epl | 34 | 27 | 7 | 11-16-0 | -4.27u | -15.81% | +1.10% (n=24) |
| la-liga | 48 | 40 | 8 | 18-22-0 | -2.04u | -5.10% | +2.32% (n=34) |
| ligue-1 | 49 | 48 | 1 | 25-23-0 | +3.36u | +7.00% | +2.10% (n=47) |
| serie-a | 51 | 44 | 7 | 19-25-0 | -3.12u | -7.10% | +0.38% (n=35) |

## Active Side x League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over / epl | 6 | 6 | 0 | 1-5-0 | -4.02u | -67.00% | -1.28% (n=3) |
| Over / la-liga | 9 | 9 | 0 | 1-8-0 | -7.00u | -77.78% | +2.76% (n=6) |
| Over / ligue-1 | 2 | 2 | 0 | 1-1-0 | -0.17u | -8.70% | +0.18% (n=2) |
| Over / serie-a | 30 | 27 | 3 | 12-15-0 | -0.24u | -0.87% | +0.45% (n=20) |
| Under / bundesliga | 32 | 27 | 5 | 8-19-0 | -10.33u | -38.27% | +0.93% (n=23) |
| Under / epl | 28 | 21 | 7 | 10-11-0 | -0.25u | -1.18% | +1.44% (n=21) |
| Under / la-liga | 39 | 31 | 8 | 17-14-0 | +4.96u | +16.00% | +2.22% (n=28) |
| Under / ligue-1 | 47 | 46 | 1 | 24-22-0 | +3.54u | +7.68% | +2.19% (n=45) |
| Under / serie-a | 21 | 17 | 4 | 7-10-0 | -2.89u | -16.98% | +0.30% (n=15) |

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
