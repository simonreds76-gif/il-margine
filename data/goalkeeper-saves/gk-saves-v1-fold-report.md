# Goalkeeper Saves v1 registered count backtest

**Status: RESEARCH / COUNT GATE ONLY. No historical goalkeeper-saves prices exist, so ROI and CLV are unavailable.**

## Target integrity

- Historical fixtures: 21,589
- Missing fixtures: 2
- Anomalous fixtures dropped in full: 108
- Valid team-save observations: 42,958
- Mean / variance-to-mean / zero rate: 3.0242 / 1.3569 / 7.41%
- Model samples after lagged-history and feature gates: 38,426

Target is team saves (`opponent SOT - opponent goals`) and may only be published against a named goalkeeper after a confirmed starting XI.

## Walk-forward folds

| Fold | Model | Train | Validation | MAE | Bias | Brier | Log loss | NB2 alpha |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 2024-2025 | INCUMBENT | 32028 | 3222 | 1.5702 | +0.0426 | 0.1826 | 0.5452 | 0.1081 |
| 2024-2025 | POISSON_CORE_SHOTS | 32028 | 3222 | 1.5349 | +0.1097 | 0.1779 | 0.5327 | 0.0000 |
| 2024-2025 | NB2_CORE | 32028 | 3222 | 1.5366 | +0.1067 | 0.1772 | 0.5305 | 0.0853 |
| 2024-2025 | NB2_CORE_SHOTS | 32028 | 3222 | 1.5357 | +0.1140 | 0.1770 | 0.5299 | 0.0850 |
| 2024-2025 | NB2_MARKET | 32028 | 3222 | 1.5160 | +0.0825 | 0.1752 | 0.5251 | 0.0743 |
| 2024-2025 | NB2_XG | 32028 | 3222 | 1.5184 | +0.1638 | 0.1743 | 0.5225 | 0.0701 |
| 2024-2025 | NB2_FULL | 32028 | 3222 | 1.5066 | +0.1163 | 0.1735 | 0.5209 | 0.0673 |
| 2025-2026 | INCUMBENT | 35250 | 3176 | 1.5310 | +0.0829 | 0.1788 | 0.5357 | 0.1077 |
| 2025-2026 | POISSON_CORE_SHOTS | 35250 | 3176 | 1.5042 | +0.0853 | 0.1758 | 0.5279 | 0.0000 |
| 2025-2026 | NB2_CORE | 35250 | 3176 | 1.5040 | +0.0782 | 0.1752 | 0.5260 | 0.0844 |
| 2025-2026 | NB2_CORE_SHOTS | 35250 | 3176 | 1.5048 | +0.0901 | 0.1751 | 0.5256 | 0.0841 |
| 2025-2026 | NB2_MARKET | 35250 | 3176 | 1.4836 | +0.0862 | 0.1723 | 0.5181 | 0.0738 |
| 2025-2026 | NB2_XG | 35250 | 3176 | 1.4888 | +0.1689 | 0.1718 | 0.5167 | 0.0695 |
| 2025-2026 | NB2_FULL | 35250 | 3176 | 1.4764 | +0.1115 | 0.1713 | 0.5155 | 0.0667 |

## Full candidate per-league guard

| Fold | League | n | Incumbent Brier | NB2 Full Brier | Delta |
|---|---|---:|---:|---:|---:|
| 2024-2025 | bundesliga | 586 | 0.1755 | 0.1719 | -0.0036 |
| 2024-2025 | epl | 744 | 0.1846 | 0.1761 | -0.0086 |
| 2024-2025 | la-liga | 610 | 0.1773 | 0.1705 | -0.0068 |
| 2024-2025 | ligue-1 | 610 | 0.1901 | 0.1729 | -0.0172 |
| 2024-2025 | serie-a | 672 | 0.1846 | 0.1755 | -0.0092 |
| 2025-2026 | bundesliga | 544 | 0.1805 | 0.1731 | -0.0074 |
| 2025-2026 | epl | 756 | 0.1709 | 0.1674 | -0.0035 |
| 2025-2026 | la-liga | 604 | 0.1835 | 0.1718 | -0.0117 |
| 2025-2026 | ligue-1 | 600 | 0.1816 | 0.1742 | -0.0074 |
| 2025-2026 | serie-a | 672 | 0.1795 | 0.1714 | -0.0081 |

## Registered decision

- Candidate: `goalkeeper-saves-v1-nb2-confirmed-starter`.
- Count evidence can authorize prospective shadow capture only.
- Bet publication requires confirmed lineups, paired real Bet365 prices and one strongest selection per fixture.
- Sell gate remains blocked until >=150 settled real-price selections, >=70% true-close coverage and mean true-close CLV >=+0.5%.
- No synthetic-price P/L, inferred CLV or public/live routing is permitted.

## Sample build counters

- anomalous_fixture: 110
- eligible: 38,426
- feature_missing: 3,134
- history_gate: 1,398
