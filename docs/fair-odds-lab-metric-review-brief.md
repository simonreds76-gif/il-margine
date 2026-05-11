# Fair Odds Lab Metric Review Brief

Context for Claude/design-model review.

We have added public explanation context to the Goalscorer Fair Odds Lab without changing the model weights.

## Implemented in this slice

- `scripts/generate-fair-odds-lab.py` accepts `--team-match-base`.
- Goalscorer workflows build a temporary canonical football form layer before generating the public artifact.
- Each public signal now gets:
  - `metrics.recent_team_form`
  - `metrics.opponent_recent_defence`
- These fields are built from causal completed-match rows only.
- The public page renders those fields in the Opponent Profile panel as tiered indicators with short notes.

Example artifact shape:

```json
{
  "recent_team_form": {
    "tier": "Strong",
    "window": 5,
    "matches": 5,
    "through_date": "2026-05-01",
    "xg_for_avg": 2.05,
    "xg_against_avg": 0.92,
    "xgd_per90": 1.13,
    "shots_for_avg": 14.8,
    "shots_against_avg": 11.8,
    "sot_for_avg": 5.4,
    "sot_against_avg": 4.6,
    "corners_for_avg": 4.2,
    "corners_against_avg": 6.2
  },
  "opponent_recent_defence": {
    "tier": "Average",
    "window": 5,
    "matches": 5,
    "xg_against_avg": 1.17,
    "shots_against_avg": 9.4
  }
}
```

## Review questions

1. Are the public labels right?
   - `Recent team form`
   - `Opponent recent defence`
   - Current notes: `Last 5: +1.13 xGD/90 (2.1 xG for, 0.9 against)` and `Last 5: 1.2 xGA, 9.4 shots conceded`.

2. Are the tier thresholds sensible for public display?
   - Recent team form by last-5 xGD/90:
     - `Strong >= +0.65`
     - `Positive >= +0.25`
     - `Average >= -0.25`
     - `Quiet < -0.25`
   - Opponent recent defensive weakness by last-5 xGA:
     - `High >= 1.70`
     - `Positive >= 1.35`
     - `Average >= 1.00`
     - `Low < 1.00`

3. Should these remain explanation-only for now, or should they influence public ranking later?
   - Current recommendation from Codex: explanation-only until we have tracked public goalscorer signal settlement volume.

4. Which tipster-style metrics are currently not available from our repo data?
   - Set-piece goals per game.
   - Set-piece xG for/against.
   - Injury/team-news missing automatic starters.
   - Last head-to-head xG narrative.

5. What is the safest next data upgrade?
   - Codex recommendation: keep using current xG/shots/corners layer first; add a provider for injuries/set-pieces only after launch, because those require external data quality/licensing checks.

## Super Sub / Sub On Play On note

The public page now explains bookmaker-dependent Super Sub upside. The model still prices the named player only.

Important implementation constraint:

- Current automatic goalscorer settlement can verify whether the named player scored.
- It cannot reliably verify whether the direct replacement scored, because our stored player logs do not contain substitution-event mapping.
- Do not count Super Sub wins automatically until we add a verified match-event source that links substituted player -> direct replacement -> scorer.

Recommended copy stance:

- Treat Sub On Play On as extra bookmaker-dependent protection, not part of the model.
- Mention bet365/Sub On Play On for SEO, but always say availability depends on the market icon and bookmaker rules.
- Historical highlights should remain named-player wins unless a future settlement note explicitly marks a verified replacement win.
