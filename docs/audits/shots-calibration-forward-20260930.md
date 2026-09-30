# Frozen calibration forward integration

The user authorised connecting the existing calibration on 30 September.
This is research with zero real stake. It is not a replacement for a live model.

The artifact `data/team-shots/shots-market-offset-v1.json` freezes the final
diagnostic fold, trained strictly before 12 September: weight
0.26634934409525224, intercept 0.07481677660354566. No new fitting or threshold
search was performed. The September improvement was previously inspected
historical evidence and did not consistently beat the market probability score.

The existing collector now registers cohort `paired-market-offset-20260930-v2`.
It uses the same frozen Opponent raw probability and same-book proportional
market probability, retains first-scan no-bet decisions and selects at most one
hypothetical 1u bet per model and fixture at the frozen 3% EV threshold.
The controls keep their original rules. Both quotes must be before kickoff,
within 24 hours of kickoff, fresh under the existing six-hour rule and within
15 minutes of each other. Features exclude the entire earlier quote day.

Old cohort lines remain byte-for-byte in the append-only JSONL. The current
summary uses only the new version and refuses changed model fingerprints.
The artifact hash, source hashes, quote times, registration time and inputs are
stored with forecasts. Outcomes are derived separately; conflicting results
remain unresolved. Pending selections older than 48 hours are shown separately.

The compact summary travels in the existing team-shots snapshot and weekly
watchlist. No new schedule, API collection or messaging is introduced.
Review at 50 and 150 independent settled fixtures. Forecast scores use matched
contracts averaged within fixture; selected betting samples can differ.
StatsHub capture and closing-price comparison remain unconnected.
