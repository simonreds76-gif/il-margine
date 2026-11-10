# Corners CLV Monitor: `corners_v3`

Generated: 2026-11-10T17:35:08Z
Picks input: `data/football-form/corners-v3-shadow-signals.csv`
Pinnacle input: `data/corners-ou/pinnacle-corners-odds.csv`

## Summary

- Picks: 228
- Active published picks: 228
- Settled: 227
- Open/pending: 1
- Settled PnL: -10.22u
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
| Over | 53 | 53 | 0 | 18-35-0 | -3.63u | -6.85% | +0.71% (n=31) |
| Under | 175 | 174 | 1 | 79-95-0 | -6.59u | -3.79% | +1.64% (n=132) |

## Active League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| bundesliga | 33 | 33 | 0 | 12-21-0 | -7.10u | -21.52% | +0.93% (n=23) |
| epl | 35 | 35 | 0 | 14-21-0 | -5.85u | -16.71% | +1.10% (n=24) |
| la-liga | 50 | 50 | 0 | 22-28-0 | +3.19u | +6.38% | +2.32% (n=34) |
| ligue-1 | 56 | 55 | 1 | 28-27-0 | +2.36u | +4.29% | +2.10% (n=47) |
| serie-a | 54 | 54 | 0 | 21-33-0 | -2.82u | -5.23% | +0.38% (n=35) |

## Active Side x League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over / epl | 7 | 7 | 0 | 1-6-0 | -5.02u | -71.71% | -1.28% (n=3) |
| Over / la-liga | 10 | 10 | 0 | 2-8-0 | -1.50u | -15.00% | +2.76% (n=6) |
| Over / ligue-1 | 3 | 3 | 0 | 1-2-0 | -1.17u | -39.13% | +0.18% (n=2) |
| Over / serie-a | 33 | 33 | 0 | 14-19-0 | +4.06u | +12.32% | +0.45% (n=20) |
| Under / bundesliga | 33 | 33 | 0 | 12-21-0 | -7.10u | -21.52% | +0.93% (n=23) |
| Under / epl | 28 | 28 | 0 | 13-15-0 | -0.83u | -2.96% | +1.44% (n=21) |
| Under / la-liga | 40 | 40 | 0 | 20-20-0 | +4.69u | +11.72% | +2.22% (n=28) |
| Under / ligue-1 | 53 | 52 | 1 | 27-25-0 | +3.54u | +6.80% | +2.19% (n=45) |
| Under / serie-a | 21 | 21 | 0 | 7-14-0 | -6.89u | -32.80% | +0.30% (n=15) |

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
