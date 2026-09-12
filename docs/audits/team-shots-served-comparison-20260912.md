# Fixed opponent shots: served-model comparison and forward activation

The candidate is now connected to a separate prospective shadow ledger. Fixed
weights are retained; no fitting occurs in the scheduler or website. Public v4
routing is unchanged. Hypothetical flat 1u results are not real-money stakes.

## Matched archived-price replay

| Period | Candidate bets | Candidate ROI | Served v4 bets | Served v4 ROI |
|---|---:|---:|---:|---:|
| May 9–July 31 | 49 | +28.42% | 23 | +29.09% |
| August–September 7 | 48 | -3.36% | 9 | +1.41% |
| Combined | 97 | +12.69% | 32 | +21.31% |

Candidate: 59W/38L, +12.310u. Served v4: 21W/11L, +6.818u.
352 matched post-calibration contracts. The reversed PSG/Rennes archived
fixture is excluded. Both lanes see the same paired bookmaker prices and
capture-day history; each independently keeps its strongest eligible selection
per fixture. Actual v4 code supplies its hierarchical dispersion, shading,
18% logit model weight, 1X2 as-of fallback and matchday 4–6 restrictions.

Current v4 July parameters are used retrospectively: its May/June comparison
is **not** out-of-sample. Archived 1X2 coverage is reported in the JSON; missing
prices use v4's real fallback. These results do not prove either future edge.
Candidate has more historical volume and units, but lower ROI and a negative
latest period. Keep v4; collect genuinely new candidate evidence.

## Operation

- Config: `data/team-shots/team-shots-opponent-config.json`, coefficients copied
  unchanged from the registered opponent-counts research artifact.
- Scanner: `scripts/team-shots-opponent-shadow.py`. Standard library only.
  Reuses current captures; no additional API calls, cron frequency, or database
  writes. Files join the existing team-shots hosted snapshot.
- New selections: future kickoff within 24h, prices at most 3h old, same
  bookmaker Over/Under pair within 15 minutes, half-lines, six prior matches,
  registered top-five leagues and minimum 3% model EV. One selection per fixture.
- Publication time is the actual scan; the price timestamp is preserved.
  Previously registered terms and losses are immutable across repeat scans.
- Settlement and closing prices reuse existing local archives/helpers.
  Missing outcomes stay pending. No retroactive publication of replay bets.
- Monitor: `/model-monitor/team-shots#opponent-shots`, pending first, W/L,
  hypothetical P/L and forward-only ROI. No extra polling.
- Existing daily/hourly football-count workflow runs inference and settlement.
  Weekly report includes fresh forward W/L/ROI/pending counts. The fixed policy
  raises a manual review flag at 150 settled fixtures and eight weeks; promotion
  still requires ROI/CLV/calibration review and is never automatic.

Validation: seven focused tests covering timestamps, stale prices, same-book
pairing, immutable first picks/losses, settlement idempotence, future-data
exclusion and numerical parity against original research. No outcome or signal
was changed to improve the reported ROI.
