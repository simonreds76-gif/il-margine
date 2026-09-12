# Football count tracking and settlement audit — 12 September 2026

## Fixed

The daily results fetch explicitly names the v4 and corners CLV files. It did
not include Opponent Shots, and newly published hourly selections can exist in
the permanent signals files before the daily CLV rebuild. The fetcher now reads
all three permanent ledgers plus the two append-only signal files whenever a
count ledger is requested. Blank results count as pending only in those known
published signal files. Settled entries suppress their original blank signal;
pick and fixture deduplication prevents duplicate fetch targets. Candidate
boards remain excluded. The existing schedule and ten-request API-Football
fallback cap are unchanged; additional unique pending fixtures can consume
more of that existing budget and require free-source lookups.

Both CLV builders now retain explicit publication odds/the original selected
`book_odds`, using archived publication snapshots only for legacy picks without
entry odds. Settlement no longer substitutes closing odds when publication
odds are missing; missing or invalid entry odds leave the selection pending.

Five old corners warmup wins had profit inconsistent with their original entry
prices. The original signal history at `3bcfea9db` verifies every corrected
price, timestamp, line and side. Only profit was corrected, **-0.266u** in total.
Grades, counts, selection terms and timestamps were preserved. The individual
before/after record is `data/football-form/corners-v3-pnl-corrections-20260912.json`.
Some incorrect profits match closing odds, consistent with the removed
fallback; historical execution logs are insufficient to attribute every row's
original code path definitively.

## Current saved evidence

Audit source: golden commit `a9666e11eceeb5e83b1b562842dfbee6a72a2088`, with
publication subsequently based on the latest branch head. Latest completed
capture run `34720545378` succeeded; its shots capture recorded 14 fixtures,
56 rows, six HTTP requests against its cap of nine, with no provider errors.
Opponent now has five pending selections for 13 September, zero settled.

| Lane / cohort | W–L | Settled | Pending | Profit | ROI |
|---|---:|---:|---:|---:|---:|
| v4 warmup | 8–6 | 14 | 0 | +0.323u | +2.31% |
| v4 eligible | 0–1 | 1 | 0 | -1.000u | -100% |
| Opponent forward | 0–0 | 0 | 5 | 0u | unavailable |
| Corners warmup, corrected | 16–20 | 36 | 0 | -2.503u | -6.95% |
| Corners eligible | 3–1 | 4 | 13 | +2.260u | +56.50% |

These small eligible samples do not establish either model's profitability.
Warmup is kept separate from eligible forward evidence. Combined corners
accounting is 19W/21L, **-0.243u / -0.61%** across 40 settled selections.

All 55 stored grades recompute correctly from their recorded counts and lines;
there are no duplicate pick IDs. Rechecking with the saved snapshot found no
pending selection newly settleable. Current snapshot/base identity joins
corroborated 54 of 55 recorded actuals without a conflicting count. Hoffenheim
vs Dortmund on 5 September did not resolve in that exact-identity cross-check;
its stored 13 corners was not altered or presented as independently confirmed.

## Today's corners and the reported five losses

The saved results snapshot was fetched at **12:12:56 UTC on 12 September**,
before today's first tracked kickoff. All nine of today's corners selections
remain pending; four further selections are on 13–14 September. Consequently
the saved evidence cannot confirm or diagnose the reported same-day 0–5.
The five most recent *settled* losses are spread over 4–11 September, with wins
between them. They must not be misrepresented as the user's five-loss day.
The next scheduled daily refresh is 13 September at 08:15 UTC / 09:15 UK,
subject to GitHub queue delay and provider availability. Settlement needs final
source counts; it is not guaranteed merely because the refresh runs.

## Corners calibration and price coverage

Across the 40 settled entries, mean predicted total is **9.298** versus actual
**9.425** (prediction bias -0.127; MAE 3.084 corners). This is not evidence of
broad total-count overprediction. The model's selected-side win probability
averages 52.63% against 47.50% observed wins. That gap is worth tracking but
cannot safely determine new weights from only 40 selected matches.

The side split is more informative for future checks: 29 Unders predicted
9.297 versus 10.034 actual corners; 11 Overs predicted 9.303 versus 7.818 actual.
Selection-conditional errors point in opposite directions, so a single blanket
upward/downward mean adjustment is not justified. Cohort and fixture mix limit
causal interpretation. The latest five settled losses include both high-count
Under losses and low-count Over losses.

The capture coverage report is the clearest operational warning: recent shots
close coverage was **56/74 (75.7%)**, while Pinnacle corners was **0/98 (0%)**,
with median last-price lag around **35.2 hours**. This concerns the broader
capture cohort, not only the 40 settled picks. Historical corners prices exist,
but they do not establish reliable current closing-price evidence. Bet365
corners are already being archived as controls; those must not silently become
Pinnacle entry or closing prices. Hosted run-log retrieval returned a GitHub
permission error, so this audit does not assert a fresh Pinnacle HTTP status.

## Verification and follow-up

77 football tests and seven Opponent tracker tests passed. New tests cover
Opponent-only and hourly-only queue entries, duplicate fixture suppression,
settled/void exclusion, original entry prices, absent entry prices despite
available closes, and preservation of settled losses. Corrected profits were
checked against the original signal archive, with a retained correction log.
The corrected CLV report, gate files and corners snapshot were rebuilt locally.

No model coefficients, staking rules or promotion gates changed. No bookmaker
or results-provider calls were made during this audit, and no new polling,
schedule, Vercel deployment or Supabase upload was added. The existing GitHub
job will use the corrected queue on its next daily fetch.

At weekly review, compare the two shots ledgers on genuinely new outcomes,
original prices, closing-price coverage and disagreements. For corners,
prioritise verified settlement of today's pending matches and recovery of
usable Pinnacle close coverage before considering another weight change.
