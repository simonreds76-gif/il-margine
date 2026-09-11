# Corners CLV Monitor: `corners_v3`

Generated: 2026-09-11T14:03:33Z
Picks input: `data/football-form/corners-v3-shadow-signals.csv`
Pinnacle input: `data/corners-ou/pinnacle-corners-odds.csv`

## Summary

- Picks: 50
- Active published picks: 50
- Settled: 36
- Open/pending: 14
- Settled PnL: -2.24u
- Picks with close: 50
- True-close coverage (<=120m): 15/37 (40.5%)
- Average true-close CLV: +2.73% (n=15)
- Hard-guard blocked: 0
- Average published-to-close CLV: +2.27%
- Allowed-league config valid: yes
- Allowed leagues: `bundesliga, epl, la-liga, ligue-1, serie-a`
- Config error: `-`

## Active Side Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over | 14 | 8 | 6 | 3-5-0 | -2.19u | -27.34% | -1.02% (n=8) |
| Under | 36 | 28 | 8 | 13-15-0 | -0.05u | -0.18% | +3.60% (n=28) |

## Active League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| bundesliga | 4 | 3 | 1 | 0-3-0 | -3.00u | -100.00% | +0.48% (n=3) |
| epl | 6 | 5 | 1 | 4-1-0 | +3.11u | +62.20% | +3.10% (n=5) |
| la-liga | 11 | 8 | 3 | 5-3-0 | +3.16u | +39.50% | +5.95% (n=8) |
| ligue-1 | 17 | 12 | 5 | 3-9-0 | -5.11u | -42.56% | +3.43% (n=12) |
| serie-a | 12 | 8 | 4 | 4-4-0 | -0.40u | -5.00% | -1.63% (n=8) |

## Active Side x League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over / la-liga | 5 | 2 | 3 | 0-2-0 | -2.00u | -100.00% | +3.17% (n=2) |
| Over / ligue-1 | 1 | 1 | 0 | 0-1-0 | -1.00u | -100.00% | +0.00% (n=1) |
| Over / serie-a | 8 | 5 | 3 | 3-2-0 | +0.81u | +16.26% | -2.91% (n=5) |
| Under / bundesliga | 4 | 3 | 1 | 0-3-0 | -3.00u | -100.00% | +0.48% (n=3) |
| Under / epl | 6 | 5 | 1 | 4-1-0 | +3.11u | +62.20% | +3.10% (n=5) |
| Under / la-liga | 6 | 6 | 0 | 5-1-0 | +5.16u | +86.00% | +6.88% (n=6) |
| Under / ligue-1 | 16 | 11 | 5 | 3-8-0 | -4.11u | -37.34% | +3.74% (n=11) |
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
