# Shots-on-Target Definition Agreement

Generated: 2026-07-14T18:36:08Z

Football-Data HST/AST is compared with independently fetched FotMob full-time `ShotsOnTarget`.
The existing `all-understat-matches.csv` is deliberately not used as an independent source: its SOT fields are copied from Football-Data and Understat supplies only xG.

## Decision

- Definition gate: WAIT/FAIL
- Provider-grade sample (>=200 matched fixtures): incomplete
- Matched fixtures: 57/79 (72.2%)
- Exact team-count agreement: 106/112 (94.6%)
- Within one SOT: 108/112 (96.4%)
- Mean absolute delta: 0.125

The definition gate requires at least 100 matched team rows and >=97% agreement within one SOT. Model development may continue after that gate, but promotion still requires the 200-fixture provider-grade sample.

## League Breakdown

| League | Fixtures | Team rows | Exact | Within one | MAE |
|---|---:|---:|---:|---:|---:|
| epl | 10 | 19 | 78.9% | 78.9% | 0.632 |
| serie-a | 8 | 16 | 100.0% | 100.0% | 0.000 |
| la-liga | 12 | 23 | 100.0% | 100.0% | 0.000 |
| bundesliga | 13 | 26 | 96.2% | 100.0% | 0.038 |
| ligue-1 | 14 | 28 | 96.4% | 100.0% | 0.036 |

## Material Discrepancies

Rows differing by more than one SOT fail closed and require a third-source check before this market can be settled automatically.

| Date | League | Fixture | Side | Football-Data | FotMob | Delta |
|---|---|---|---|---:|---:|---:|
| 2026-05-24 | epl | Sunderland vs Chelsea | home | 2 | 6 | +4 |
| 2026-05-24 | epl | Tottenham vs Everton | home | 6 | 2 | -4 |
| 2026-05-24 | epl | Sunderland vs Chelsea | away | 1 | 3 | +2 |
| 2026-05-24 | epl | Tottenham vs Everton | away | 3 | 1 | -2 |
