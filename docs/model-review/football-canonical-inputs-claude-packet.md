# Claude Review Packet: Football Canonical Input Layer

We are improving Il Margine football derivative models without adding distracting products.
Please audit the plan and challenge any weak assumptions before we wire it into production.

## Current Goal

Build a canonical football team/player form layer that can feed team shots, corners, and goalscorer models.
Do not build steam tracking, public xG tables, or a Dixon-Coles product yet.

## Audit Artifacts

- Markdown audit: `data/football-form/input-audit.md`
- JSON audit: `data/football-form/input-audit.json`

## Implemented Artifacts So Far

- Team-match base table: `data/football-form/team-match-base.csv`
- Causal rolling team-form table: `data/football-form/team-rolling-form.csv`
- Team-form generation report: `data/football-form/team-form-report.md`
- Team-form table now preserves raw values plus causal league-relative normalized fields.
- These artifacts are not wired into live model selection yet.
- Version manifest: `data/football-form/team-form-manifest.json`
- Schema/freshness validation report: `data/football-form/team-form-validation.md` / `data/football-form/team-form-validation.json`
- Causal player rolling-form table: `data/football-form/player-rolling-form.csv`
- Player-form generation report: `data/football-form/player-form-report.md`
- Player-log freshness health: `data/football-form/player-log-health.json`
- Goalscorer model smoke test: `data/football-form/goalscorer-player-log-smoke.md`
- Research backtest summary: `data/football-form/canonical-backtest-summary.csv`
- Research backtest report: `data/football-form/canonical-backtest-report.md`
- Corners canonical v0 beats current on common-sample count MAE and Brier/log-loss.
- Team-shots canonical v1_market adds capped 1X2 win-probability/game-state adjustment and beats current on common-sample count MAE and Brier/log-loss across tested O/U lines.
- No live policy or published pick logic has been changed yet; this remains research-only pending odds/CLV and recent-window validation.

## Changes Since Previous Review

- The 15-day stale player-log issue is fixed. Hosted goalscorer refresh now checks freshness, refreshes stale leagues, writes health output only to temp, and hardens rebase/dirty-worktree handling.
- Added schema/freshness validation for canonical team-form outputs: row counts, required fields, critical coverage, duplicate keys, freshness, market coverage, and xG coverage warnings.
- Added date-versioned canonical CSV outputs and a manifest so model reports can record exactly which canonical data version they used.
- Added causal league-relative normalized fields for shots, corners, and xG. They use only prior league rows, not current-season full-sample means.
- Added a team-shots `canonical_form_v1_market_*` research variant using the market-implied win probability gap as a capped game-state proxy.

## Findings From Current Repo

- No hard input-audit issues detected by the first pass.

## Proposed Implementation Order

1. Keep the stale-player-log fix in production workflows and monitor the next scheduled run.
2. Split canonical backtests into full-window and last-90-day windows for Brier/log-loss promotion gating.
3. Add odds/CLV joins for team-shots v1_market and corners v0 before any promotion.
4. Test negative-binomial probability calibration for team shots versus current Poisson O/U conversion.
5. Only then wire canonical inputs into research monitor lanes; do not move official policy yet.

## Questions For Follow-up Review

1. Does the capped market-implied game-state adjustment look mathematically defensible for team shots, or should it be learned/fit instead of hand-capped?
2. Is the causal league-relative normalization enough for v1, or should normalization use trailing-12-month league baselines instead of all prior league rows?
3. Should team-shots O/U probabilities move to negative-binomial calibration now that count MAE improved but dispersion is still likely non-Poisson?
4. For promotion, should the block be both full-window and last-90-day Brier/log-loss, then CLV watch in research?
5. Which odds/CLV join should be done first: team-shots v1_market or corners v0?
