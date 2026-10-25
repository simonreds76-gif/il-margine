# Assist Value Set-Piece Source Audit

Fetched at UTC: `2026-10-25T12:31:22+00:00`

## Decision

Overall: **PASS_SOURCE_LAYER**

- RotoWire public player pages are accepted as the primary Big-5 role source if every team returns a set-piece block.
- Official FPL API is accepted as the Premier League validator if it returns current set-piece order fields.
- SetPieceTakers is rejected as a live primary while row timestamps are stale and CSV export is disabled.
- RotoWire week numbers can exceed domestic league matchweeks, so the feed is a role source, not a league-only historical-volume source.

## RotoWire

- Teams with set-piece blocks: `96/96`
- Player role rows extracted: `702`

| League | Teams OK | Teams | Role rows | Max latest week |
|---|---:|---:|---:|---:|
| bundesliga | 18 | 18 | 115 | 10 |
| epl | 20 | 20 | 139 | 11 |
| la-liga | 20 | 20 | 171 | 13 |
| ligue-1 | 18 | 18 | 132 | 11 |
| serie-a | 20 | 20 | 145 | 11 |

## FPL API

- Status: `PASS`
- Teams: `20`
- Players: `669`
- Players with set-piece role fields: `144`
- Registered season: `2026/27`
- Exact 20-team roster match: `YES`
- Snapshot valid until UTC: `2026-11-01T12:31:22+00:00`

## SetPieceTakers

- Pages checked: `15`
- Stale March 20 pages: `0`
- CSV-disabled pages: `0`
- Decision: `REJECT_AS_LIVE_PRIMARY`

## Top Last-5 Corner Role Shares From RotoWire

| League | Team | Player | Last-5 corner share | Season corner share | Corner total |
|---|---|---|---:|---:|---:|
| bundesliga | FSV Mainz 05 | Nadiem Amiri | 100.0% | 100.0% | 22 |
| bundesliga | SV 07 Elversberg | Felix Keidel | 100.0% | 100.0% | 18 |
| ligue-1 | Angers | Branco van den Boomen | 100.0% | 97.67% | 42 |
| serie-a | Frosinone | Giacomo Calo | 95.83% | 96.88% | 31 |
| epl | Leeds United | Anton Stach | 95.0% | 85.19% | 23 |
| bundesliga | Bayer Leverkusen | Aleix Garcia | 85.71% | 91.3% | 42 |
| ligue-1 | Lens | Florian Thauvin | 83.33% | 80.33% | 49 |
| la-liga | Málaga | Pablo Martinez | 80.0% | 72.09% | 31 |
| ligue-1 | Brest | Joris Chotard | 78.57% | 90.32% | 28 |
| epl | Crystal Palace | Adam Wharton | 76.47% | 64.29% | 18 |
| bundesliga | RB Leipzig | David Raum | 71.43% | 90.0% | 36 |
| epl | Coventry City | Jack Rudoni | 69.23% | 40.0% | 10 |
| la-liga | Real Madrid | Arda Guler | 68.42% | 50.0% | 28 |
| ligue-1 | Monaco | Aleksandr Golovin | 66.67% | 45.45% | 10 |
| serie-a | Monza | Samuele Birindelli | 65.0% | 44.83% | 13 |

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
