# Goalscorer roster correction — 2026-09-08

Confirmed-lineup forecasts now allocate team non-penalty expected goals across the playing squad, independently of bookmaker quote availability. Only real quotes are emitted. Existing model rates, opponent adjustments, penalty logic and website layout remain in place.

The lineup collector preserves substitute identities and position groups from the same response it already fetches. Explicit reserve goalkeepers are excluded. A named reserve without Understat history uses the existing position prior; `roster_prior_players` records the count. Missing starter identities, missing reserve roles or malformed squads block public publication. Incomplete legacy calculations remain separately identified for diagnosis.

Validation: seven integration tests cover quote removal, keeper inclusion, roster priors, incomplete squads, duplicate names and the Lab gate. A structural replay of Rayo Vallecano–Alaves (20 August) holds Jorge de Frutos at 26.3072% with a full quote list and a single quote. The old incomplete-population calculation moved from 29.0426% to 77.0769%. Replay prices were synthetic and substitute metadata was fetched retrospectively: this is a correctness check, not a profitability or out-of-sample calibration test. Higher ROI is not established.

Version: `goalscorer_v1_roster_20260908`, raw calibration. Existing issued bets are not rewritten. No new schedule, endpoint, paid feed, polling interval or ISR refresh is introduced. Hosted GitHub Actions do the calculation; the website consumes its existing JSON feed. Automatic Vercel deployments are disabled specifically for the pipeline branch `golden-with-speed-insights`, preserving the current production deployment and other release branches.
