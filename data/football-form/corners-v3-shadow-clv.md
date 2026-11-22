# Corners CLV Monitor: `corners_v3`

Generated: 2026-11-22T16:21:47Z
Picks input: `data/football-form/corners-v3-shadow-signals.csv`
Pinnacle input: `data/corners-ou/pinnacle-corners-odds.csv`

## Summary

- Picks: 270
- Active published picks: 270
- Settled: 229
- Open/pending: 41
- Settled PnL: -12.22u
- Picks with close: 164
- True-close coverage (<=120m): 88/256 (34.4%)
- Average true-close CLV: +1.20% (n=88)
- Hard-guard blocked: 0
- Average published-to-close CLV: +1.48%
- Allowed-league config valid: yes
- Allowed leagues: `bundesliga, epl, la-liga, ligue-1, serie-a`
- Config error: `-`

## Active Side Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over | 59 | 53 | 6 | 18-35-0 | -3.63u | -6.85% | +0.71% (n=31) |
| Under | 211 | 176 | 35 | 79-97-0 | -8.59u | -4.88% | +1.64% (n=132) |

## Active League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| bundesliga | 39 | 33 | 6 | 12-21-0 | -7.10u | -21.52% | +0.93% (n=23) |
| epl | 47 | 36 | 11 | 14-22-0 | -6.85u | -19.02% | +1.10% (n=24) |
| la-liga | 62 | 51 | 11 | 22-29-0 | +2.19u | +4.29% | +2.32% (n=34) |
| ligue-1 | 62 | 55 | 7 | 28-27-0 | +2.36u | +4.29% | +2.10% (n=47) |
| serie-a | 60 | 54 | 6 | 21-33-0 | -2.82u | -5.23% | +0.38% (n=35) |

## Active Side x League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over / epl | 9 | 7 | 2 | 1-6-0 | -5.02u | -71.71% | -1.28% (n=3) |
| Over / la-liga | 12 | 10 | 2 | 2-8-0 | -1.50u | -15.00% | +2.76% (n=6) |
| Over / ligue-1 | 4 | 3 | 1 | 1-2-0 | -1.17u | -39.13% | +0.18% (n=2) |
| Over / serie-a | 34 | 33 | 1 | 14-19-0 | +4.06u | +12.32% | +0.45% (n=20) |
| Under / bundesliga | 39 | 33 | 6 | 12-21-0 | -7.10u | -21.52% | +0.93% (n=23) |
| Under / epl | 38 | 29 | 9 | 13-16-0 | -1.83u | -6.30% | +1.44% (n=21) |
| Under / la-liga | 50 | 41 | 9 | 20-21-0 | +3.69u | +9.00% | +2.22% (n=28) |
| Under / ligue-1 | 58 | 52 | 6 | 27-25-0 | +3.54u | +6.80% | +2.19% (n=45) |
| Under / serie-a | 26 | 21 | 5 | 7-14-0 | -6.89u | -32.80% | +0.30% (n=15) |

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
