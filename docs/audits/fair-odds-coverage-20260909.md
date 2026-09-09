# Daily Fair Odds Lab coverage correction — 9 September 2026

Version: `daily_shrunk_rates_v2_20260909`.

The public snapshot at 12:04 UTC contained 110 starters across five fixtures,
but only 60 model probabilities and 28 Bet365 quotes. Missing fallback forecasts,
incomplete roster allocation and club aliases caused avoidable gaps.

The daily forecast now uses the existing player-rate estimator (900-minute
shrinkage towards positional rates), expected minutes, confirmed role adjustment
and the existing team non-penalty goal budget. Weights are normalized across the
sporting squad, independently of bookmaker quote availability. The 10% unallocated
team share and existing penalty component are retained. These are reused model
parameters, not weights selected to maximize this snapshot's apparent value.

Identified players with no history receive a labeled positional estimate. If a
starting player needs that prior, roster status remains `estimated_roster` and
cannot pass the confirmed-roster public tip gate. Limited-data daily estimates
do not generate value gaps or enter the first-official-comparison ledger.

Legacy tip-selection probabilities retain their existing calculation. Daily
comparisons carry the new version in forecast files and evaluation records.

Local replay with the saved historical logs and fetched lineup/roster identities:

| Check | Before | After |
| --- | ---: | ---: |
| Outfield players with estimates | 60/100 | 100/100 |
| Matched Bet365 quotes | 28 | 57 |
| Joël Schingtienne decimal fair odds | 410.79 | 41.33 |
| Albion Rrahmani decimal fair odds | hidden | 4.82 (limited data) |
| Akor Adams decimal fair odds | hidden | 2.95 (limited data) |

The quote improvement reuses captured prices through canonical club names.
Raw captured quotes are also eligible independently of model matching; absent
quotes remain absent. Goalkeepers remain explicitly unpriced by the outfield
model. No added bookmaker polling or server-side prediction requests.

Validation covers quote independence, squad completeness, duplicate identities,
new-starter priors, team-rate budget conservation, history shrinkage, penalty
review, club aliases, stale/changed lineups and explicit missing-price reasons.
This is a structural and coverage correction, not proof of profitable ROI.
Assess this version separately on prospectively frozen official comparisons.
