# Corners v3 registered experiment

**Status: research only. Corners publication remains blocked.**

## Event-feature coverage

- Eligible 2019+ top-five fixtures: 13394
- Matched Understat event fixtures: 11405
- Coverage: 85.2% (required 70%)
- Lagged model samples after history gate: 10889
- Coverage gate: **PASS**
- Count-model gate: **PASS**
- Market/sell gate: **BLOCKED** pending the registered 2026-27 real-price sample.

WIDE is `abs(Y-0.5)>=0.18`; BLOCK is the Understat `BlockedShot` rate. Both are lagged EMA20 proxies.

## Walk-forward folds

| Fold | Train | Validation | Baseline MAE | v3 MAE | Baseline Brier | v3 Brier | Baseline log loss | v3 log loss |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2024-2025 | 7590 | 1653 | 2.7884 | 2.7036 | 0.2202 | 0.2121 | 0.6364 | 0.6132 |
| 2025-2026 | 9243 | 1646 | 2.8019 | 2.7033 | 0.2232 | 0.2132 | 0.6432 | 0.6156 |

### Per-league Brier guard

| Fold | League | Matches | Baseline | v3 | Delta |
|---|---|---:|---:|---:|---:|
| 2024-2025 | bundesliga | 258 | 0.2238 | 0.2148 | -0.0089 |
| 2024-2025 | epl | 374 | 0.2242 | 0.2169 | -0.0073 |
| 2024-2025 | la-liga | 342 | 0.2125 | 0.2063 | -0.0062 |
| 2024-2025 | ligue-1 | 306 | 0.2188 | 0.2084 | -0.0104 |
| 2024-2025 | serie-a | 373 | 0.2219 | 0.2137 | -0.0082 |
| 2025-2026 | bundesliga | 234 | 0.2225 | 0.2178 | -0.0047 |
| 2025-2026 | epl | 374 | 0.2315 | 0.2150 | -0.0164 |
| 2025-2026 | la-liga | 373 | 0.2269 | 0.2160 | -0.0109 |
| 2025-2026 | ligue-1 | 291 | 0.2233 | 0.2165 | -0.0068 |
| 2025-2026 | serie-a | 374 | 0.2115 | 0.2029 | -0.0086 |

### Pre-registered feature ablation

| Fold | Variant | MAE | Brier | Log loss | NB alpha |
|---|---|---:|---:|---:|---:|
| 2024-2025 | CF/CA | 2.7046 | 0.2121 | 0.6133 | 0.0161 |
| 2024-2025 | CF/CA + TEMPO | 2.7042 | 0.2121 | 0.6133 | 0.0161 |
| 2024-2025 | FULL | 2.7036 | 0.2121 | 0.6132 | 0.0161 |
| 2025-2026 | CF/CA | 2.7058 | 0.2133 | 0.6161 | 0.0167 |
| 2025-2026 | CF/CA + TEMPO | 2.7046 | 0.2132 | 0.6156 | 0.0167 |
| 2025-2026 | FULL | 2.7033 | 0.2132 | 0.6156 | 0.0167 |

### Standardized fitted coefficients

Coefficients are fitted on each fold's training window only. They are shown for auditability, not causal interpretation.

| Fold | Intercept | CF home | CA away | CF away | CA home | WIDE | BLOCK | TEMPO | NB alpha |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2024-2025 | -0.045 | +0.022 | +0.028 | +0.005 | +0.020 | -0.002 | -0.001 | +0.006 | 0.0161 |
| 2025-2026 | -0.046 | +0.023 | +0.028 | +0.005 | +0.018 | -0.002 | -0.004 | +0.007 | 0.0167 |

## Market gate

**BLOCKED.** Historical 2024-25/2025-26 Pinnacle corner prices do not exist in this repository. Count accuracy can reject v3, but cannot promote it. The 2026-27 prospective window must beat de-vigged real Pinnacle Brier and log loss.

If the count folds fail, corners v3 is killed before prospective selection. If they pass, it enters shadow only; it does not become sellable.
