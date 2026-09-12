# Corners CLV Monitor: `corners_v3`

Generated: 2026-09-12T18:39:09Z
Picks input: `data\football-form\corners-v3-shadow-signals.csv`
Pinnacle input: `data\corners-ou\pinnacle-corners-odds.csv`

## Summary

- Picks: 53
- Active published picks: 53
- Settled: 40
- Open/pending: 13
- Settled PnL: +0.02u
- Picks with close: 53
- True-close coverage (<=120m): 15/45 (33.3%)
- Average true-close CLV: +2.73% (n=15)
- Hard-guard blocked: 0
- Average published-to-close CLV: +2.14%
- Allowed-league config valid: yes
- Allowed leagues: `bundesliga, epl, la-liga, ligue-1, serie-a`
- Config error: `-`

## Active Side Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over | 14 | 11 | 3 | 5-6-0 | -1.03u | -9.34% | -0.74% (n=11) |
| Under | 39 | 29 | 10 | 14-15-0 | +1.05u | +3.62% | +3.48% (n=29) |

## Active League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| bundesliga | 5 | 3 | 2 | 0-3-0 | -3.00u | -100.00% | +0.48% (n=3) |
| epl | 7 | 5 | 2 | 4-1-0 | +3.11u | +62.20% | +3.10% (n=5) |
| la-liga | 11 | 9 | 2 | 6-3-0 | +4.16u | +46.22% | +5.29% (n=9) |
| ligue-1 | 18 | 13 | 5 | 4-9-0 | -4.01u | -30.82% | +3.16% (n=13) |
| serie-a | 12 | 10 | 2 | 5-5-0 | -0.24u | -2.40% | -1.31% (n=10) |

## Active Side x League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over / la-liga | 5 | 3 | 2 | 1-2-0 | -1.00u | -33.33% | +2.11% (n=3) |
| Over / ligue-1 | 1 | 1 | 0 | 0-1-0 | -1.00u | -100.00% | +0.00% (n=1) |
| Over / serie-a | 8 | 7 | 1 | 4-3-0 | +0.97u | +13.90% | -2.08% (n=7) |
| Under / bundesliga | 5 | 3 | 2 | 0-3-0 | -3.00u | -100.00% | +0.48% (n=3) |
| Under / epl | 7 | 5 | 2 | 4-1-0 | +3.11u | +62.20% | +3.10% (n=5) |
| Under / la-liga | 6 | 6 | 0 | 5-1-0 | +5.16u | +86.00% | +6.88% (n=6) |
| Under / ligue-1 | 17 | 12 | 5 | 4-8-0 | -3.01u | -25.06% | +3.43% (n=12) |
| Under / serie-a | 4 | 3 | 1 | 1-2-0 | -1.21u | -40.43% | +0.49% (n=3) |

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
