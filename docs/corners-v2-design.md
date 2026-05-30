# Corners v2 real-odds rebuild

Last updated: 2026-05-30
Status: research design, not sellable, not public picks

## Decision

Build the v2 corners lane as a real-odds-only validation system. The first model form is a Negative Binomial match-total model, with the existing independent-Poisson model kept as the v1 control. Do not build or sell a corners product from the old synthetic backtest.

## Why v1 is not enough

The current historical report is useful for count calibration, but it is not a tradeable backtest. It compares the model against a synthetic B365 1X2-to-corners regression and fair no-vig prices. That makes the headline ROI an artifact of model-vs-model disagreement, not proof of value against bookmaker odds.

The only evidence that matters for a sellable lane is real captured Pinnacle corner odds. Current real-odds evidence is thin and not positive enough: the v0 CLV monitor has only about 48 settled real picks, negative/flat ROI, and weak published-to-close CLV. Therefore corners remains shadow/research until the real-odds gates below pass.

## Model v2, phase 1

Use a Negative Binomial model on match total corners:

- Existing EMA legs still estimate home and away corner expectation.
- The match-total mean is `lambda_total = lambda_home + lambda_away`.
- Total corners are priced with `NB(mean=lambda_total, dispersion=r)`.
- Dispersion `r` is fit from historical actual totals, pooled first, then optionally per league with shrinkage toward pooled.
- Independent Poisson remains the control model.
- Bivariate Poisson is deferred unless NB improves calibration but still misses home/away correlation or tail shape.

This directly addresses the main structural weakness: corner totals are overdispersed relative to Poisson.

## Market anchoring

v2 must anchor to real Pinnacle lines, not synthetic lines.

Required backtest flow:

1. Load `data/corners-ou/pinnacle-corners-odds.csv`.
2. Group by match, line, and side.
3. De-vig each over/under pair into a fair market probability.
4. Infer a market total expectation from the real line/price surface where possible.
5. Blend in lambda space:

```text
lambda_final = w * lambda_model + (1 - w) * lambda_market
```

Start with small `w` in the 0.20 to 0.35 range and fit only on past data. The market is the anchor; the model is the residual signal.

## Validation rule

All validation that mentions ROI, CLV, or sellability must use real captured Pinnacle odds. Synthetic backtests may only be labelled calibration diagnostics.

The next required script is:

```text
scripts/corners-real-odds-backtest.py
```

It should produce:

```text
data/corners-ou/corners-real-odds-backtest-results.csv
data/corners-ou/corners-real-odds-backtest-report.txt
```

Required output columns:

```text
match_id,date,league,home,away,line,side,published_odds,close_odds,
actual_total,result,pnl_units,model_prob,market_fair_prob,edge,
published_to_close_clv,positive_clv,model_version,close_is_stale
```

## Sellability gate

Corners is not sellable unless every condition below is true on real captured Pinnacle odds:

```text
n >= 200 settled real-odds picks
mean published-to-close CLV >= +1.0%
positive CLV share >= 55%
ROI >= 0%
CLV positive in at least 3 of 5 leagues with n >= 40
no league with n >= 40 below -0.5% CLV
no line band with n >= 40 below -0.5% CLV
```

Calibration gate:

```text
pooled Brier <= independent-Poisson v1 Brier
league Brier <= 1.05x v1 for each league with n >= 150
reliability bins within +/-3 percentage points where sample size is credible
```

Until those gates pass, corners remains internal shadow research.

## Anti-overfit rules

- No per league by line parameter grid.
- No threshold sweep in the tradeable report.
- No reporting ROI for slices with fewer than 150 settled picks.
- Walk-forward only: each scored fixture can only use data available before that fixture.
- The final sell/no-sell decision comes from pooled real-odds CLV/Brier, not the best-looking league.

## Code plan

Phase A, foundation:

- Add `scripts/corners_nb.py` with pure Negative Binomial maths and dispersion fitting.
- Keep `scripts/corners_poisson.py` unchanged as the v1 control.
- Add this design doc so the hard constraints survive future sessions.

Phase B, real-odds validation:

- Add `scripts/corners-real-odds-backtest.py`.
- Reuse odds loading ideas from `scripts/corners-v0-clv-monitor.py`.
- Compute real published odds, real close odds, real CLV, and real PnL only.
- Mark stale closes when the latest close snapshot is more than 12 hours before kickoff.

Phase C, integration:

- Modify `scripts/corners-v0-promotion-check.py` so research readiness requires the real-odds CLV gate.
- Modify `scripts/matchday-shortlist.py` only after v2 passes validation.
- Increase near-kickoff corner odds capture before next season so close prices are not day-stale.

## Product decision

Current status: no demonstrated sellable corners edge.

Commercial use before gates pass: none, except internal research. If v2 passes later, it can become a next-season football add-on. If it fails on real odds, kill corners rather than dressing up synthetic ROI.
