# Team-Shots Promotion Check: `canonical_form_v2_pooled_opp_nb`

Generated: 2026-04-25T19:44:33+00:00

This is a research-lane gate only. It does not change live picks.

Research lane ready across all leagues: **no**
Research lane ready for passing leagues only: **yes**
Passing leagues: `bundesliga, la-liga, ligue-1`
Blocked leagues: `epl, serie-a`

## Per-League Gates

| League | Common N | Current MAE | V1 MAE | Count | Brier | Log-loss | Last90 N | Last90 Current MAE | Last90 V1 MAE | Last90 Improvement | Last90 Count | Last90 Brier | Last90 Log-loss |
| --- | ---: | ---: | ---: | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- | --- |
| bundesliga | 432 | 3.8726 | 3.7870 | PASS | PASS | PASS | 222 | 3.8478 | 3.7969 | 1.32% | PASS | PASS | PASS |
| epl | 544 | 3.6259 | 3.5700 | PASS | PASS | PASS | 224 | 3.4593 | 3.5543 | -2.75% | FAIL | FAIL | FAIL |
| la-liga | 520 | 3.7184 | 3.6381 | PASS | PASS | PASS | 242 | 3.8294 | 3.8061 | 0.61% | PASS | PASS | PASS |
| ligue-1 | 428 | 3.7790 | 3.7218 | PASS | PASS | PASS | 212 | 3.5528 | 3.4977 | 1.55% | PASS | PASS | PASS |
| serie-a | 540 | 3.7501 | 3.7342 | PASS | PASS | PASS | 240 | 3.9397 | 3.9463 | -0.17% | FAIL | PASS | PASS |

## Canonical-Only Guard

- Canonical-only sample size: `38850`
- Hard block active: `yes`
- Reason: Team-shots canonical-only coverage is large but not segment-validated yet; publish only where current_model_would_have_priced is true.

## Publication Rule

- Allow `canonical_form_v2_pooled_opp_nb` into research lane only for fixtures where the current model would also have priced the fixture.
- Restrict initial research-lane publication to passing leagues only.
- Keep canonical-only fixtures blocked until segment calibration is stable.
- Allowed-league config written to `data/football-form/team-shots-v2-allowed-leagues.json`.
