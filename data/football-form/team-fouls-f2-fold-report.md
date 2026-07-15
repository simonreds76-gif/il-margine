# Team Fouls F2: Registered Poisson Holdout

Generated: 2026-07-15T10:50:24Z
Samples: 41,772 team legs across 20,886 matches.

**Decision: COUNT GATE FAIL EXTERNAL GATES BLOCKED. Signals remain disabled.**

F2 uses only team committed form, opponent fouls-drawn form and opening-market strength. It uses the locked F1 holdouts and performs no threshold or feature sweep.

| Fold | Baseline MAE | F2 MAE | Improvement | Strength dNLL | Strength dMAE | F2 Brier | F1 NB Brier | Max decile gap |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2024-2025 | 3.075 | 2.854 | +7.18% | -0.00197 | -0.00608 | 0.1912 | 0.1901 | 1.50% |
| 2025-2026 | 3.043 | 2.807 | +7.73% | -0.00009 | -0.00146 | 0.1867 | 0.1853 | 1.66% |

## Gate summary

- PASS: `folds_complete`
- PASS: `mae_improvement`
- FAIL: `opening_strength_increment`
- PASS: `beats_causal_probability_baseline`
- FAIL: `poisson_beats_f1_distribution`
- PASS: `reliability`
- FAIL: `market_prices`
- FAIL: `settlement_definition`

## Product status

- Research only; no candidate, stake, ROI or CLV row is produced.
- Paired Bet365 team-fouls O/U prices remain a hard external gate.
- Settlement source agreement remains a hard external gate.
- A count-gate pass alone never authorizes tips.
