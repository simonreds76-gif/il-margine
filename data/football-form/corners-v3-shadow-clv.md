# Corners CLV Monitor: `corners_v3`

Generated: 2026-10-13T16:05:22Z
Picks input: `data/football-form/corners-v3-shadow-signals.csv`
Pinnacle input: `data/corners-ou/pinnacle-corners-odds.csv`

## Summary

- Picks: 98
- Active published picks: 98
- Settled: 97
- Open/pending: 1
- Settled PnL: -6.36u
- Picks with close: 98
- True-close coverage (<=120m): 55/98 (56.1%)
- Average true-close CLV: +1.00% (n=55)
- Hard-guard blocked: 0
- Average published-to-close CLV: +1.15%
- Allowed-league config valid: yes
- Allowed leagues: `bundesliga, epl, la-liga, ligue-1, serie-a`
- Config error: `-`

## Active Side Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over | 23 | 22 | 1 | 11-11-0 | -0.68u | -3.07% | +0.58% (n=22) |
| Under | 75 | 75 | 0 | 33-42-0 | -5.69u | -7.58% | +1.30% (n=75) |

## Active League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| bundesliga | 13 | 13 | 0 | 2-11-0 | -8.18u | -62.92% | -0.27% (n=13) |
| epl | 13 | 13 | 0 | 8-5-0 | +3.19u | +24.55% | +2.53% (n=13) |
| la-liga | 21 | 21 | 0 | 12-9-0 | +4.44u | +21.14% | +1.53% (n=21) |
| ligue-1 | 30 | 30 | 0 | 12-18-0 | -4.96u | -16.55% | +1.65% (n=30) |
| serie-a | 21 | 20 | 1 | 10-10-0 | -0.85u | -4.26% | -0.04% (n=20) |

## Active Side x League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over / epl | 1 | 1 | 0 | 1-0-0 | +0.98u | +98.00% | +0.00% (n=1) |
| Over / la-liga | 6 | 6 | 0 | 1-5-0 | -4.00u | -66.67% | +2.76% (n=6) |
| Over / ligue-1 | 2 | 2 | 0 | 1-1-0 | -0.17u | -8.70% | +0.18% (n=2) |
| Over / serie-a | 14 | 13 | 1 | 8-5-0 | +2.52u | +19.37% | -0.32% (n=13) |
| Under / bundesliga | 13 | 13 | 0 | 2-11-0 | -8.18u | -62.92% | -0.27% (n=13) |
| Under / epl | 12 | 12 | 0 | 7-5-0 | +2.21u | +18.43% | +2.74% (n=12) |
| Under / la-liga | 15 | 15 | 0 | 11-4-0 | +8.44u | +56.27% | +1.05% (n=15) |
| Under / ligue-1 | 28 | 28 | 0 | 11-17-0 | -4.79u | -17.11% | +1.75% (n=28) |
| Under / serie-a | 7 | 7 | 0 | 2-5-0 | -3.37u | -48.13% | +0.48% (n=7) |

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
