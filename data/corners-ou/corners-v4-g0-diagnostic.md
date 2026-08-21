# Corners v4 G0 diagnostic

**RESEARCH ONLY. The live Corners v3 lane, locks, routing and stakes are unchanged.**

Additive candidates: pre-match favourite-strength gap and lagged corners per shot.
Enriched samples: 6901 / 10889
Missing features: `{"fav_gap_missing": 3, "fixture_not_found": 3985}`

## Count folds

| Season | Variant | MAE | Brier | Log loss | Bias | NB alpha |
|---|---|---:|---:|---:|---:|---:|
| 2024-2025 | v3_control | 2.6904 | 0.2116 | 0.6122 | +0.1061 | 0.0177 |
| 2024-2025 | v3_plus_fav_gap | 2.6891 | 0.2114 | 0.6117 | +0.1082 | 0.0174 |
| 2024-2025 | v3_plus_corner_per_shot | 2.6856 | 0.2114 | 0.6117 | +0.0716 | 0.0176 |
| 2024-2025 | v4_full | 2.6850 | 0.2112 | 0.6114 | +0.0810 | 0.0174 |
| 2024-2025 | v4_lean_no_wide_block | 2.6825 | 0.2111 | 0.6111 | +0.0629 | 0.0174 |
| 2024-2025 | v4_core | 2.6834 | 0.2111 | 0.6111 | +0.0665 | 0.0174 |
| 2025-2026 | v3_control | 2.7249 | 0.2127 | 0.6147 | +0.1244 | 0.0181 |
| 2025-2026 | v3_plus_fav_gap | 2.7217 | 0.2125 | 0.6142 | +0.1131 | 0.0178 |
| 2025-2026 | v3_plus_corner_per_shot | 2.7213 | 0.2126 | 0.6144 | +0.1003 | 0.0180 |
| 2025-2026 | v4_full | 2.7189 | 0.2124 | 0.6140 | +0.0939 | 0.0177 |
| 2025-2026 | v4_lean_no_wide_block | 2.7175 | 0.2123 | 0.6139 | +0.0955 | 0.0178 |
| 2025-2026 | v4_core | 2.7185 | 0.2124 | 0.6140 | +0.0981 | 0.0178 |

## Real-market G0

G0a: absolute predicted-minus-actual over-rate <= 0.015 at every line 7.5-12.5.
G0b: raw model Brier <= de-vigged Pinnacle Brier + 0.010.

| Variant | n | Model Brier | Market Brier | Delta | G0a | G0b | Overall |
|---|---:|---:|---:|---:|---|---|---|
| v3_control | 431 | 0.249714 | 0.240626 | +0.009088 | FAIL | PASS | FAIL |
| v3_plus_fav_gap | 431 | 0.249730 | 0.240626 | +0.009105 | FAIL | PASS | FAIL |
| v3_plus_corner_per_shot | 431 | 0.249904 | 0.240626 | +0.009278 | FAIL | PASS | FAIL |
| v4_full | 431 | 0.249892 | 0.240626 | +0.009267 | FAIL | PASS | FAIL |
| v4_lean_no_wide_block | 431 | 0.249590 | 0.240626 | +0.008965 | FAIL | PASS | FAIL |
| v4_core | 431 | 0.249867 | 0.240626 | +0.009241 | FAIL | PASS | FAIL |

### Per-line calibration

#### v3_control

| Line | n | Predicted over | Actual over | Residual | Model Brier | Market Brier | Gate |
|---:|---:|---:|---:|---:|---:|---:|---|
| 7.5 | 19 | 67.010% | 52.632% | +14.378% | 0.260589 | 0.240427 | FAIL |
| 8.5 | 129 | 57.524% | 58.915% | -1.391% | 0.240781 | 0.235211 | PASS |
| 9.5 | 161 | 46.493% | 52.174% | -5.681% | 0.250992 | 0.242390 | FAIL |
| 10.5 | 111 | 36.311% | 44.144% | -7.833% | 0.254868 | 0.243184 | FAIL |
| 11.5 | 11 | 31.918% | 45.455% | -13.537% | 0.264964 | 0.252822 | FAIL |
| 12.5 | 0 | - | - | - | - | - | FAIL |

#### v3_plus_fav_gap

