# Football Player Form Layer Report

Generated: 2026-04-25T10:06:27+00:00

## Outputs

- `data/football-form/player-rolling-form.csv`

## Summary

- Source files: 15
- Raw rows: 145335
- Usable player rows: 145335
- Rolling rows: 145335
- Date range: 2023-08-11 to 2026-04-10

## League Coverage

| League | Player rows |
| --- | ---: |
| bundesliga | 25763 |
| epl | 30973 |
| la-liga | 32030 |
| ligue-1 | 25281 |
| serie-a | 31288 |

## Source Stats

```json
{
  "files": 15,
  "raw_rows": 145335,
  "skipped_no_date": 0,
  "usable_rows": 145335
}
```

## Notes

- Rolling features are causal: each row uses only prior appearances for that player.
- Windows include 5/10 for shared football form and 16/40 to mirror the current goalscorer model.
- `team_xg_share` is player xG divided by team xG across the same player appearances.
- This table is not wired into live goalscorer selection yet.
