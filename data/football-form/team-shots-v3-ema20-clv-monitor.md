# Team-Shots CLV Monitor: `canonical_form_v3_ema20_nb`

Generated: 2026-06-09T20:53:19Z
Picks input: `data/football-form/team-shots-v3-ema20-published-picks.csv`
Odds input: `data/team-shots/team-shots-odds-history.csv`

## Summary

- Picks: 72
- Active published picks: 68
- Settled: 72
- Open/pending: 0
- Settled PnL: +10.93u
- Picks with close: 72
- Hard-guard blocked: 4
- Average published-to-close CLV: +0.35%
- Allowed-league config valid: yes
- Allowed leagues: `bundesliga, epl, la-liga, ligue-1, serie-a`
- Config error: `-`

## Active Side Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over | 23 | 23 | 0 | 11-12-0 | -2.75u | -11.97% | +0.40% (n=23) |
| Under | 45 | 45 | 0 | 30-15-0 | +10.15u | +22.56% | +0.00% (n=45) |

## Active League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| bundesliga | 11 | 11 | 0 | 5-6-0 | -2.19u | -19.87% | +0.00% (n=11) |
| epl | 14 | 14 | 0 | 8-6-0 | +0.56u | +4.02% | +0.00% (n=14) |
| la-liga | 17 | 17 | 0 | 12-5-0 | +5.72u | +33.65% | +0.54% (n=17) |
| serie-a | 26 | 26 | 0 | 16-10-0 | +3.30u | +12.70% | +0.00% (n=26) |

## Active Side x League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over / bundesliga | 6 | 6 | 0 | 4-2-0 | +0.98u | +16.35% | +0.00% (n=6) |
| Over / epl | 3 | 3 | 0 | 1-2-0 | -1.00u | -33.33% | +0.00% (n=3) |
| Over / la-liga | 5 | 5 | 0 | 3-2-0 | +0.80u | +16.00% | +1.82% (n=5) |
| Over / serie-a | 9 | 9 | 0 | 3-6-0 | -3.53u | -39.27% | +0.00% (n=9) |
| Under / bundesliga | 5 | 5 | 0 | 1-4-0 | -3.17u | -63.34% | +0.00% (n=5) |
| Under / epl | 11 | 11 | 0 | 7-4-0 | +1.56u | +14.21% | +0.00% (n=11) |
| Under / la-liga | 12 | 12 | 0 | 9-3-0 | +4.92u | +41.00% | +0.00% (n=12) |
| Under / serie-a | 17 | 17 | 0 | 13-4-0 | +6.84u | +40.22% | +0.00% (n=17) |

## Required Fields

- `current_model_would_have_priced` must be true while canonical-only evidence is blocked.
- `time_to_kickoff_hours` records publication timing so CLV can be interpreted by lead time.
- `published_to_close_clv` tracks the captured bookmaker price versus close.
- `model_to_close_clv` tracks the model-implied probability versus close.
- `confidence_guard_applied=true` means the row must not be treated as a published pick.

## De-Promotion Rules

- Pause `canonical_form_v3_ema20_nb` if 30-day rolling CLV is below 0 with at least 50 settled picks.
- Pause `canonical_form_v3_ema20_nb` if rolling 90-day production Brier exceeds 1.05x the pre-promotion backtest Brier.
