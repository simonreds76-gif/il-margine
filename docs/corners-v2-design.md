# Corners V2 Design

Status: research only. Nothing in this document authorises a paid or live corners lane.

## Reason for rebuild

The current corners v0 backtest is not a tradeable ROI test because it prices the model against a synthetic B365 1X2-derived corners baseline at no-vig fair odds. That can be useful for count calibration, but it is not evidence of beating a bookmaker market.

The only valid validation source for v2 is captured real Pinnacle corner totals.

## Approved model path

1. Build NB-total first.
2. Keep independent Poisson v1 as the control.
3. Add bivariate/correlation only if NB still misses Brier/reliability on real odds.

The v2 total model is:

```text
lambda_model_raw = lambda_home_ema + lambda_away_ema
debias_delta = mean(lambda_market - lambda_model_raw), fitted on pre-lock data only
lambda_model_adj = lambda_model_raw + debias_delta_league_or_pooled
lambda_market = NB mean implied by de-vigged Pinnacle over probability at the captured line
lambda_final = w * lambda_model_adj + (1 - w) * lambda_market
```

Default `w = 0.30`. The market is the anchor; the model is a residual perturbation. The level debias is fitted only on the pre-lock market sample, then frozen for the locked holdout.

## Validation rules

All validation must use real captured Pinnacle odds. Synthetic B365 regression prices are barred from ROI/CLV claims.

Sell gate, all required and measured on the locked holdout unless explicitly stated:

- At least 200 settled selected bets with true-close odds, where the close snapshot is no more than 2 hours before kickoff.
- Mean true-close published-to-close CLV at least +1.0%.
- At least 55% of selected bets positive true-close CLV.
- V2 Brier no worse than the de-vigged market Brier.
- Real-odds ROI at least 0 at the fixed pre-declared edge threshold.
- Positive true-close CLV in at least 3 of 5 leagues once each has at least 40 selected bets.

Until these pass, corners remains research/shadow only.

## Current locked-holdout read

After adding pre-lock market-scale debias, the broad fake under edge collapsed. The latest generated report still fails the sell gate:

- Holdout selected bets: 130.
- Holdout ROI: -6.06%.
- Holdout true-close CLV sample: 7 bets, insufficient.
- Holdout true-close CLV: -2.70%.
- Holdout V2 Brier: 0.241345 vs market Brier 0.240787, so the market still wins.

Interpretation: the immediate blocker is not another slice, it is better near-kickoff Pinnacle capture plus more settled real-price rows. Do not create an under-only or Serie A-only tracker from the old in-sample diagnostics.

## New files

- `scripts/corners_nb.py`: pure NB math helpers.
- `scripts/corners-nb-model.py`: additive NB prediction export for count calibration.
- `scripts/corners-real-odds-backtest.py`: the only valid v2 ROI/CLV validation gate.
- `data/corners-ou/corners-real-odds-backtest-results.csv`: generated scored real-odds rows.
- `data/corners-ou/corners-real-odds-backtest-report.txt`: generated gate report.

## Explicit non-goals

- Do not revive synthetic ROI tables as performance evidence.
- Do not slice league x line until sample sizes are large enough.
- Do not sell corners before the real-odds CLV gate passes.
- Do not merge corners v2 into `matchday-shortlist.py` until the gate passes.
