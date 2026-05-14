# Corners V0 CLV Monitor

Generated: 2026-05-14T20:26:37Z
Picks input: `data/football-form/corners-v0-published-picks.csv`
Pinnacle input: `data/corners-ou/pinnacle-corners-odds.csv`

## Summary

- Picks: 40
- Active published picks: 40
- Settled: 35
- Open/pending: 5
- Settled PnL: -0.22u
- Picks with close: 40
- Hard-guard blocked: 0
- Average published-to-close CLV: +0.51%
- Allowed-league config valid: yes
- Allowed leagues: `epl, ligue-1, serie-a`
- Config error: `-`

## Active Side Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over | 24 | 19 | 5 | 10-9-0 | +2.03u | +10.68% | -0.18% (n=19) |
| Under | 16 | 16 | 0 | 7-9-0 | -2.25u | -14.07% | +1.46% (n=16) |

## Active League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| epl | 6 | 6 | 0 | 1-5-0 | -3.95u | -65.83% | +0.99% (n=6) |
| ligue-1 | 18 | 14 | 4 | 8-6-0 | +3.24u | +23.13% | -0.25% (n=14) |
| serie-a | 16 | 15 | 1 | 8-7-0 | +0.49u | +3.27% | +1.16% (n=15) |

## Active Side x League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over / epl | 4 | 4 | 0 | 1-3-0 | -1.95u | -48.75% | +0.00% (n=4) |
| Over / ligue-1 | 16 | 12 | 4 | 8-4-0 | +5.24u | +43.65% | -0.29% (n=12) |
| Over / serie-a | 4 | 3 | 1 | 1-2-0 | -1.26u | -41.97% | +0.00% (n=3) |
| Under / epl | 2 | 2 | 0 | 0-2-0 | -2.00u | -100.00% | +2.97% (n=2) |
| Under / ligue-1 | 2 | 2 | 0 | 0-2-0 | -2.00u | -100.00% | +0.00% (n=2) |
| Under / serie-a | 12 | 12 | 0 | 7-5-0 | +1.75u | +14.57% | +1.45% (n=12) |

## Required Fields

- `current_model_would_have_priced` must be true for publication while canonical-only evidence is below threshold.
- `time_to_kickoff_hours` records publication timing so CLV can be interpreted by lead time.
- `published_to_close_clv` tracks the taken/published Pinnacle price versus close.
- `model_to_close_clv` tracks the model-implied probability versus close.
- `confidence_guard_applied=true` means the row must not be treated as a published pick.

## De-Promotion Rules

- Pause corners v0 if 30-day rolling CLV is below 0 with at least 50 settled picks.
- Pause corners v0 if rolling 90-day production Brier exceeds 1.05x the pre-promotion backtest Brier.

## Re-Promotion Rules After A Pause

- Re-run the original full-window and last-90 Brier/log-loss gates.
- Document the specific cause of the pause: negative CLV drift or Brier calibration drift.
- Ship a documented data/model/scope change before re-enabling; do not simply re-enable because variance looks nicer.
- Wait at least 14 days after the pause before attempting re-promotion.
