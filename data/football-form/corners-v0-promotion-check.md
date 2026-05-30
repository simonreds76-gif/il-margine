# Corners V0 Promotion Check

Generated: 2026-05-30T14:06:15+00:00

This is a research-lane gate only. It does not change live picks.

Research lane ready across all leagues with hard canonical-only cutoff: **no**
Research lane ready for passing leagues only: **no**
Passing leagues: `-`
Blocked leagues: `bundesliga, epl, la-liga, ligue-1, serie-a`

## Real-Odds Gate

- Source: `data/corners-ou/corners-real-odds-backtest-results.csv`
- Model: `nb_market_blend`
- Selected fresh-close bets: `90` / required `200`
- ROI: `-6.64%` / required `>= 0.00%`
- Mean CLV: `1.14%` / required `>= 1.00%`
- Positive CLV share: `54.4%` / required `>= 55.0%`
- Qualified positive leagues: `-` / required `3`
- Overall pass: **no**
- Reason: real-odds CLV gate failed; corners remains research-only

## Per-League Count/Calibration Gates

| League | Common N | Current MAE | V0 MAE | Count | Brier | Log-loss | Last90 N | Last90 Current MAE | Last90 V0 MAE | Last90 Count | Last90 Brier | Last90 Log-loss |
| --- | ---: | ---: | ---: | --- | --- | --- | ---: | ---: | ---: | --- | --- | --- |
| bundesliga | 3546 | 2.7983 | 2.7591 | PASS | PASS | PASS | 100 | 2.8539 | 2.9486 | FAIL | FAIL | FAIL |
| epl | 4411 | 2.8668 | 2.8275 | PASS | PASS | PASS | 110 | 2.9214 | 2.7639 | PASS | PASS | PASS |
| la-liga | 4429 | 2.6806 | 2.6408 | PASS | PASS | PASS | 132 | 2.8464 | 2.8838 | FAIL | FAIL | FAIL |
| ligue-1 | 4095 | 2.7458 | 2.6851 | PASS | PASS | PASS | 98 | 3.0791 | 2.9024 | PASS | PASS | PASS |
| serie-a | 4405 | 2.8549 | 2.8418 | PASS | PASS | PASS | 122 | 2.7327 | 2.7206 | PASS | PASS | PASS |

## Canonical-Only Guard

- Canonical-only sample size: `2`
- Hard block active: `yes`
- Reason: canonical-only N=2 < 200; do not publish picks where current model was historically silent

## Publication Rule

- Allow corners v0 into research lane only for fixtures where the current model would also have priced the fixture.
- Restrict initial research-lane publication to passing leagues only.
- Keep canonical-only fixtures blocked until N >= 200 and segment calibration is stable.
- Keep all corners publication blocked unless the real Pinnacle odds gate passes.
- CLV monitoring must log `current_model_would_have_priced` so live results can keep common vs extended-coverage bets separate.
- Allowed-league config written to `data\football-form\corners-v0-allowed-leagues.json`.
