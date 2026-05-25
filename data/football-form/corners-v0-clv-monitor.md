# Corners V0 CLV Monitor

Generated: 2026-05-25T12:00:46Z
Picks input: `data/football-form/corners-v0-published-picks.csv`
Pinnacle input: `data/corners-ou/pinnacle-corners-odds.csv`

## Summary

- Picks: 48
- Active published picks: 48
- Settled: 48
- Open/pending: 0
- Settled PnL: -1.12u
- Picks with close: 48
- Hard-guard blocked: 0
- Average published-to-close CLV: +0.40%
- Allowed-league config valid: yes
- Allowed leagues: `epl, ligue-1, serie-a`
- Config error: `-`

## Active Side Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over | 32 | 32 | 0 | 16-16-0 | +1.13u | +3.53% | -0.13% (n=32) |
| Under | 16 | 16 | 0 | 7-9-0 | -2.25u | -14.07% | +1.46% (n=16) |

## Active League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| epl | 11 | 11 | 0 | 3-8-0 | -5.13u | -46.61% | +0.40% (n=11) |
| ligue-1 | 19 | 19 | 0 | 12-7-0 | +6.52u | +34.30% | -0.16% (n=19) |
| serie-a | 18 | 18 | 0 | 8-10-0 | -2.51u | -13.94% | +1.00% (n=18) |

## Active Side x League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over / epl | 9 | 9 | 0 | 3-6-0 | -3.13u | -34.74% | -0.17% (n=9) |
| Over / ligue-1 | 17 | 17 | 0 | 12-5-0 | +8.52u | +50.10% | -0.18% (n=17) |
| Over / serie-a | 6 | 6 | 0 | 1-5-0 | -4.26u | -70.98% | +0.08% (n=6) |
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
