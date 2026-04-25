# Corners V0 Promotion Check

Generated: 2026-04-25T14:43:22+00:00

This is a research-lane gate only. It does not change live picks.

Research lane ready across all leagues with hard canonical-only cutoff: **no**
Research lane ready for passing leagues only: **yes**
Passing leagues: `epl, ligue-1, serie-a`
Blocked leagues: `bundesliga, la-liga`

## Per-League Gates

| League | Common N | Current MAE | V0 MAE | Count | Brier | Log-loss | Last90 N | Last90 Current MAE | Last90 V0 MAE | Last90 Count | Last90 Brier | Last90 Log-loss |
| --- | ---: | ---: | ---: | --- | --- | --- | ---: | ---: | ---: | --- | --- | --- |
| bundesliga | 3510 | 2.7947 | 2.7547 | PASS | PASS | PASS | 111 | 2.5870 | 2.6594 | FAIL | FAIL | FAIL |
| epl | 4363 | 2.8648 | 2.8260 | PASS | PASS | PASS | 112 | 2.6609 | 2.5618 | PASS | PASS | PASS |
| la-liga | 4369 | 2.6803 | 2.6405 | PASS | PASS | PASS | 121 | 2.7026 | 2.7749 | FAIL | FAIL | FAIL |
| ligue-1 | 4058 | 2.7383 | 2.6776 | PASS | PASS | PASS | 106 | 2.6322 | 2.4323 | PASS | PASS | PASS |
| serie-a | 4355 | 2.8581 | 2.8434 | PASS | PASS | PASS | 120 | 2.7384 | 2.6993 | PASS | PASS | PASS |

## Canonical-Only Guard

- Canonical-only sample size: `2`
- Hard block active: `yes`
- Reason: canonical-only N=2 < 200; do not publish picks where current model was historically silent

## Publication Rule

- Allow corners v0 into research lane only for fixtures where the current model would also have priced the fixture.
- Restrict initial research-lane publication to passing leagues only.
- Keep canonical-only fixtures blocked until N >= 200 and segment calibration is stable.
- CLV monitoring must log `current_model_would_have_priced` so live results can keep common vs extended-coverage bets separate.
- Allowed-league config written to `data\football-form\corners-v0-allowed-leagues.json`.
