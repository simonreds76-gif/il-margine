# Team-Shots CLV Monitor: `canonical_form_v3_ema20_nb`

Generated: 2026-05-18T20:23:31Z
Picks input: `data/football-form/team-shots-v3-ema20-published-picks.csv`
Odds input: `data/team-shots/team-shots-odds-history.csv`

## Summary

- Picks: 60
- Active published picks: 56
- Settled: 59
- Open/pending: 1
- Settled PnL: +5.19u
- Picks with close: 60
- Hard-guard blocked: 4
- Average published-to-close CLV: +0.42%
- Allowed-league config valid: yes
- Allowed leagues: `bundesliga, epl, la-liga, ligue-1, serie-a`
- Config error: `-`

## Active Side Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over | 22 | 22 | 0 | 10-12-0 | -3.59u | -16.30% | +0.41% (n=22) |
| Under | 34 | 33 | 1 | 21-12-0 | +5.25u | +15.90% | +0.00% (n=33) |

## Active League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| bundesliga | 11 | 11 | 0 | 5-6-0 | -2.19u | -19.87% | +0.00% (n=11) |
| epl | 11 | 10 | 1 | 6-4-0 | +0.85u | +8.54% | +0.00% (n=10) |
| la-liga | 13 | 13 | 0 | 8-5-0 | +2.34u | +18.02% | +0.70% (n=13) |
| serie-a | 21 | 21 | 0 | 12-9-0 | +0.65u | +3.10% | +0.00% (n=21) |

## Active Side x League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over / bundesliga | 6 | 6 | 0 | 4-2-0 | +0.98u | +16.35% | +0.00% (n=6) |
| Over / epl | 3 | 3 | 0 | 1-2-0 | -1.00u | -33.33% | +0.00% (n=3) |
| Over / la-liga | 5 | 5 | 0 | 3-2-0 | +0.80u | +16.00% | +1.82% (n=5) |
| Over / serie-a | 8 | 8 | 0 | 2-6-0 | -4.37u | -54.59% | +0.00% (n=8) |
| Under / bundesliga | 5 | 5 | 0 | 1-4-0 | -3.17u | -63.34% | +0.00% (n=5) |
| Under / epl | 8 | 7 | 1 | 5-2-0 | +1.85u | +26.49% | +0.00% (n=7) |
| Under / la-liga | 8 | 8 | 0 | 5-3-0 | +1.54u | +19.28% | +0.00% (n=8) |
| Under / serie-a | 13 | 13 | 0 | 10-3-0 | +5.02u | +38.61% | +0.00% (n=13) |

## Required Fields

- `current_model_would_have_priced` must be true while canonical-only evidence is blocked.
- `time_to_kickoff_hours` records publication timing so CLV can be interpreted by lead time.
- `published_to_close_clv` tracks the captured bookmaker price versus close.
- `model_to_close_clv` tracks the model-implied probability versus close.
- `confidence_guard_applied=true` means the row must not be treated as a published pick.

## De-Promotion Rules

- Pause `canonical_form_v3_ema20_nb` if 30-day rolling CLV is below 0 with at least 50 settled picks.
- Pause `canonical_form_v3_ema20_nb` if rolling 90-day production Brier exceeds 1.05x the pre-promotion backtest Brier.
