# Latest hits portraits and Super Sub audit — 9 September 2026

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
