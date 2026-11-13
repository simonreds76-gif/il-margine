# Assist Value Set-Piece Source Audit

Fetched at UTC: `2026-11-13T15:18:03+00:00`

## Decision

Overall: **PASS_SOURCE_LAYER**

- RotoWire public player pages are accepted as the primary Big-5 role source if every team returns a set-piece block.
- Official FPL API is accepted as the Premier League validator if it returns current set-piece order fields.
- SetPieceTakers is rejected as a live primary while row timestamps are stale and CSV export is disabled.
- RotoWire week numbers can exceed domestic league matchweeks, so the feed is a role source, not a league-only historical-volume source.

## RotoWire

- Teams with set-piece blocks: `96/96`
- Player role rows extracted: `761`

| League | Teams OK | Teams | Role rows | Max latest week |
|---|---:|---:|---:|---:|
| bundesliga | 18 | 18 | 121 | 13 |
| epl | 20 | 20 | 152 | 14 |
| la-liga | 20 | 20 | 179 | 16 |
| ligue-1 | 18 | 18 | 144 | 15 |
| serie-a | 20 | 20 | 165 | 15 |

## FPL API

- Status: `PASS`
- Teams: `20`
- Players: `672`
- Players with set-piece role fields: `150`
- Registered season: `2026/27`
- Exact 20-team roster match: `YES`
- Snapshot valid until UTC: `2026-11-20T15:18:03+00:00`

## SetPieceTakers

- Pages checked: `15`
- Stale March 20 pages: `0`
- CSV-disabled pages: `0`
- Decision: `REJECT_AS_LIVE_PRIMARY`

## Top Last-5 Corner Role Shares From RotoWire

| League | Team | Player | Last-5 corner share | Season corner share | Corner total |
|---|---|---|---:|---:|---:|
| ligue-1 | AJ Auxerre | Romain Faivre | 93.75% | 66.67% | 24 |
| bundesliga | FSV Mainz 05 | Nadiem Amiri | 93.33% | 96.88% | 31 |
| bundesliga | SV 07 Elversberg | Felix Keidel | 93.33% | 96.0% | 24 |
| serie-a | Frosinone | Giacomo Calo | 91.18% | 95.16% | 59 |
| ligue-1 | Brest | Joris Chotard | 90.91% | 91.18% | 31 |
| serie-a | Como | Luis Milla | 90.0% | 70.49% | 43 |
| bundesliga | Bayer Leverkusen | Aleix Garcia | 89.29% | 91.18% | 62 |
| ligue-1 | Lens | Florian Thauvin | 84.21% | 81.69% | 58 |
| ligue-1 | Angers | Branco van den Boomen | 83.33% | 92.73% | 51 |
| bundesliga | Eintracht Frankfurt | Fares Chaibi | 80.0% | 54.29% | 19 |
| ligue-1 | Paris FC | Pablo Pagis | 78.95% | 64.52% | 20 |
| la-liga | Valencia | Javi Guerra | 78.57% | 30.23% | 13 |
| epl | Coventry City | Jack Rudoni | 71.43% | 48.39% | 15 |
| bundesliga | RB Leipzig | David Raum | 71.43% | 92.0% | 46 |
| ligue-1 | Toulouse | Cristian Casseres | 71.43% | 57.69% | 15 |

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
