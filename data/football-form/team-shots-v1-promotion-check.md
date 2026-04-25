# Team-Shots V1 Promotion Check

Generated: 2026-04-25T19:23:21+00:00

This is a research-lane gate only. It does not change live picks.

Research lane ready across all leagues: **no**
Research lane ready for passing leagues only: **yes**
Passing leagues: `la-liga`
Blocked leagues: `bundesliga, epl, ligue-1, serie-a`

## Per-League Gates

| League | Common N | Current MAE | V1 MAE | Count | Brier | Log-loss | Last90 N | Last90 Current MAE | Last90 V1 MAE | Last90 Improvement | Last90 Count | Last90 Brier | Last90 Log-loss |
| --- | ---: | ---: | ---: | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- | --- |
| bundesliga | 432 | 3.8726 | 3.7781 | PASS | PASS | PASS | 222 | 3.8478 | 3.8572 | -0.24% | FAIL | PASS | FAIL |
| epl | 544 | 3.6259 | 3.6504 | FAIL | PASS | PASS | 224 | 3.4593 | 3.5884 | -3.73% | FAIL | FAIL | PASS |
| la-liga | 520 | 3.7184 | 3.6305 | PASS | PASS | PASS | 242 | 3.8294 | 3.7148 | 2.99% | PASS | PASS | PASS |
| ligue-1 | 428 | 3.7790 | 3.7990 | FAIL | PASS | PASS | 212 | 3.5528 | 3.6434 | -2.55% | FAIL | FAIL | PASS |
| serie-a | 540 | 3.7501 | 3.7954 | FAIL | PASS | PASS | 240 | 3.9397 | 4.0260 | -2.19% | FAIL | PASS | PASS |

## Canonical-Only Guard

- Canonical-only sample size: `38850`
- Hard block active: `yes`
- Reason: Team-shots canonical-only coverage is large but not segment-validated yet; publish only where current_model_would_have_priced is true.

## Publication Rule

- Allow team-shots v1 into research lane only for fixtures where the current model would also have priced the fixture.
- Restrict initial research-lane publication to passing leagues only.
- Keep canonical-only fixtures blocked until segment calibration is stable.
- Allowed-league config written to `data\football-form\team-shots-v1-allowed-leagues.json`.
