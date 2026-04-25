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
- Corners v0 CLV monitor schema/report: `data/football-form/corners-v0-clv-monitor.csv` / `data/football-form/corners-v0-clv-monitor.md`
- League YoY variance report: `data/football-form/league-yoy-variance.md` / `data/football-form/league-yoy-variance.json`
- EPL and Serie A show material shots/corners regime variance, so trailing-12-month normalization should be implemented before any football-form promotion.

## Changes Since Previous Review

- The 15-day stale player-log issue is fixed. Hosted goalscorer refresh now checks freshness, refreshes stale leagues, writes health output only to temp, and hardens rebase/dirty-worktree handling.
- Added schema/freshness validation for canonical team-form outputs: row counts, required fields, critical coverage, duplicate keys, freshness, market coverage, and xG coverage warnings.
- Added date-versioned canonical CSV outputs and a manifest so model reports can record exactly which canonical data version they used.
- Added causal league-relative normalized fields for shots, corners, and xG. They use only prior league rows, not current-season full-sample means.
- Added common/canonical-only/full and last-90 sample splits to the canonical backtest report.
- Added a team-shots `canonical_form_v1_market_nb` research variant using the market-implied win probability gap as a capped game-state proxy and causal prior-data negative-binomial O/U calibration.
- Added a league year-over-year variance check to decide whether all-prior normalization is safe or trailing-12-month baselines are required.
- Added a corners v0 per-league promotion gate. Aggregate corners passed, but Bundesliga and La Liga fail the recent segment gate, so all-league promotion is blocked.
- Added a corners v0 CLV monitor schema with publication, 3h, 1h, close, CLV, and hard canonical-only guard fields.

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

- Use trailing-12-month baselines before promotion for primary shots/corners metrics in: epl, serie-a.
- Treat trailing xG as guarded/sparse-only first in: bundesliga.
- La Liga and Ligue 1 are within the 10% material threshold on the checked primary metrics, so all-prior baselines are less risky there.

## Corners V0 Segment Gate

- All-league research promotion: fail.
- Passing leagues for partial research lane: epl, ligue-1, serie-a.
- Blocked leagues until recent segment calibration is fixed: bundesliga, la-liga.
- Canonical-only hard block: on; sample N=2.
- Do not publish canonical-only picks. Do not publish Bundesliga or La Liga corners v0 picks yet.

## Findings From Current Repo

- No hard input-audit issues detected by the first pass.

## Proposed Implementation Order

1. Keep the stale-player-log fix in production workflows and monitor the next scheduled run.
2. Run corners v0 odds/CLV join first, but only for passing leagues: EPL, Ligue 1, and Serie A.
3. Keep the corners confidence guard as a hard cutoff: canonical-only fixtures are blocked, not flagged.
4. Implement trailing-12-month normalization for EPL/Serie A primary shots/corners before any team-shots promotion.
5. Diagnose Bundesliga and La Liga corners v0 recent-segment failures before allowing all-league research publication.
6. Add win-prob gap bucket calibration for team-shots; negative binomial improves O/U probability but recent count MAE still lags current.
7. Then do the team-shots odds/CLV join and keep it research-only until the recent-window count issue is explained or fixed.

## Questions For Follow-up Review

1. Segment check changed the corners read: EPL/Ligue 1/Serie A pass, Bundesliga/La Liga fail recent segment gates. Should partial research publication be allowed only for passing leagues?
2. For Bundesliga and La Liga corners v0, should we tune per-league calibration, recent-pressure weight, or keep the current corners lane as-is for those leagues?
3. Team-shots v1_market_nb improves Brier/log-loss but last-90 count MAE is worse than current. Should we tune the capped game-state lambda, split by win-prob bucket, or hold the model entirely?
4. For EPL/Serie A, should trailing-12-month normalization replace all-prior normalization globally, or only for shots/corners primary metrics?
5. Is the CLV monitor schema now sufficient for corners v0 live research tracking and de-promotion rules?
