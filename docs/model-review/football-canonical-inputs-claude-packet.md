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
- Corners canonical v0 beats current on aggregate common-sample and last-90 common-sample count MAE and Brier/log-loss.
- Team-shots canonical v1_market_nb adds capped 1X2 win-probability/game-state adjustment plus causal prior-data league negative-binomial O/U conversion. It improves Brier/log-loss, but recent count MAE is not yet better than current.
- No live policy or published pick logic has been changed yet; this remains research-only pending odds/CLV and recent-window validation.
- Corners v0 segment promotion check: `data/football-form/corners-v0-promotion-check.md` / `data/football-form/corners-v0-promotion-check.json`
- Segment gate read: partial research lane only. Passing leagues `epl, ligue-1, serie-a`; blocked leagues `bundesliga, la-liga`.
- Corners v0 publication config: `data/football-form/corners-v0-allowed-leagues.json`. The publisher/monitor reads this config instead of relying on a stale one-off report.
- Corners v0 CLV monitor schema/report: `data/football-form/corners-v0-clv-monitor.csv` / `data/football-form/corners-v0-clv-monitor.md`
- League YoY variance report: `data/football-form/league-yoy-variance.md` / `data/football-form/league-yoy-variance.json`
- EPL and Serie A show material shots/corners regime variance, so trailing-12-month normalization should be implemented before any football-form promotion.
- Lower-threshold YoY variance sensitivity: `data/football-form/league-yoy-variance-7pct.md` / `data/football-form/league-yoy-variance-7pct.json`
- At 7%, primary trailing-12-month candidates expand to `epl, la-liga, ligue-1, serie-a`; guarded/sparse candidates `bundesliga`.
- Team-shots last-90 diagnostic: `data/football-form/team-shots-last90-diagnostic.md` / `data/football-form/team-shots-last90-diagnostic.json`
- Cap-disabled team-shots lambda does not beat capped lambda in the recent window, so the cap is not the first suspect.

## Changes Since Previous Review

- The 15-day stale player-log issue is fixed. Hosted goalscorer refresh now checks freshness, refreshes stale leagues, writes health output only to temp, and hardens rebase/dirty-worktree handling.
- Added schema/freshness validation for canonical team-form outputs: row counts, required fields, critical coverage, duplicate keys, freshness, market coverage, and xG coverage warnings.
- Added date-versioned canonical CSV outputs and a manifest so model reports can record exactly which canonical data version they used.
- Added causal league-relative normalized fields for shots, corners, and xG. They use only prior league rows, not current-season full-sample means.
- Added common/canonical-only/full and last-90 sample splits to the canonical backtest report.
- Added a team-shots `canonical_form_v1_market_nb` research variant using the market-implied win probability gap as a capped game-state proxy and causal prior-data negative-binomial O/U calibration.
- Added a league year-over-year variance check to decide whether all-prior normalization is safe or trailing-12-month baselines are required.
- Added a corners v0 per-league promotion gate. Aggregate corners passed, but Bundesliga and La Liga fail the recent segment gate, so all-league promotion is blocked.
- Operationalised the corners v0 gate as an allowed-league config. Initial research publication is allowed only for EPL, Ligue 1, and Serie A; Bundesliga and La Liga stay blocked.
- Added a corners v0 CLV monitor schema with publication, 3h, 1h, close, CLV, time-to-kickoff, allowed-league blocking, and hard canonical-only guard fields.
- Ran the lower-threshold YoY variance sensitivity Claude requested. At 7%, La Liga and Ligue 1 also become primary trailing-12-month candidates; Bundesliga remains guarded/sparse because its primary shots/corners are just below threshold while xG is sparse/volatile.
- Ran the team-shots last-90 diagnostic. Cap-disabled lambda is worse than capped lambda, so cap tuning is not the first fix; recent canonical lambda still lags current in most leagues.

## Backtest Highlights

