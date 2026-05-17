# Assist Value Set-Piece Source Audit

Fetched at UTC: `2026-05-17T18:23:47+00:00`

## Decision

Overall: **PASS_SOURCE_LAYER**

- RotoWire public player pages are accepted as the primary Big-5 role source if every team returns a set-piece block.
- Official FPL API is accepted as the Premier League validator if it returns current set-piece order fields.
- SetPieceTakers is rejected as a live primary while row timestamps are stale and CSV export is disabled.
- RotoWire week numbers can exceed domestic league matchweeks, so the feed is a role source, not a league-only historical-volume source.

## RotoWire

- Teams with set-piece blocks: `96/96`
- Player role rows extracted: `1034`

| League | Teams OK | Teams | Role rows | Max latest week |
|---|---:|---:|---:|---:|
| bundesliga | 18 | 18 | 184 | 48 |
| epl | 20 | 20 | 209 | 54 |
| la-liga | 20 | 20 | 223 | 53 |
| ligue-1 | 18 | 18 | 200 | 50 |
| serie-a | 20 | 20 | 218 | 51 |

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
| la-liga | Real Madrid | Trent Alexander-Arnold | 91.3% | 28.63% | 65 |
| bundesliga | FSV Mainz 05 | Nadiem Amiri | 90.91% | 57.25% | 79 |
| ligue-1 | Metz | Gauthier Hein | 90.91% | 63.25% | 74 |
| ligue-1 | Lorient | Pablo Pagis | 90.0% | 58.75% | 47 |
| epl | Burnley | James Ward-Prowse | 88.24% | 34.15% | 42 |
| ligue-1 | Rennes | Sebastian Szymanski | 81.48% | 23.53% | 36 |
| bundesliga | VfL Wolfsburg | Christian Eriksen | 81.25% | 55.0% | 77 |
| ligue-1 | Angers | Branco van den Boomen | 80.0% | 37.36% | 34 |
| bundesliga | SC Freiburg | Jan-Niklas Beste | 77.78% | 38.5% | 72 |
| ligue-1 | AJ Auxerre | Kevin Danois | 77.78% | 61.76% | 84 |
| la-liga | Sevilla | Ruben Vargas | 76.92% | 22.45% | 33 |
| epl | West Ham United | Jarrod Bowen | 75.0% | 37.14% | 65 |
| bundesliga | RB Leipzig | Max Finkgrafe | 75.0% | 12.24% | 18 |
| epl | Leeds United | Anton Stach | 72.22% | 58.01% | 105 |

## Outputs

- `/home/runner/work/il-margine/il-margine/data/assist-value/rotowire-setpiece-roles.csv`
- `/home/runner/work/il-margine/il-margine/data/assist-value/rotowire-source-status.csv`
- `/home/runner/work/il-margine/il-margine/data/assist-value/fpl-setpiece-roles.csv`
- `/home/runner/work/il-margine/il-margine/data/assist-value/setpiecetakers-source-status.csv`
- `/home/runner/work/il-margine/il-margine/data/assist-value/setpiece-source-audit.json`

## Production Guard

No public Assist Value Lab picks are authorised by this audit. This only proves the source layer is viable enough to build a shadow model.
