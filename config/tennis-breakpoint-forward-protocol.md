# Frozen forward paper specification: ATP total break-point chances, model C (v2), Grosvenor criterion 2100114880

Paper only: zero real stake, no Telegram or other alerts, live models unchanged. Model C is frozen exactly as v2: `frozen-bp-params.json` sha e14c32c46f4d…. There is no refitting at any point.

## 1. Activation
- **Freeze before T0:** this file, `bp_c_forward.py` and `frozen-bp-params.json` are hashed and timestamped before activation time T0.
- **What counts:** only quotes captured after T0. Quotes, forecasts or results from before T0 (including the 94 historical quotes) are never relabelled as forward.

## 2. Eligibility (all must hold; otherwise logged with a reason and no forecast)
- **Scope:** ATP singles, best of three. Levels: 250/500, Masters, and Grand Slam qualifying; main draw and qualifying both included.
- **Excluded:** Challenger, WTA, team events, Finals and best-of-five. They are outside C's fit scope.
- **Market:** Grosvenor criterion 2100114880 (full-match Total Break Points), with both Over and Under prices present, a half-integer line, the offer open, and the event NOT_STARTED with capture time earlier than the scheduled start.
- **Identity:**
  - Grosvenor event ID mapped to exactly one native ATP pair (both participant IDs exact), plus that edition's surface, level and phase from the native schedule.
  - Ambiguous or missing mapping is logged as UNMAPPED.
  - A change of opponent counts as a new fixture identity, never a continuation.
- **Primary quote:** the first eligible capture per event ID after T0.
  - If that capture holds several lines, use the line whose proportionally de-vigged Over probability is closest to 0.5; on a tie, the lower line.
  - Later captures are logged as secondary context only.

## 3. Forecast (as of the capture; immutable)
- **History:** only validated completed results dated ≤ capture date (UTC) − 2 days that are actually in the store when the forecast is made. Record the snapshot hash, rows used and last result date. Anything later is never backfilled into a stored forecast.
- **Computation:** `bp_c_forward.forecast()`, with frozen constants and NB2 α = 0.1122885.
  - P(Over L) = `nbinom.sf(floor(L), n = 1/α, p = n/(n + μ))`, with the log-space cumulative cross-check stored.
  - If μ is not finite or ≤ 0, there is no forecast.
- **Timing:** a forecast is valid only if it is written before the scheduled start. Later ones are kept but labelled LATE and excluded from the primary cohort.
- **Stored per forecast (append-only):**
  - identity: fixture and event IDs, capture time, line and both prices;
  - market: de-vigged Over probability;
  - model state: as-of Elo favourite probability and bin, Ê and its fallback tier, λ_cell, the four player ratios, μ, α, P(Over) and EV;
  - decision: the hypothetical-bet flag;
  - hashes: code, parameters and history snapshot.

## 4. Hypothetical decision and outcomes
- **Bet rule:** Over at 1u if P_C(Over) × over − 1 ≥ 0.05. Every bet is hypothetical.
- **Outcome:** labelled COMPLETED_RESEARCH_OUTCOME (native w_bpFaced + l_bpFaced, after the strict v2 validation). It is never treated as bookmaker grading.
- **Excluded from the primary cohort:** retirement, walkover, invalid statistics or no result, each counted by reason. Grosvenor's own grading or void status is stored verbatim if it is ever observable.

## 5. Metrics, kept separate
- **All forecasts (calibration):**
  - count log score, mean bias, inclusive interval coverage at 50 / 80 / 90, and randomised PIT with stable match-ID uniforms;
  - Over-outcome Brier and log loss for C against the de-vigged market, paired, with edition-cluster intervals;
  - calibration intercept and slope of P(Over);
  - monthly bias, as a descriptive drift monitor only.
- **Selection:** bets, W/L, stake, profit and ROI, from the first settled bet, with sample caveats and edition-cluster intervals once there are at least 8 editions.

## 6. Review points (pre-declared)
- **Integrity check after the first 20 settled fixtures:** mapping errors, LATE forecasts, history lag, and Grosvenor definition or settlement (if observable). A systematic definition mismatch stops the track.
- **Interim, descriptive only:** at 100 settled.
- **First formal review:** at 300 settled from at least 12 editions. Report every section-5 metric. **No promotion or real staking is considered unless** C's paired Over log loss against the market is below zero with the interval excluding zero, **and** C's 80% coverage is within ±3 points with no half-year |bias| above 0.5.
- **Second formal review:** at 600 settled.
- **Limitation:** every review is descriptive about ROI. The 300 and 600 points are review milestones, not proof thresholds.

## 7. Online reproduction of C without refitting (sufficient statistics)
- **Frozen constants** (`frozen-bp-params.json`):
  - the λ_cell table (cell → surface → global);
  - the exposure table (cell × bin → surface × bin → bin → global);
  - k⁰c = 58.81, k⁰g = 84.16, k¹c = 51.05, k¹g = 68.27; α = 0.1122885;
  - 730-day window and 2-day lag; Elo with K = 32, initial 1500, day-batched, starting 2020-01-01; bins [.5, .6, .7, .8, .9, 1].
- **History state:** the validated completed history from 2020-01-01. Elo is cumulative from that date, and pass-1 expectations need pass-0 ratios at each past match, which reach back a further 730 days. Equivalent append-only state:
  - Elo ratings;
  - per-player lists of (date, break points faced, pass-1 concession expectation, pass-1 creation expectation). Each new result's pass-1 expectations use both players' pass-0 ratios as of its own result date − 2, computed once at ingest.
  - Invalid rows are dropped from all state, as in v2.
- **Parity:** `bp_c_forward.py parity` rebuilt all 94 historical quotes outcome-free, with the target and every later result truncated away and player order swapped on 47 rows.
  - μ and P(Over) match v2 within 5e-7 (v2 CSV rounding to six decimals);
  - Ê matches within 3e-7;
  - every bet flag is identical;
  - the NB tail cross-check agrees within 8e-15.
  - The history builder therefore runs with target outcomes unavailable.

## Installed integration details (frozen before activation)
Implementation: tennis_breakpoint_model.py, tennis_breakpoint_forward.py, tennis_breakpoint_history_build.py and tennis-breakpoint-c-frozen.json. Registration hashes these and eligibility/settlement dependencies. Byte-level mismatches stop new capture.
The existing raw-price collector invokes capture immediately after ingestion if local registration exists. Daily/admin hooks also capture, then refresh isolated history; nightly joins results. No new schedule or alerts. Cloud hosts without registration collect evidence only.
30-minute quote age, history timestamp before quote and seven-day source freshness are explicit operational guards. Earlier stale quotes are counted per forecast; health exclusion counts are per-run. Event-plus-pair and exact native edition/round/pair dedup permit replacement opponents.
Forward outcomes use native OnCourt counts and strict v2 validation, not independently verified bookmaker grading. UTC-date mismatches remain unresolved.
Calibration slope/intercept is unavailable below100 fixtures or20 per outcome class; diagnostic only. Fixed-seed edition bootstrap uses2000 resamples after8 editions. Bias means predicted minus actual; revisions and excluded selected bets are explicit.
