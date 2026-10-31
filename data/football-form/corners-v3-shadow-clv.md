# Corners CLV Monitor: `corners_v3`

Generated: 2026-10-31T14:36:32Z
Picks input: `data/football-form/corners-v3-shadow-signals.csv`
Pinnacle input: `data/corners-ou/pinnacle-corners-odds.csv`

## Summary

- Picks: 189
- Active published picks: 189
- Settled: 149
- Open/pending: 40
- Settled PnL: -9.77u
- Picks with close: 164
- True-close coverage (<=120m): 88/161 (54.7%)
- Average true-close CLV: +1.20% (n=88)
- Hard-guard blocked: 0
- Average published-to-close CLV: +1.48%
- Allowed-league config valid: yes
- Allowed leagues: `bundesliga, epl, la-liga, ligue-1, serie-a`
- Config error: `-`

## Active Side Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over | 44 | 32 | 12 | 14-18-0 | -4.93u | -15.40% | +0.71% (n=31) |
| Under | 145 | 117 | 28 | 54-63-0 | -4.84u | -4.14% | +1.44% (n=117) |

## Active League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| bundesliga | 27 | 20 | 7 | 5-15-0 | -9.30u | -46.50% | +0.69% (n=20) |
| epl | 29 | 21 | 8 | 10-11-0 | -0.54u | -2.56% | +1.26% (n=21) |
| la-liga | 42 | 30 | 12 | 15-15-0 | +1.81u | +6.03% | +2.03% (n=30) |
| ligue-1 | 48 | 42 | 6 | 21-21-0 | +1.04u | +2.47% | +1.83% (n=42) |
| serie-a | 43 | 36 | 7 | 17-19-0 | -2.78u | -7.73% | +0.38% (n=35) |

## Active Side x League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over / epl | 6 | 3 | 3 | 1-2-0 | -1.02u | -34.00% | -1.28% (n=3) |
| Over / la-liga | 9 | 6 | 3 | 1-5-0 | -4.00u | -66.67% | +2.76% (n=6) |
| Over / ligue-1 | 2 | 2 | 0 | 1-1-0 | -0.17u | -8.70% | +0.18% (n=2) |
| Over / serie-a | 27 | 21 | 6 | 11-10-0 | +0.26u | +1.26% | +0.45% (n=20) |
| Under / bundesliga | 27 | 20 | 7 | 5-15-0 | -9.30u | -46.50% | +0.69% (n=20) |
| Under / epl | 23 | 18 | 5 | 9-9-0 | +0.48u | +2.68% | +1.68% (n=18) |
| Under / la-liga | 33 | 24 | 9 | 14-10-0 | +5.81u | +24.21% | +1.84% (n=24) |
| Under / ligue-1 | 46 | 40 | 6 | 20-20-0 | +1.21u | +3.03% | +1.91% (n=40) |
| Under / serie-a | 16 | 15 | 1 | 6-9-0 | -3.05u | -20.31% | +0.30% (n=15) |

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
