# Assist Value Set-Piece Source Audit

Fetched at UTC: `2026-11-06T14:56:48+00:00`

## Decision

Overall: **PASS_SOURCE_LAYER**

- RotoWire public player pages are accepted as the primary Big-5 role source if every team returns a set-piece block.
- Official FPL API is accepted as the Premier League validator if it returns current set-piece order fields.
- SetPieceTakers is rejected as a live primary while row timestamps are stale and CSV export is disabled.
- RotoWire week numbers can exceed domestic league matchweeks, so the feed is a role source, not a league-only historical-volume source.

## RotoWire

- Teams with set-piece blocks: `96/96`
- Player role rows extracted: `746`

| League | Teams OK | Teams | Role rows | Max latest week |
|---|---:|---:|---:|---:|
| bundesliga | 18 | 18 | 117 | 12 |
| epl | 20 | 20 | 149 | 13 |
| la-liga | 20 | 20 | 177 | 15 |
| ligue-1 | 18 | 18 | 141 | 14 |
| serie-a | 20 | 20 | 162 | 14 |

## FPL API

- Status: `PASS`
- Teams: `20`
- Players: `670`
- Players with set-piece role fields: `149`
- Registered season: `2026/27`
- Exact 20-team roster match: `YES`
- Snapshot valid until UTC: `2026-11-13T14:56:48+00:00`

## SetPieceTakers

- Pages checked: `15`
- Stale March 20 pages: `0`
- CSV-disabled pages: `0`
- Decision: `REJECT_AS_LIVE_PRIMARY`

## Top Last-5 Corner Role Shares From RotoWire

| League | Team | Player | Last-5 corner share | Season corner share | Corner total |
|---|---|---|---:|---:|---:|
| ligue-1 | Angers | Branco van den Boomen | 100.0% | 98.04% | 50 |
| bundesliga | SV 07 Elversberg | Felix Keidel | 93.33% | 95.45% | 21 |
| serie-a | Frosinone | Giacomo Calo | 93.1% | 96.23% | 51 |
| bundesliga | FSV Mainz 05 | Nadiem Amiri | 91.67% | 96.3% | 26 |
| bundesliga | Bayer Leverkusen | Aleix Garcia | 88.89% | 90.48% | 57 |
| serie-a | Como | Luis Milla | 88.89% | 69.49% | 41 |
| ligue-1 | Brest | Joris Chotard | 84.62% | 90.91% | 30 |
| ligue-1 | AJ Auxerre | Romain Faivre | 80.95% | 65.71% | 23 |
| epl | Leeds United | Anton Stach | 78.95% | 77.78% | 28 |
| ligue-1 | Troyes | Antoine Mille | 75.0% | 42.22% | 19 |
| la-liga | Málaga | Pablo Martinez | 73.91% | 70.45% | 31 |
| ligue-1 | Lens | Florian Thauvin | 73.68% | 80.6% | 54 |
| bundesliga | RB Leipzig | David Raum | 73.33% | 91.67% | 44 |
| la-liga | Deportivo Alaves | Denis Suarez | 71.43% | 58.97% | 23 |
| ligue-1 | Paris FC | Pablo Pagis | 70.59% | 59.26% | 16 |

## Outputs

- `/home/runner/work/il-margine/il-margine/data/assist-value/rotowire-setpiece-roles.csv`
- `/home/runner/work/il-margine/il-margine/data/assist-value/rotowire-source-status.csv`
- `/home/runner/work/il-margine/il-margine/data/assist-value/fpl-setpiece-roles.csv`
- `/home/runner/work/il-margine/il-margine/data/assist-value/fpl-player-roster.csv`
- `/home/runner/work/il-margine/il-margine/data/assist-value/fpl-source-status.json`
- `/home/runner/work/il-margine/il-margine/data/assist-value/setpiecetakers-source-status.csv`
- `/home/runner/work/il-margine/il-margine/data/assist-value/setpiece-source-audit.json`

## Production Guard

No public Assist Value Lab picks are authorised by this audit. This only proves the source layer is viable enough to build a shadow model.
