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
- These artifacts are not wired into live model selection yet.
- Causal player rolling-form table: `data/football-form/player-rolling-form.csv`
- Player-form generation report: `data/football-form/player-form-report.md`
- Player-log freshness health: `data/football-form/player-log-health.json`
- Goalscorer model smoke test: `data/football-form/goalscorer-player-log-smoke.md`
- Research backtest summary: `data/football-form/canonical-backtest-summary.csv`
- Research backtest report: `data/football-form/canonical-backtest-report.md`
- Initial result: corners canonical v0 beats current on common-sample Brier/log-loss; team-shots v0 is not good enough on count accuracy yet.

## Findings From Current Repo

- WARN [goalscorer_player_logs]: Latest player-log row is 15 days old (2026-04-10).

## Proposed Implementation Order

1. Build `data/football-form/team-match-base.csv` from existing FBref/Football-Data sources.
2. Build `data/football-form/team-rolling-form.csv` with causal rolling 5/10-game features.
3. Build `data/football-form/player-rolling-form.csv` from goalscorer player logs.
4. Backtest team-shots with canonical inputs versus current embedded rolling logic.
5. Backtest corners with added pressure features before any live/research promotion.
6. Backtest goalscorer with canonical team/player shares, then keep it research unless calibration improves.

## Questions For Review

1. Are the proposed canonical team fields sufficient for team shots and corners, or should we add more pressure proxies before backtesting?
2. Should the first canonical layer preserve both raw and normalized xG/shots/corners values per league?
3. What is the cleanest way to compute opponent-strength adjustment without importing a weak or noisy Elo proxy?
4. For corners, should xG/shots/possession enter as direct features or only as sanity/segmentation filters?
5. Which success gate should block production: Brier/log-loss, CLV, or a combined rule?
