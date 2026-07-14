# Team Fouls v1: F1 Walk-Forward Count Gate

Generated: 2026-07-14T22:49:36Z
Samples: 41,772 team legs across 20,886 matches.

**Decision: COUNT GATE FAIL MARKET BLOCKED. No bets or public signals are authorized.**

The model is evaluated without bookmaker foul prices. Passing this report would validate count estimates only; M0 remains a separate hard block.

## Fold results

| Fold | Train legs | Validation matches | Baseline MAE | Full MAE | Improvement | Full NLL |
|---|---:|---:|---:|---:|---:|---:|
| 2024-2025 | 34,850 | 1,727 | 3.075 | 2.839 | +7.69% | 2.6792 |
| 2025-2026 | 38,304 | 1,734 | 3.043 | 2.790 | +8.29% | 2.6621 |

## Registered feature ladder

| Fold | Transition | Scope | Delta NLL | Delta MAE | Gate |
|---|---|---|---:|---:|---|
| 2024-2025 | core -> core_referee | EPL | +0.00139 | +0.00831 | FAIL |
| 2024-2025 | core_referee -> core_referee_market | ALL | -0.00703 | -0.02370 | PASS |
| 2024-2025 | core_referee_market -> full | ALL | +0.00002 | +0.00009 | FAIL |
| 2025-2026 | core -> core_referee | EPL | -0.00257 | -0.00784 | PASS |
| 2025-2026 | core_referee -> core_referee_market | ALL | -0.00533 | -0.01651 | PASS |
| 2025-2026 | core_referee_market -> full | ALL | -0.00007 | -0.00010 | FAIL |

## Distribution and calibration

| Fold | Poisson Brier | Fixed NB Brier | Hierarchical NB Brier | Max decile gap | Empirical total VMR | Priced total VMR |
|---|---:|---:|---:|---:|---:|---:|
| 2024-2025 | 0.1900 | 0.1904 | 0.1901 | 1.527% | 1.373 | 1.431 |
| 2025-2026 | 0.1852 | 0.1858 | 0.1853 | 2.091% | 1.459 | 1.482 |

## Gate summary

- PASS: `folds_complete`
- FAIL: `feature_ladder`
- PASS: `mae_improvement`
- FAIL: `hierarchical_nb_cells`
- FAIL: `reliability`
- PASS: `total_variance`
- FAIL: `market_prices`

Hierarchical NB wins: 2/10 league-fold cells (required 8/10).

## Product status

- Research only. This script does not write candidates, picks, stakes, or settlement rows.
- Team/match fouls prices remain unobserved in the configured feed.
- A future lock requires paired bookmaker prices, source-definition agreement, and prospective CLV evidence.
