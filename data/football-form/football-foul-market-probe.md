# Odds-API.io Football Foul Market Probe

Generated: 2026-07-15T11:28:25Z
Status: **NO_FOUL_MARKETS_RETURNED**
Bookmaker: Bet365
Events probed: 10
HTTP requests: 2

The documented `/v3/odds/multi` endpoint returns every market available to the account for the requested bookmaker. No separate REST market selector or team-fouls tier endpoint is documented.

## Foul labels

- None returned in this bounded event sample.

## Card / booking controls

- None returned.

## Decision

- The configured Bet365 feed did not return a foul market in the probed events. M0 remains blocked.
- A market shown on Bet365's website is not automatable unless paired prices are returned by the feed.
- No Team Fouls model signal is authorized by this probe.
