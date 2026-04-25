# Football Research-Lane State

Generated: `2026-04-25T19:45:00Z`

This is the single operational readout for football research lanes. It does not change live picks by itself.

| Market | Model | State | Allowed leagues | Canonical-only | Monitor | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| corners_total | canonical_form_v0 | research_partial | epl, ligue-1, serie-a | blocked | data/football-form/corners-v0-clv-monitor.md | Bundesliga and La Liga remain blocked after recent segment gate and venue diagnostic. |
| team_shots | canonical_form_v1_market_nb | research_partial | la-liga | blocked | data/football-form/team-shots-v1-clv-monitor.md | Conservative research config. V1 passes only La Liga. |
| team_shots | canonical_form_v2_pooled_opp_nb | candidate_partial | bundesliga, la-liga, ligue-1 | blocked | - | Diagnostic/promotable candidate only. EPL and Serie A remain blocked. |

## Current Rules

- Fail closed if an allowed-league config is missing or malformed.
- Publish only leagues listed in the model's allowed-league config.
- Canonical-only fixtures remain blocked until segment calibration explicitly passes.
- Pause a lane if CLV or rolling Brier de-promotion rules fire.

## Latest Diagnostics

- `data/football-form/team-shots-v1-promotion-check.md`
- `data/football-form/team-shots-v2-promotion-check.md`
- `data/football-form/corners-v0-venue-diagnostic.md`
- `data/football-form/team-shots-v1-clv-monitor.md`
