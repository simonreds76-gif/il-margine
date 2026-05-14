# Clay ML Disable Note - May 2026

## Status

Clay ML stays disabled.

- `STRICT_CLAY_CALIBRATED_ENABLED` defaults to `0` in scheduled runs.
- `CLAY_BO3_ML_ENABLE` defaults to `0` in scheduled runs and `strict-policy-report.py`.
- `clay_bo3` may continue as an internal diagnostic/near-miss lane, but it must not emit ML bets unless explicitly enabled for a research run.

## Why

The repo's own calibration diagnostic rejects the clay ML model:

- Holdout 2025 ECE: `0.0580`, above the `0.04` gate.
- Holdout 2025 log-loss delta vs Pinnacle: `+0.0263`.
- Holdout 2025 model log-loss: `0.6199`.
- Holdout 2025 Pinnacle log-loss: `0.5936`.
- Verdict in `clay-ml-calibration-analysis.txt`: do not re-enable clay ML shadow before refitting/reviewing the calibration map.

The current clay bo3 ML signal gate also failed the 2022-2025 historical backtest:

- Scope: ATP clay non-Slam bo3, `confidence=high`, edge `5-13%`, flat 1u.
- Overall: `336` bets, `144W-192L`, `-45.00u`, `-13.4% ROI`.
- 2022: `-18.5% ROI`.
- 2023: `-5.8% ROI`.
- 2024: `-14.8% ROI`.
- 2025: `-14.5% ROI`.
- Simple edge-band sweep inside `5-13%` did not produce a robust by-year pass.

The earlier commit `c73a2271` re-enabled clay calibrated shadow despite the diagnostic failure. That was the wrong direction. The disable is now intentional.

## Market Coverage

- Clay ML can be historically backtested from `data/backtest/backtest-results-{2022..2025}.csv`.
- Historical open-close CLV should be possible by joining those rows to tennis-data `PSW` / `PSL` close prices in `data/backtest/atp-{2022..2025}.xlsx`.
- Clay spread/handicap cannot be honestly backtested for 2022-2025 from current repo data because historical spread line and spread odds were not persisted.
- Clay totals cannot be honestly backtested for 2022-2025 because historical OU lines and odds are absent.
- Challenger cannot be historically backtested from current ATP-only backtest files; it must remain monitor-only until real odds/outcome history exists.

## Locked Re-Enable Gates

Any future clay ML re-enable needs one locked design and one sealed 2025 touch. All gates must pass:

- 2025 sealed sample size `N >= 100`.
- 2025 sealed ROI bootstrap 95% lower bound `> -1%`.
- 2025 sealed ROI `> -3%`.
- Model log-loss delta vs Pinnacle `<= 0`.
- Model Brier score `<=` Pinnacle Brier score.
- ECE `<= 0.04`.
- Average CLV `>= 0`.
- CLV-positive rate `>= 50%`.
- Each edge bucket with `n >= 30` has ROI `>= -3%`.
- Backtest stability: 2022, 2023, and 2024 each have ROI `> -3%`.
- Sealed touches consumed for the design iteration: `<= 1`.

If a proposal cannot satisfy these gates, keep clay ML disabled.
