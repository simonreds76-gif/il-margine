# Assist Value Set-Piece Source Audit

Fetched at UTC: `2026-05-17T11:27:05+00:00`

## Decision

Overall: **PASS_SOURCE_LAYER**

- RotoWire public player pages are accepted as the primary Big-5 role source if every team returns a set-piece block.
- Official FPL API is accepted as the Premier League validator if it returns current set-piece order fields.
- SetPieceTakers is rejected as a live primary while row timestamps are stale and CSV export is disabled.
- RotoWire week numbers can exceed domestic league matchweeks, so the feed is a role source, not a league-only historical-volume source.

## RotoWire

- Teams with set-piece blocks: `96/96`
- Player role rows extracted: `1032`

| League | Teams OK | Teams | Role rows | Max latest week |
|---|---:|---:|---:|---:|
| bundesliga | 18 | 18 | 184 | 48 |
| epl | 20 | 20 | 208 | 54 |
| la-liga | 20 | 20 | 223 | 52 |
| ligue-1 | 18 | 18 | 200 | 49 |
| serie-a | 20 | 20 | 217 | 50 |

## FPL API

- Status: `PASS`
- Teams: `20`
- Players: `838`
- Players with set-piece role fields: `131`

## SetPieceTakers

- Pages checked: `15`
- Stale March 20 pages: `15`
- CSV-disabled pages: `15`
- Decision: `REJECT_AS_LIVE_PRIMARY`

## Top Last-5 Corner Role Shares From RotoWire

| League | Team | Player | Last-5 corner share | Season corner share | Corner total |
|---|---|---|---:|---:|---:|
| la-liga | Getafe | Luis Milla | 100.0% | 83.45% | 116 |
| ligue-1 | Lorient | Pablo Pagis | 93.33% | 58.75% | 47 |
| la-liga | Real Madrid | Trent Alexander-Arnold | 91.67% | 28.89% | 65 |
| bundesliga | FSV Mainz 05 | Nadiem Amiri | 90.91% | 57.25% | 79 |
| ligue-1 | Metz | Gauthier Hein | 90.91% | 63.25% | 74 |
| epl | Burnley | James Ward-Prowse | 88.24% | 34.15% | 42 |
| bundesliga | VfL Wolfsburg | Christian Eriksen | 81.25% | 55.0% | 77 |
| ligue-1 | AJ Auxerre | Kevin Danois | 80.95% | 61.76% | 84 |
| ligue-1 | Angers | Branco van den Boomen | 80.0% | 37.36% | 34 |
| bundesliga | SC Freiburg | Jan-Niklas Beste | 77.78% | 38.5% | 72 |
| epl | West Ham United | Jarrod Bowen | 75.0% | 36.78% | 64 |
| bundesliga | RB Leipzig | Max Finkgrafe | 75.0% | 12.24% | 18 |
| bundesliga | Bayer Leverkusen | Alejandro Grimaldo | 72.0% | 55.62% | 94 |
| bundesliga | Union Berlin | Christopher Trimmel | 72.0% | 51.95% | 80 |
| epl | Sunderland | Enzo Le Fee | 71.43% | 37.69% | 49 |

## Outputs

- `data\assist-value\rotowire-setpiece-roles.csv`
- `data\assist-value\rotowire-source-status.csv`
- `data\assist-value\fpl-setpiece-roles.csv`
- `data\assist-value\setpiecetakers-source-status.csv`
- `data\assist-value\setpiece-source-audit.json`

## Production Guard

No public Assist Value Lab picks are authorised by this audit. This only proves the source layer is viable enough to build a shadow model.
