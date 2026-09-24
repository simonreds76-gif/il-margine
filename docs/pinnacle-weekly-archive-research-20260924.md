# Weekly Pinnacle archive: verified candidate, 24 September 2026

The PC capture and weekly tasks remain disabled. No bookmaker substitution or new scheduler is enabled by this research.

## Best candidate: OddsPapi v4

Official documentation explicitly exempts `/v4/historical-odds` from the request allowance. The existing free account returned HTTP 200 for all five sampled matches. Its allowance was 250 and usage increased from 0 to 6: five fixture-list calls and one tournament-catalogue call. Five historical calls consumed no metered requests. Account reads are unmetered.

Sources:
- https://oddspapi.io/en/docs/requests-and-quota
- https://oddspapi.io/en/docs/get-historical-odds
- https://oddspapi.io/en/docs/get-fixtures

History is documented from January 2026 onwards. It does not solve July–December 2025. Hitting the billable allowance blocks history too, despite history not consuming it. Reserve headroom and cache lookup responses. History has a five-second endpoint cooldown.

## Bounded live verification

Completed-fixture queries for 18–22 September returned 10 EPL, 10 La Liga, 10 Serie A, 9 Bundesliga and 9 Ligue 1 fixtures. One history per league was downloaded with `bookmakers=pinnacle`. Market 101 returned full-match home/draw/away outcomes 101/102/103 and timestamped price/status changes.

| Match | Last active prices before scheduled kickoff (H/D/A) |
| --- | --- |
| Brentford–Chelsea | 2.57 / 3.64 / 2.75 |
| Espanyol–Elche | 1.819 / 3.73 / 4.73 |
| Monza–Sassuolo | 2.97 / 3.35 / 2.55 |
| Monaco–Lens | 1.854 / 3.90 / 4.29 |
| Bayern–Union Berlin | 1.05 / 18.00 / 46.00 |

Four samples had outcome updates within roughly two minutes of scheduled kickoff. Bayern's final active update was about 44 minutes earlier, followed by identical prices being deactivated 25 seconds before the recorded actual start. This is a change log: a price's last-change time is not automatically the last time it was available. Do not discard unchanged prices solely because of age, or blindly carry them through suspensions.

This establishes recent machine-readable Pinnacle availability across five leagues, not complete historical coverage or perfect provider accuracy. Hosted-run access and full-week reconciliation remain to be tested.

## Proposed weekly cloud design

1. Fetch completed fixtures by tournament for a rolling overlap window; cache catalogue IDs (17 EPL, 8 La Liga, 23 Serie A, 34 Ligue 1, 35 Bundesliga).
2. Download each new or corrected fixture's Pinnacle history with a five-second gap. Store raw responses privately and retain event IDs, timestamps, settlement evidence and content hashes.
3. Reconstruct all three outcome states at the same pre-match cutoff. Use the earlier of scheduled and credible actual start as a conservative initial boundary; validate delayed/rescheduled matches separately. Distinguish price updates, suspensions and final deactivation. Do not simply choose the latest `active:true` row across a suspension, or use an in-play quote.
4. Verify regulation-time final scores and club/league identity against the results source. Reject incomplete/conflicting markets, abnormal overround, unknown teams and ambiguous timing. Reconcile all fixtures, not just successful downloads.
5. Publish a compact validated archive only if changed; preserve the last good release and send an actionable failure alert. Do not deploy for every download.

Five fixture calls weekly plus cached lookups would be roughly 20–25 metered calls monthly, with historical reads unmetered under today's documented policy. Scores or additional fixture detail can add requests, so usage monitoring remains required.

## Other sources and Claude review

Claude searched public sources and reviewed the public bookmakers page. It found no verified public weekly Pinnacle CSV. Its 250-request warning missed the explicit free historical endpoint exemption, and its five-league match-count arithmetic was wrong. These were checked directly rather than repeated.

- Football-Data: simple current CSVs, but warns Pinnacle prices unreliable since 23 July 2025; recent inspected files have no complete Pinnacle closing triplets.
- Goaloo: existing local extraction already works; a recurring hosted extraction is still unverified. It remains a potential cross-check/archive fallback.
- SteamWatch and Scanbet: public archive pages exist; a documented free bulk export was not verified. A browsable archive alone does not establish a reliable weekly ingestion service.
- OddsPortal: no official free bulk endpoint was established in this research.

No signup, upgrade, payment or account selection change was made. Private sample responses and the Claude transcript are retained outside the repository in the task output directory.