| Area | Sample | N | Current MAE | Canonical MAE | Probability gate | Read |
| --- | --- | ---: | ---: | ---: | --- | --- |
| corners v0 | common | 20655 | 2.7876 | 2.7492 | Brier ok, log-loss ok | aggregate pass only; segment gate decides publication |
| corners v0 | last_90_common | 570 | 2.6663 | 2.6309 | Brier ok, log-loss ok | recent window also passes |
| corners v0 | canonical_only | 2 | - | 9.8308 | no baseline | sample is tiny; add confidence guard, do not infer coverage safety |
| team-shots v1_market_nb | common | 2464 | 3.7425 | 3.7262 | Brier ok, log-loss ok | NB helps O/U calibration |
| team-shots v1_market_nb | last_90_common | 1140 | 3.7320 | 3.7699 | Brier ok, log-loss ok | probability passes, count MAE does not; keep research-only |
| team-shots v1_market_nb | canonical_only | 38850 | - | 3.5336 | no baseline | coverage looks usable, still needs segment gates |

## Normalization Read

- 10% material threshold: primary trailing-12-month candidates `epl, serie-a`; guarded/sparse candidates `bundesliga`.
- 7% sensitivity threshold: primary trailing-12-month candidates `epl, la-liga, ligue-1, serie-a`; guarded/sparse candidates `bundesliga`.
- This supports testing per-(league, metric) trailing normalization for La Liga before re-opening its corners v0 segment gate.
- Keep Bundesliga guarded first: shots/corners are just below the 7% line, while xG variance is sparse and should not be blindly promoted into the model.

## Team-Shots Last-90 Diagnostic

- Full common MAE: current `3.7425`, canonical capped `3.7262`.
- Last-90 common MAE: current `3.7321`, canonical capped `3.7699`, cap disabled `3.7948`.
- Cap-disabled recent MAE beats capped recent MAE: `no`.
- Recent canonical capped lags current in: `bundesliga, epl, ligue-1, serie-a`.
- Cap hurts by league only in: `serie-a`.
- Read: do not tune the cap first. The recent count issue is a canonical lambda / normalization problem until proven otherwise.

## Corners V0 Segment Gate

- All-league research promotion: fail.
- Passing leagues for partial research lane: epl, ligue-1, serie-a.
- Active allowed-league config: `epl, ligue-1, serie-a`.
- Blocked leagues until recent segment calibration is fixed: bundesliga, la-liga.
- Canonical-only hard block: on; sample N=2.
- Do not publish canonical-only picks. Do not publish Bundesliga or La Liga corners v0 picks yet.

## Findings From Current Repo

- No hard input-audit issues detected by the first pass.

## Proposed Implementation Order

1. Keep the stale-player-log fix in production workflows and monitor the next scheduled run.
2. Keep corners v0 research publication restricted by `corners-v0-allowed-leagues.json`: EPL, Ligue 1, and Serie A only.
3. Keep the corners confidence guard as a hard cutoff: canonical-only fixtures are blocked, not flagged.
4. Implement/test per-(league, metric) trailing-12-month normalization, starting with EPL/Serie A and re-testing La Liga because it crosses the 7% sensitivity threshold.
5. Re-run corners segment gates after normalization. Only then consider adding La Liga or Bundesliga to the allowed-league config.
6. Hold team-shots. The cap-disabled diagnostic did not fix last-90 count MAE, so investigate canonical lambda/normalization before any odds/CLV join.
7. Once team-shots recent count MAE is explained or fixed, then run segment gates and the odds/CLV join.

## Questions For Follow-up Review

1. Does the allowed-league config plus hard canonical-only block cover the corners v0 research publication risk without adding more live-policy complexity?
2. Given the 7% YoY sensitivity, should La Liga get per-metric trailing-12-month normalization before any per-league model calibration is considered?
3. Team-shots cap-disabled recent MAE is worse than capped recent MAE. What lambda diagnostic should run next: normalization replay, largest-error input spot check, or current-model feature comparison?
4. Should Bundesliga remain guarded/sparse until xG coverage improves, or should shots/corners trailing normalization be tested there despite falling just below the 7% primary threshold?
5. Are the CLV de-promotion rules sufficient now that the monitor records time-to-kickoff and writes pre-close rows?
