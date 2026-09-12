# Team shots and corners: opponent-adjusted count research

Date: 12 September 2026. Status: LOCAL RESEARCH, NOT PROMOTED OR DEPLOYED.

This supersedes the partial-coverage outputs and preliminary figures from this session. StatsHub was used to understand visible model behaviour, not as a source of training labels or proof of profitability. Its hidden mean algorithm has not been recovered. No corners market was present in the inspected team-model selector.

## Implemented

- One fixed candidate per market, trained by negative-binomial count likelihood with ridge regularization; no ROI parameter search.
- Opponent-adjusted past performance, pooled attack/concession rates, home/away deviations, recent-vs-long form, shot pressure, rest, and league/venue baselines. Corner totals combine both teams and their strength asymmetry.
- Eight-match shrinkage prior, last-20 histories with 0.93 decay, minimum six observations, three-year fitting windows. Constants were specified before inspecting these candidate results.
- Strictly earlier-day history. Archived odds comparisons freeze history before capture day; rest uses the known fixture date. No untimestamped historical 1X2 odds or current-match statistics are input features.
- Verified alias deduplication in the canonical form builder and live publisher code. Four duplicate team records (two fixtures) removed from the research view. Conflicting duplicate results raise an error; missing enrichment can be merged.

## Matched-price replay

Count parameters frozen before 1 April 2026. Market blend fitted only on April–8 May probabilities, without an intercept. May–July is validation; August–early September is a previously inspected historical diagnostic, not a new untouched holdout. The incumbent below is the archived raw count model, not the served market-blended shots lane.

Flat 1u, at least 3% estimated EV, at most one selection per fixture, earliest complete same-bookmaker pre-kickoff market board. Each variant sees the same matched contracts, but may select different bets. No claim that all historical prices were executable. All losses remain in the full JSON pick lists.

| Market | Period | Variant | Bets | W–L | P/L | ROI | Brier ↓ |
|---|---|---|---:|---:|---:|---:|---:|
| shots | validation | candidate_raw | 90 | 57–33 | +14.91u | +16.6% | 0.23922 |
| shots | validation | candidate_calibrated | 49 | 34–15 | +13.93u | +28.4% | 0.23850 |
| shots | validation | incumbent_raw | 87 | 46–41 | -2.28u | -2.6% | 0.26311 |
| shots | validation | market | 0 | 0–0 | +0.00u | — | 0.24586 |
| shots | historical_diagnostic | candidate_raw | 83 | 40–43 | -8.54u | -10.3% | 0.27341 |
| shots | historical_diagnostic | candidate_calibrated | 48 | 25–23 | -1.61u | -3.4% | 0.25644 |
| shots | historical_diagnostic | incumbent_raw | 86 | 37–49 | -17.90u | -20.8% | 0.28460 |
| shots | historical_diagnostic | market | 0 | 0–0 | +0.00u | — | 0.24953 |
| corners | validation | candidate_raw | 33 | 15–18 | -2.60u | -7.9% | 0.24164 |
| corners | validation | candidate_calibrated | 0 | 0–0 | +0.00u | — | 0.24122 |
| corners | validation | incumbent_raw | 44 | 14–30 | -16.12u | -36.6% | 0.25373 |
| corners | validation | market | 0 | 0–0 | +0.00u | — | 0.24122 |
| corners | historical_diagnostic | candidate_raw | 32 | 14–18 | -1.60u | -5.0% | 0.24963 |
| corners | historical_diagnostic | candidate_calibrated | 0 | 0–0 | +0.00u | — | 0.24665 |
| corners | historical_diagnostic | incumbent_raw | 39 | 18–21 | -0.94u | -2.4% | 0.24772 |
| corners | historical_diagnostic | market | 0 | 0–0 | +0.00u | — | 0.24665 |

## Count validation and coverage

- shots: 592 matched price rows; 1 excluded. Frozen calibrated model weight: 0.445.
  - Fit before 2024-01-01: 11026 training observations; 3388 later observations. Candidate MAE 3.595, league/venue-only baseline 4.004. This baseline is not the incumbent count model.
  - Fit before 2025-01-01: 10510 training observations; 3436 later observations. Candidate MAE 3.613, league/venue-only baseline 4.092. This baseline is not the incumbent count model.
  - Fit before 2026-04-01: 10692 training observations; 1004 later observations. Candidate MAE 3.751, league/venue-only baseline 4.121. This baseline is not the incumbent count model.
  - Excluded 2026-08-23|ligue-1|paris sg|stade rennais, paris sg: fixture_or_team_history_unavailable. No opposite-venue fixture substitution.
- corners: 784 matched price rows; 0 excluded. Frozen calibrated model weight: 0.000.
  - Fit before 2024-01-01: 5513 training observations; 1694 later observations. Candidate MAE 2.708, league/venue-only baseline 2.731. This baseline is not the incumbent count model.
  - Fit before 2025-01-01: 5255 training observations; 1718 later observations. Candidate MAE 2.698, league/venue-only baseline 2.704. This baseline is not the incumbent count model.
  - Fit before 2026-04-01: 5346 training observations; 502 later observations. Candidate MAE 2.864, league/venue-only baseline 2.897. This baseline is not the incumbent count model.

## Decision

Team shots: keep the candidate for prospective evaluation. Improvement over the raw incumbent and aggregate profit do not establish a durable betting edge: the later period remains negative and worse than market probabilities. Do not select a profitable retrospective league/window and call that a validated strategy.

Corners: do not promote. The candidate does not consistently beat market probabilities; April calibration selected zero model weight. Positive ROI has not been established.

The separate parameters are saved as inactive research parameters. No live model routing, stakes, published selections, settlements, or scheduling were changed. The form-integrity repair is implemented locally and tested, but has not been deployed in this turn. No Vercel/Supabase work or paid provider calls are added by this research.

Next model-validation step: freeze these candidates, then collect prospective prices/predictions without changing parameters. Prioritize corners inputs that measure attacking style and pressure; fit their weights on earlier count data and test on a new period. Do not infer a profitable corners formula from StatsHub’s shots display.

## Verification and reproduction

88 relevant unit tests passed, including current/future-result leakage, archived-price cutoffs, same-day ordering, missing counts, exact club aliases, duplicate disagreement, rolling-form deduplication, and live signal/settlement protections.

Run `scripts/football-counts-opponent-research.py --observations <audit-observations.json> --output-dir <local-output-directory>` from the repository. The observations are produced by the existing football-counts-calibration-audit.py. Frozen parameters, coefficients, source hashes, full selections and results are in the complete report JSON.

Full private report: `C:\Users\44746\Documents\Codex\2026-09-05\re\outputs\counts-opponent-20260912-complete\report.json`
