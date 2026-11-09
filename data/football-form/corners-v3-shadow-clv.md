# Corners CLV Monitor: `corners_v3`

Generated: 2026-11-09T18:53:14Z
Picks input: `data/football-form/corners-v3-shadow-signals.csv`
Pinnacle input: `data/corners-ou/pinnacle-corners-odds.csv`

## Summary

- Picks: 228
- Active published picks: 228
- Settled: 204
- Open/pending: 24
- Settled PnL: -12.15u
- Picks with close: 164
- True-close coverage (<=120m): 88/228 (38.6%)
- Average true-close CLV: +1.20% (n=88)
- Hard-guard blocked: 0
- Average published-to-close CLV: +1.48%
- Allowed-league config valid: yes
- Allowed leagues: `bundesliga, epl, la-liga, ligue-1, serie-a`
- Config error: `-`

## Active Side Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over | 53 | 47 | 6 | 16-31-0 | -9.63u | -20.49% | +0.71% (n=31) |
| Under | 175 | 157 | 18 | 73-84-0 | -2.52u | -1.61% | +1.64% (n=132) |

## Active League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| bundesliga | 33 | 30 | 3 | 11-19-0 | -5.83u | -19.43% | +0.93% (n=23) |
| epl | 35 | 31 | 4 | 13-18-0 | -3.60u | -11.61% | +1.10% (n=24) |
| la-liga | 50 | 45 | 5 | 20-25-0 | -1.76u | -3.91% | +2.32% (n=34) |
| ligue-1 | 56 | 49 | 7 | 25-24-0 | +2.36u | +4.82% | +2.10% (n=47) |
| serie-a | 54 | 49 | 5 | 20-29-0 | -3.32u | -6.78% | +0.38% (n=35) |

## Active Side x League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over / epl | 7 | 6 | 1 | 1-5-0 | -4.02u | -67.00% | -1.28% (n=3) |
| Over / la-liga | 10 | 9 | 1 | 1-8-0 | -7.00u | -77.78% | +2.76% (n=6) |
| Over / ligue-1 | 3 | 3 | 0 | 1-2-0 | -1.17u | -39.13% | +0.18% (n=2) |
| Over / serie-a | 33 | 29 | 4 | 13-16-0 | +2.56u | +8.84% | +0.45% (n=20) |
| Under / bundesliga | 33 | 30 | 3 | 11-19-0 | -5.83u | -19.43% | +0.93% (n=23) |
| Under / epl | 28 | 25 | 3 | 12-13-0 | +0.42u | +1.69% | +1.44% (n=21) |
| Under / la-liga | 40 | 36 | 4 | 19-17-0 | +5.24u | +14.56% | +2.22% (n=28) |
| Under / ligue-1 | 53 | 46 | 7 | 24-22-0 | +3.54u | +7.68% | +2.19% (n=45) |
| Under / serie-a | 21 | 20 | 1 | 7-13-0 | -5.89u | -29.43% | +0.30% (n=15) |

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
