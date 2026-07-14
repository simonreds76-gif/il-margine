# Team Shots v4 registered experiment

**Status: research only. The live v3 mean and routing are unchanged.**

v4 freezes the canonical EMA20 v3 mean and tests only NB2 dispersion. Per-team alpha is partially pooled to league alpha with `k=60`.

- Count-distribution gate: **PASS**
- Market/sell gate: **BLOCKED** pending the registered 2026-27 true-close sample.

## Walk-forward count-distribution folds

| Fold | Train team rows | Validation team rows | MAE | Bias | Poisson Brier | Fixed a=.25 | League MLE | Hierarchical MLE | Hierarchical log loss |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2024-2025 | 34854 | 3456 | 3.6321 | 0.6291 | 0.1933 | 0.1937 | 0.1896 | 0.1897 | 0.5603 |
| 2025-2026 | 38310 | 3468 | 3.6311 | 0.3301 | 0.1968 | 0.1991 | 0.1938 | 0.1937 | 0.5686 |

### Per-league Brier guard

| Fold | League | Team rows | Fixed a=.25 | Hierarchical MLE | Delta |
|---|---|---:|---:|---:|---:|
| 2024-2025 | bundesliga | 588 | 0.2013 | 0.1989 | -0.0024 |
| 2024-2025 | epl | 748 | 0.1917 | 0.1886 | -0.0030 |
| 2024-2025 | la-liga | 760 | 0.1878 | 0.1830 | -0.0048 |
| 2024-2025 | ligue-1 | 612 | 0.1933 | 0.1874 | -0.0059 |
| 2024-2025 | serie-a | 748 | 0.1959 | 0.1922 | -0.0037 |
| 2025-2026 | bundesliga | 612 | 0.2061 | 0.2005 | -0.0055 |
| 2025-2026 | epl | 760 | 0.1983 | 0.1906 | -0.0077 |
| 2025-2026 | la-liga | 748 | 0.1978 | 0.1929 | -0.0050 |
| 2025-2026 | ligue-1 | 600 | 0.2006 | 0.1985 | -0.0021 |
| 2025-2026 | serie-a | 748 | 0.1942 | 0.1882 | -0.0060 |

The count MAE/bias columns are identical across distribution variants because the mean is deliberately frozen.

## Captured-market diagnostic

- Status: **DIAGNOSTIC_ONLY**
- Matched two-way market rows: 780
- Earlier/later temporal split: 468 / 312 at 2026-05-09
- Fitted over-vig share: 0.856
- Fitted model logit weight: 0.180
- Validation Brier, market / model / blend: 0.2490 / 0.2459 / 0.2467
- Validation log loss, market / blend: 0.6911 / 0.6865
- True-close coverage (<=2h): 65/312 (20.8%)

This is not a sell gate: the market sample begins in April 2026 and true-close coverage is too low. It exists to prevent us from mistaking a model-only probability improvement for a takeable betting edge.

## Locked decision rule

- Continue to prospective shadow only if hierarchical NB improves both validation folds versus fixed alpha and does not regress log loss.
- Sellability still requires >=150 settled real-price bets, true-close coverage >=70%, and mean true-close CLV >=+0.5%.
- No MD1-MD3 bets and no live wiring from this report.
