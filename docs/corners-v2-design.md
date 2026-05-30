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
lambda_model = lambda_home_ema + lambda_away_ema
lambda_market = NB mean implied by de-vigged Pinnacle over probability at the captured line
lambda_final = w * lambda_model + (1 - w) * lambda_market
```

Default `w = 0.30`. The market is the anchor; the model is a residual perturbation.

## Validation rules

All validation must use real captured Pinnacle odds. Synthetic B365 regression prices are barred from ROI/CLV claims.

Sell gate, all required:

- At least 200 settled real-odds selected bets.
- Mean published-to-close CLV at least +1.0%.
- At least 55% of selected bets positive CLV.
- Real-odds ROI at least 0 at the fixed pre-declared edge threshold.
- Positive CLV in at least 3 of 5 leagues once each has at least 40 selected bets.

Until these pass, corners remains research/shadow only.

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
