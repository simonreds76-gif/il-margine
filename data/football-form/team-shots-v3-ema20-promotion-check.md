# Team-Shots Promotion Check: `canonical_form_v3_ema20_nb`

Generated: 2026-04-25T22:19:15+00:00

This is a research-lane gate only. It does not change live picks.

Research lane ready across all leagues: **yes**
Research lane ready for passing leagues only: **yes**
Passing leagues: `bundesliga, epl, la-liga, ligue-1, serie-a`
Blocked leagues: `-`

## Per-League Gates

| League | Common N | Current MAE | Candidate MAE | Count | Brier | Log-loss | Last90 N | Last90 Current MAE | Last90 Candidate MAE | Last90 Improvement | Last90 Count | Last90 Brier | Last90 Log-loss |
| --- | ---: | ---: | ---: | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- | --- |
| bundesliga | 432 | 3.8726 | 3.7530 | PASS | PASS | PASS | 222 | 3.8478 | 3.7622 | 2.22% | PASS | PASS | PASS |
| epl | 544 | 3.6259 | 3.4297 | PASS | PASS | PASS | 224 | 3.4593 | 3.3498 | 3.17% | PASS | PASS | PASS |
| la-liga | 520 | 3.7184 | 3.5714 | PASS | PASS | PASS | 242 | 3.8294 | 3.7293 | 2.61% | PASS | PASS | PASS |
| ligue-1 | 428 | 3.7790 | 3.7326 | PASS | PASS | PASS | 212 | 3.5528 | 3.4854 | 1.90% | PASS | PASS | PASS |
| serie-a | 540 | 3.7501 | 3.6322 | PASS | PASS | PASS | 240 | 3.9397 | 3.8507 | 2.26% | PASS | PASS | PASS |

## Canonical-Only Guard

- Canonical-only sample size: `38850`
- Hard block active: `yes`
- Reason: Team-shots canonical-only coverage is large but not segment-validated yet; publish only where current_model_would_have_priced is true.

## Publication Rule

- Allow `canonical_form_v3_ema20_nb` into research lane only for fixtures where the current model would also have priced the fixture.
- Restrict initial research-lane publication to passing leagues only.
- Keep canonical-only fixtures blocked until segment calibration is stable.
- Allowed-league config written to `data/football-form/team-shots-v3-ema20-allowed-leagues.json`.
