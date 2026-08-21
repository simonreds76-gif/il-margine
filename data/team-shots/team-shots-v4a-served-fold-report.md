# Team Shots v4a served-baseline diagnostic

**Status: research only. The live v3 mean and routing are unchanged.**

v4a reproduces the currently served mean with `use_market=False`. It is an honest diagnostic of the train/serve mismatch and cannot change routing, stakes, promotion state, or the registered v4 artifacts.

- Count-distribution gate: **PASS**
- Market/sell gate: **BLOCKED** pending the registered 2026-27 true-close sample.

## Walk-forward count-distribution folds

| Fold | Train team rows | Validation team rows | MAE | Bias | Poisson Brier | Fixed a=.25 | League MLE | Hierarchical MLE | Hierarchical log loss |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2024-2025 | 34854 | 3456 | 3.7217 | 0.5205 | 0.1988 | 0.2018 | 0.1962 | 0.1962 | 0.5752 |
| 2025-2026 | 38310 | 3468 | 3.7240 | 0.2311 | 0.2021 | 0.2070 | 0.2004 | 0.2002 | 0.5845 |

## Train/serve mismatch versus registered v4

Positive deltas are regressions from removing the causal market-strength input at serve time.

| Fold | Registered MAE | Served MAE | MAE delta | Registered hierarchical Brier | Served hierarchical Brier | Brier delta |
|---|---:|---:|---:|---:|---:|---:|
| 2024-2025 | 3.6321 | 3.7217 | +0.0897 | 0.1897 | 0.1962 | +0.0065 |
| 2025-2026 | 3.6311 | 3.7240 | +0.0929 | 0.1937 | 0.2002 | +0.0066 |

### Per-league Brier guard

| Fold | League | Team rows | Fixed a=.25 | Hierarchical MLE | Delta |
|---|---|---:|---:|---:|---:|
| 2024-2025 | bundesliga | 588 | 0.2089 | 0.2053 | -0.0037 |
| 2024-2025 | epl | 748 | 0.2008 | 0.1961 | -0.0046 |
| 2024-2025 | la-liga | 760 | 0.1950 | 0.1880 | -0.0070 |
| 2024-2025 | ligue-1 | 612 | 0.2030 | 0.1965 | -0.0065 |
| 2024-2025 | serie-a | 748 | 0.2032 | 0.1971 | -0.0060 |
| 2025-2026 | bundesliga | 612 | 0.2126 | 0.2056 | -0.0069 |
| 2025-2026 | epl | 760 | 0.2072 | 0.1989 | -0.0084 |
| 2025-2026 | la-liga | 748 | 0.2048 | 0.1986 | -0.0062 |
| 2025-2026 | ligue-1 | 600 | 0.2083 | 0.2045 | -0.0038 |
| 2025-2026 | serie-a | 748 | 0.2031 | 0.1955 | -0.0076 |

The count MAE/bias columns are identical across distribution variants because the mean is deliberately frozen.

## Captured-market diagnostic

- Status: **DIAGNOSTIC_ONLY**
- Matched two-way market rows: 780
- Earlier/later temporal split: 468 / 312 at 2026-05-09
- Fitted over-vig share: 0.856
- Fitted model logit weight: 0.240
- Validation Brier, market / model / blend: 0.2490 / 0.2536 / 0.2465
- Validation log loss, market / blend: 0.6911 / 0.6861
- True-close coverage (<=2h): 65/312 (20.8%)

This is not a sell gate: the market sample begins in April 2026 and true-close coverage is too low. It exists to prevent us from mistaking a model-only probability improvement for a takeable betting edge.

## Locked decision rule

- Continue to prospective shadow only if hierarchical NB improves both validation folds versus fixed alpha and does not regress log loss.
- Sellability still requires >=150 settled real-price bets, true-close coverage >=70%, and mean true-close CLV >=+0.5%.
- No MD1-MD3 bets and no live wiring from this report.
