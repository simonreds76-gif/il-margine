# Goalscorer Player Log Smoke Test

Generated: 2026-04-25

Purpose: verify current-season player logs can still be consumed by `goalscorer-model.py` before asking Claude to audit the canonical football-form work.

## Freshness

`goalscorer-player-log-health.py --season current --max-age-days 3` flags all five current-season logs as stale.

Latest match date across current-season logs: `2026-04-10`.

## Model Smoke Results

| League | Loaded rows | Normalized rows | Processed rows | Model rows | Fallback rows |
| --- | ---: | ---: | ---: | ---: | ---: |
| serie-a | 9,197 | 8,575 | 8,575 | 6,824 | 1,751 |
| epl | 8,964 | 8,344 | 8,344 | 6,712 | 1,632 |
| la-liga | 9,067 | 8,465 | 8,465 | 6,704 | 1,761 |
| bundesliga | 7,613 | 7,107 | 7,107 | 5,569 | 1,538 |
| ligue-1 | 7,441 | 6,935 | 6,935 | 5,317 | 1,618 |

## Interpretation

- The model still runs on the files, so this is not a schema break.
- The problem is data freshness: hosted refresh skipped Understat because files existed.
- Workflows now check current-season log age and refresh stale leagues before expected refresh and settlement.
