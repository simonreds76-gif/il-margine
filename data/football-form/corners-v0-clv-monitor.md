# Corners V0 CLV Monitor

Generated: 2026-05-23T09:46:39Z
Picks input: `data/football-form/corners-v0-published-picks.csv`
Pinnacle input: `data/corners-ou/pinnacle-corners-odds.csv`

## Summary

- Picks: 46
- Active published picks: 46
- Settled: 43
- Open/pending: 3
- Settled PnL: +2.05u
- Picks with close: 46
- Hard-guard blocked: 0
- Average published-to-close CLV: +0.42%
- Allowed-league config valid: yes
- Allowed leagues: `epl, ligue-1, serie-a`
- Config error: `-`

## Active Side Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over | 30 | 27 | 3 | 15-12-0 | +4.30u | +15.92% | -0.09% (n=27) |
| Under | 16 | 16 | 0 | 7-9-0 | -2.25u | -14.07% | +1.46% (n=16) |

## Active League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| epl | 10 | 8 | 2 | 2-6-0 | -3.96u | -49.50% | +0.74% (n=8) |
| ligue-1 | 19 | 19 | 0 | 12-7-0 | +6.52u | +34.30% | -0.16% (n=19) |
| serie-a | 17 | 16 | 1 | 8-8-0 | -0.51u | -3.19% | +1.12% (n=16) |

## Active Side x League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over / epl | 8 | 6 | 2 | 2-4-0 | -1.96u | -32.67% | +0.00% (n=6) |
| Over / ligue-1 | 17 | 17 | 0 | 12-5-0 | +8.52u | +50.10% | -0.18% (n=17) |
| Over / serie-a | 5 | 4 | 1 | 1-3-0 | -2.26u | -56.47% | +0.12% (n=4) |
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
