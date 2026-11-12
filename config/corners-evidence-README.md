# Corners opportunity evidence v1

Authorized 12 November 2026. This archives the existing Corners v3 scorer; it
does not create a new prediction model or change a selection, stake or alert.
The current production publisher and its frozen dependencies remain unchanged.

The existing daily and hourly `refresh-football-count-evidence.py` call retains
every available bookmaker/line pair, both forecasts and all no-bet reasons in
`data/football-form/corners-candidate-evidence-v1/observations`. Input contexts,
source hashes, code/parameter snapshots and scan receipts are separate objects.
No-bets enter the existing bounded result queue. Result observations/corrections
are append-only; issued ledgers are never written by this module.

## Interpretation

- This is genuine prospective evidence only after registration, an unchanged
  saved board passes replay, both quotes are fresh before the recorded kickoff,
  the same-book pair is coherent, and the required inputs exist. Historical
  verification packets are never copied into this archive.
- The first eligible observation per ordered league-season fixture, line and
  bookmaker is the default future comparison cohort. Reschedules retain that
  identity. All later observations remain available separately. Distinct lines
  and bookmakers are correlated opportunities, not independent fixtures.
- A descriptive primary line uses the closest pair of implied probabilities,
  then the lower line on ties. This rule uses no outcomes. A future full strategy
  comparison must freeze its own chronological evaluation/selection protocol;
  it may not retrospectively choose the best timestamp or line.
- Half-lines have zero push probability. Integer/quarter quotes are retained
  with explicit exclusions because v3 does not produce their full payoff
  distribution. Missing forecasts are not fabricated.
- The current adapters retain normalized raw quotes rather than every original
  provider field. Per-record gaps enumerate missing market/selection IDs and
  status flags. Kickoff comes from the saved bookmaker feed; prices are recorded
  quotes, not certified executable. Abandoned/ambiguous matches require review.
- Inputs are observed at capture time. Older file contents/dates are not evidence
  that they existed before that observation. Rounded board parity is within
  5.1e-7 for the full-precision probability; published fields match exactly.
- Zero current opportunities is different from a capture error. See
  `capture-status.json`, latest quote time, run universe and exclusion counts.
  No live-operation claim until a genuine capture and settlement are verified.

## Reproducible verification

`python -m unittest scripts.tests.test_corners_candidate_evidence`

Cloud contract checks also replay the current saved source files into temporary
output paths, run the archive twice and verify issued ledgers and parameters
have no diff. No external market requests or Telegram calls are made.

The first future Fable comparison should compare paired log loss/Brier and
count bias before ROI, reporting the entire common opportunity set (including
zero P/L for no-bets), W/L/exposure/pending and uncertainty clustered by fixture
and time. Existing selected-only historical studies remain separate.
