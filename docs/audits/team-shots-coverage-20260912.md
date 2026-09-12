# Team-shots capture correction — 12 September 2026

The 16:29 UTC scrape returned no team-shots markets for its three fixtures inside the 90-minute window. This did **not** represent the entire day: the canonical archive already contained earlier captures, and the model gate reported 44 scored candidates across 11 fixtures, with no eligible selection. The earlier user-facing report incorrectly described a day-wide price gap.

A bounded live check of the existing Odds-API.io account returned Bet365 team totals, with distinct home/away identities and paired over/under prices. BetMGM was also checked and did not supply team shots for those fixtures. No bookmaker subscription was changed.

The repaired capture at 18:30 UTC returned 72 rows across 18 upcoming fixtures in all five leagues: EPL 12, Serie A 12, La Liga 16, Bundesliga 8, Ligue 1 24. All timestamps are actual collection times; no past picks were reconstructed from later prices. Rows were appended to the canonical archive, with control markets retained from the same responses.

## Durable change

- Scheduled team-shots collection covers the next 24 hours, rather than depending on execution within 90 minutes of kickoff. GitHub schedule delays therefore have a larger tolerance.
- Football event discovery is shared across all five league passes within one capture run, then cleared on budget configuration for the next run.
- The nine-request hard ceiling remains. The verified all-league capture used six HTTP requests: one discovery plus five odds batches. Each league remains capped at ten fixtures / one odds batch. GK and Pinnacle corners retain their existing close windows.
- No Vercel deployment or polling increase is required for the capture change.

## Validation

Four capture diagnostic tests and four market filter tests passed. The new regression test verifies coverage of fixtures five hours away across all five leagues in six requests, and verifies that a new run resets the discovery cache. The actual all-league capture also succeeded within that budget. The existing archive, scoring, tracking and snapshot scripts ran successfully.

The refreshed model scored 52 team-shots rows across 11 fixtures: zero eligible. Forty-nine rows failed the 3% minimum edge; twenty failed the early-season market-gap cap, with overlap between blockers. Coverage and selection eligibility are distinct; no model thresholds were relaxed to manufacture signals.

## Follow-up: priced fixtures silently skipped at the historical-data join

Further tracing found twenty long bookmaker club names without matching form-history keys. Exact aliases were added for these observed clubs, including Auxerre, Nice, Lyon, Manchester City, Rayo Vallecano, Inter and PSG. This is a deterministic identity correction, not a change in model weights. Regression tests check all twenty joins and verify that Paris FC/PSG, Manchester City/United and other distinct clubs remain separate.

After the correction, the current price archive has no unmatched prior-history club names. Team Shots scoring increased from 52 rows / 11 fixtures to **100 rows / 23 fixtures**, still with no qualifying selection: 95 rows fail the minimum edge and 34 fail the early-season gap cap (overlapping reasons). Ten vNext model tests passed. The shared publisher also generated two additional future corners records from already archived Pinnacle quotes (Brest–PSG and Leeds–Newcastle); their model generation is 12 September at 18:36 UTC, while the existing ledger's publication field inherits the older quote-capture timestamp. No retrospective finished-match selections were added and no Telegram alerts were sent.

The canonical archive contained 216 rows captured earlier on 12 September across 43 fixture IDs, including future fixtures; lack of a new price in the final narrow scan must not be reported as a day-wide capture outage.
