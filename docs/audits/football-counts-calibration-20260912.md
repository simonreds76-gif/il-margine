# Football counts calibration review — 12 September 2026

## Decision

Repair the verified input and evidence defects. Do not adopt the tested new weights or relax the team-shots gap cap: none demonstrated a consistent probability/ROI improvement across both later periods. Corners remains research; its probability estimates are not established betting advantages.

## Today's first five corners results

The saved FotMob full-match statistics confirm all five losses, at flat 1u per selection: -5u, ROI -100%. This audit does not retrospectively remove them or change their odds. Four later French fixtures were still pending when checked.

| Fixture | Selection | Actual corners |
|---|---|---:|
| Genoa–Frosinone | Under 8.5 | 17 |
| Dortmund–Paderborn | Under 9.5 | 10 |
| Hoffenheim–Stuttgart | Under 9.5 | 12 |
| Liverpool–Fulham | Under 9.5 | 13 |
| Osasuna–Espanyol | Over 9.5 | 7 |

The source snapshots and detailed results are saved locally under `outputs/football-signals-20260912`. This report verifies results; it does not write them into settlement ledgers. Several recorded quotes were from September 9–10. They must not be described as newly available executable prices or true closing odds.

## Temporal replay

`scripts/football-counts-calibration-audit.py` rebuilds causal rolling features from the durable base. Count parameters use only games before April 1, 2026 (41,042 shots team rows; 10,541 corners fixtures). Probability blend/intercept parameters are fitted on April 1–May 8 by fixture-weighted log loss, not ROI. Validation is May 9–July 31; the final historical replay is August 1–September 7. The archive supplies 353 shots fixtures and 316 corners fixtures across all three market periods.

Only the earliest complete, same-bookmaker, pre-kickoff, half-line price board per fixture is evaluated. Later prices cannot be picked retrospectively. Multiple lines receive equal shares of one fixture's probability-metric weight. Simulated betting uses at most one selection per fixture, EV >=3%, flat 1u. `legacy` reproduces the prior served pricing formula and its MD4–6 raw gap cap; count parameters are refitted before April, not the production model trained through May. Replay results are not the actual prospective ledger and include no claim that historical quotes remained executable.

| Variant | Validation ROI (bets) | August–September ROI (bets) |
|---|---:|---:|
| Shots prior served formula | +21.28% (20) | -23.75% (19) |
| Shots fitted blend | +18.22% (19) | -12.81% (23) |
| Shots fitted blend + intercept | -3.39% (19) | +3.49% (25) |
| Corners raw count probability | -36.64% (44) | -2.40% (39) |
| Corners fitted blend | No selections | No selections |
| Corners fitted blend + intercept | -9.14% (79) | -28.17% (59) |

For corners, fitting selected zero count-model weight. Market Brier was better than the count model in both validation (.24122 vs .25373) and the final replay (.24665 vs .24772); lower is better. Adding an intercept produced attractive calibration-period ROI but failed later. These results do not support an arbitrary correction upward after today's under losses.

The shots blend+intercept final-period +3.49% is not a promotion result: it lost in validation and its final Brier .25455 remained worse than market .24954. No threshold, weight or intercept from these experiments enters production. Previously inspected historical periods are not a fresh prospective test. The JSON companion contains all variants, metrics, fitting boundaries and input SHA-256 hashes; local `audit.json` also contains every simulated pick.

## Implemented repairs

1. **Team-shots train/serve mismatch:** inject the already collected 1X2 strength input into the registered mean formula. Require all home/draw/away prices in one same-bookmaker snapshot, no later than either shots price, before kickoff, and within 24 hours of that quote. Otherwise retain neutral strength. No closing information is reconstructed retrospectively. Existing coefficient .22 and adjustment cap of 12% are unchanged.
2. **As-of corners features:** only event rows strictly before the fixture day enter the event state, preventing same-day/future results entering a replay.
3. **Immutable published selection:** preserve the first recorded selection, probability, odds and result per fixture. Rescoring updates the candidate board and can add new fixtures; it cannot replace an old selection with a better-looking one.
4. **Evidence provenance:** tag new inputs by version, retain quote/strength timestamps, and carry those plus the expected count through closing-price monitoring. Existing records are not relabelled as the repaired version.

A local comparison at 19:27 UTC matched all 70 current shots candidate rows to verified earlier 1X2 data. Manchester United's mean changed 16.9241→16.3409; Manchester City's 16.1567→16.7134. There were still zero eligible selections. The previously documented early-season raw-gap/EV conflict remains unresolved by validated model evidence, and is explicitly reported as a rule conflict rather than missing prices.

All calculations were local, using saved data. No extra bookmaker API calls, Supabase writes, Vercel computation, Telegram broadcasts, or new scheduled backtests were required. The input repairs run through the existing football shadow refresh; future evidence retains the input-version tag for comparison.

## Next evidence required

Evaluate the corrected timestamped-strength cohort before selecting a replacement shots gap policy. For corners, collect fresh paired prices and true closes alongside the original predictions, then test any feature/model revision on later fixtures. Preserve the current losing control. The tested weight-only changes do not justify promotion.
