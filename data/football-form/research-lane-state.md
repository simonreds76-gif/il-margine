# Football Research-Lane State

Generated: `2026-04-25T22:19:15Z`

This is the single operational readout for football research lanes. It does not change live picks by itself.

| Market | Model | State | Allowed leagues | Canonical-only | Monitor | Last gate | Next action | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| corners_total | canonical_form_v0 | research_partial | epl, ligue-1, serie-a | blocked | data/football-form/corners-v0-clv-monitor.md | 2026-04-25T19:42:49Z | Test total-corners calibration/pressure correction for Bundesliga and La Liga. | Pure home/away redistribution cannot move total O/U. |
| team_shots | canonical_form_v1_market_nb | deprecated_reference | la-liga | blocked | data/football-form/team-shots-v1-clv-monitor.md | 2026-04-25T19:43:56Z | Keep for backtest comparison only. | V1 passed only La Liga. |
| team_shots | canonical_form_v2_pooled_opp_nb | deprecated_reference | bundesliga, la-liga, ligue-1 | blocked | data/football-form/team-shots-v2-clv-monitor.md | 2026-04-25T19:44:33Z | Keep for backtest comparison only. | V2 was superseded by v3 EMA20. |
| team_shots | canonical_form_v3_ema20_nb | research_all_leagues | bundesliga, epl, la-liga, ligue-1, serie-a | blocked | data/football-form/team-shots-v3-ema20-clv-monitor.md | 2026-04-25T22:19:15Z | Watch CLV passively; do not unblock canonical-only fixtures. | Clean canonical EMA20 passes all five league segment gates. |

## Current Rules

- Fail closed if an allowed-league config is missing or malformed.
- Publish only leagues listed in the model's allowed-league config.
- Canonical-only fixtures remain blocked until segment calibration explicitly passes.
- Pause a lane if CLV or rolling Brier de-promotion rules fire.

## Latest Diagnostics

- `data/football-form/team-shots-v1-promotion-check.md`
- `data/football-form/team-shots-v2-promotion-check.md`
- `data/football-form/team-shots-v3-ema20-promotion-check.md`
- `data/football-form/corners-v0-venue-diagnostic.md`
- `data/football-form/corners-total-diagnostic.md`
- `data/football-form/team-shots-v1-clv-monitor.md`
- `data/football-form/team-shots-v2-clv-monitor.md`
- `data/football-form/team-shots-v3-ema20-clv-monitor.md`

## Diagnostic Reads

- Team-shots v3 replaces v2 as the active research candidate: v3 allows all five leagues while canonical-only fixtures remain blocked.
- V1 and v2 remain only as reference variants.
- V3 uses clean causal EMA20 fields generated inside the canonical form table, not a proxy blend with current model output.
- Corners blocked leagues do not have the team-shots venue-concession bug. A symmetric home/away correction does not change total corners, so the next test must target total-corners calibration or pressure.