| Line | n | Predicted over | Actual over | Residual | Model Brier | Market Brier | Gate |
|---:|---:|---:|---:|---:|---:|---:|---|
| 7.5 | 19 | 66.838% | 52.632% | +14.207% | 0.258324 | 0.240427 | FAIL |
| 8.5 | 129 | 57.242% | 58.915% | -1.673% | 0.240225 | 0.235211 | FAIL |
| 9.5 | 161 | 46.225% | 52.174% | -5.949% | 0.251311 | 0.242390 | FAIL |
| 10.5 | 111 | 36.040% | 44.144% | -8.104% | 0.254571 | 0.243184 | FAIL |
| 11.5 | 11 | 31.937% | 45.455% | -13.518% | 0.274359 | 0.252822 | FAIL |
| 12.5 | 0 | - | - | - | - | - | FAIL |

#### v3_plus_corner_per_shot

| Line | n | Predicted over | Actual over | Residual | Model Brier | Market Brier | Gate |
|---:|---:|---:|---:|---:|---:|---:|---|
| 7.5 | 19 | 66.514% | 52.632% | +13.883% | 0.261414 | 0.240427 | FAIL |
| 8.5 | 129 | 57.063% | 58.915% | -1.852% | 0.241468 | 0.235211 | FAIL |
| 9.5 | 161 | 46.118% | 52.174% | -6.056% | 0.251183 | 0.242390 | FAIL |
| 10.5 | 111 | 36.133% | 44.144% | -8.011% | 0.254760 | 0.243184 | FAIL |
| 11.5 | 11 | 32.164% | 45.455% | -13.291% | 0.261219 | 0.252822 | FAIL |
| 12.5 | 0 | - | - | - | - | - | FAIL |

#### v4_full

| Line | n | Predicted over | Actual over | Residual | Model Brier | Market Brier | Gate |
|---:|---:|---:|---:|---:|---:|---:|---|
| 7.5 | 19 | 66.425% | 52.632% | +13.794% | 0.259153 | 0.240427 | FAIL |
| 8.5 | 129 | 56.863% | 58.915% | -2.052% | 0.240837 | 0.235211 | FAIL |
| 9.5 | 161 | 45.918% | 52.174% | -6.256% | 0.251465 | 0.242390 | FAIL |
| 10.5 | 111 | 35.899% | 44.144% | -8.245% | 0.254482 | 0.243184 | FAIL |
| 11.5 | 11 | 32.134% | 45.455% | -13.321% | 0.270757 | 0.252822 | FAIL |
| 12.5 | 0 | - | - | - | - | - | FAIL |

#### v4_lean_no_wide_block

| Line | n | Predicted over | Actual over | Residual | Model Brier | Market Brier | Gate |
|---:|---:|---:|---:|---:|---:|---:|---|
| 7.5 | 19 | 66.309% | 52.632% | +13.678% | 0.259052 | 0.240427 | FAIL |
| 8.5 | 129 | 56.762% | 58.915% | -2.153% | 0.240633 | 0.235211 | FAIL |
| 9.5 | 161 | 45.879% | 52.174% | -6.295% | 0.251388 | 0.242390 | FAIL |
| 10.5 | 111 | 35.920% | 44.144% | -8.224% | 0.253861 | 0.243184 | FAIL |
| 11.5 | 11 | 32.463% | 45.455% | -12.991% | 0.268902 | 0.252822 | FAIL |
| 12.5 | 0 | - | - | - | - | - | FAIL |

#### v4_core

| Line | n | Predicted over | Actual over | Residual | Model Brier | Market Brier | Gate |
|---:|---:|---:|---:|---:|---:|---:|---|
| 7.5 | 19 | 66.499% | 52.632% | +13.868% | 0.258164 | 0.240427 | FAIL |
| 8.5 | 129 | 56.866% | 58.915% | -2.049% | 0.240465 | 0.235211 | FAIL |
| 9.5 | 161 | 45.925% | 52.174% | -6.249% | 0.251752 | 0.242390 | FAIL |
| 10.5 | 111 | 35.861% | 44.144% | -8.283% | 0.254484 | 0.243184 | FAIL |
| 11.5 | 11 | 32.104% | 45.455% | -13.351% | 0.271612 | 0.252822 | FAIL |
| 12.5 | 0 | - | - | - | - | - | FAIL |

## Decision

No candidate is promoted by this script. Passing G0 would only justify a locked prospective shadow registration; it would not establish a sellable edge.
