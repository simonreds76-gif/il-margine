# Latest hits portraits and Super Sub audit — 9 September 2026

## Subsequent user-authorized change, 9 September

The user explicitly requested automatic Bet365 Super Sub tracking for the daily board. The earlier eligibility gate described below is superseded: Bet365 rows now use `bet365_automatic_20260909` without requiring the promotion verification flag. This is an operator-selected tracking policy, not captured proof that a bookmaker accepted a particular promotion contract. The evidence flag is not falsely set to verified.

Named-player goals/outcomes are preserved separately from promotion-inclusive win/loss and profit. Clear one-for-one substitution chains are followed; ambiguous mappings remain pending. Previously settled daily-board losses are rechecked once under the new policy. No existing daily CSV files were present at implementation time. Public Latest hits now admits recorded positive-value Super Sub wins and labels the replacement explicitly. The archived Brobbey/Isidor win was used for local visual verification, without reordering production highlights.

Validation: 23 targeted tests passed, including an end-to-end CSV settlement regression changing an old daily loss to +3 units at odds 4 while preserving zero named-player goals, plus idempotent reruns. TypeScript and targeted lint passed. No new scheduler or collection frequency was added.

The following sections describe the initial audit before that subsequent instruction.

Portraits use FotMob's existing player-image URLs, loaded lazily and directly by the browser. The website falls back to a club shirt if an image fails. There are no new odds/API calls, image transformations, polling jobs, or database writes.

The legacy identity map contains 48 unique league/name matches verified against saved `data/goalscorer/match-results/<league>/fotmob-*.json` player records. Conflicting or missing identities were excluded. All six current highlights are resolved. Legacy signal `player_id` belongs to Understat and must never be treated as a FotMob ID. New daily-board rows carry FotMob IDs; the highlight generator now carries those portraits automatically.

## Settlement findings

- Legacy Bet365 rows still call `_settle_super_sub_replacement` automatically after the named player fails to score. They infer bookmaker eligibility by name, rather than stored promotion evidence.
- Daily-board creation explicitly writes `super_sub_contract_verified=0`. The settler requires this field to be `1` for daily-board replacement credit. The new board therefore does NOT currently count Super Sub wins automatically.
- For eligible rows, the current algorithm credits a scoring direct replacement only when exactly one player exits and one enters for that team/minute. Simultaneous substitutions are not resolved. Replacement chains are not followed.
- The public page excludes `super_sub_win` highlights and requires the named player to score. No display or settlement policy was changed in this portrait update.
- Bet365's Sub On Play On help describes selected marked markets, bookmaker-designated replacements for simultaneous substitutions, and continuing replacement chains. A Bet365 odds quote alone does not prove the captured market carries this promotion. Official help: https://help.bet365.com/s/en/sports/sub-on-play-on (regional official help also returned the detailed rules during this audit).

To extend accurate promotion-inclusive settlement, capture market-level promotion evidence and the authoritative replacement mapping, retain the named-player outcome separately, and display verified replacement wins with the replacement's name. Do not simply set every daily row's verification flag to 1 or retroactively invent eligibility.

Validation: six targeted tests cover namespace correctness, future daily portraits, legacy replacement wins, daily eligibility, ambiguous substitutions, own goals, and other bookmakers. Generated highlights pass the existing source-record validator. Desktop and 390px mobile portrait cards were visually checked; all six current portraits loaded.
