# Assist Value Set-Piece Source Audit

Fetched at UTC: `2026-10-31T13:34:54+00:00`

## Decision

Overall: **PASS_SOURCE_LAYER**

- RotoWire public player pages are accepted as the primary Big-5 role source if every team returns a set-piece block.
- Official FPL API is accepted as the Premier League validator if it returns current set-piece order fields.
- SetPieceTakers is rejected as a live primary while row timestamps are stale and CSV export is disabled.
- RotoWire week numbers can exceed domestic league matchweeks, so the feed is a role source, not a league-only historical-volume source.

## RotoWire

- Teams with set-piece blocks: `96/96`
- Player role rows extracted: `729`

| League | Teams OK | Teams | Role rows | Max latest week |
|---|---:|---:|---:|---:|
| bundesliga | 18 | 18 | 116 | 11 |
| epl | 20 | 20 | 145 | 12 |
| la-liga | 20 | 20 | 173 | 14 |
| ligue-1 | 18 | 18 | 138 | 12 |
| serie-a | 20 | 20 | 157 | 12 |

## FPL API

- Status: `PASS`
- Teams: `20`
- Players: `669`
- Players with set-piece role fields: `143`
- Registered season: `2026/27`
- Exact 20-team roster match: `YES`
- Snapshot valid until UTC: `2026-11-07T13:34:54+00:00`

## SetPieceTakers

- Pages checked: `15`
- Stale March 20 pages: `0`
- CSV-disabled pages: `0`
- Decision: `REJECT_AS_LIVE_PRIMARY`

## Top Last-5 Corner Role Shares From RotoWire

| League | Team | Player | Last-5 corner share | Season corner share | Corner total |
|---|---|---|---:|---:|---:|
| ligue-1 | Angers | Branco van den Boomen | 100.0% | 97.92% | 47 |
| bundesliga | SV 07 Elversberg | Felix Keidel | 93.33% | 95.45% | 21 |
| serie-a | Frosinone | Giacomo Calo | 93.1% | 95.74% | 45 |
| bundesliga | FSV Mainz 05 | Nadiem Amiri | 91.67% | 96.3% | 26 |
| epl | Leeds United | Anton Stach | 89.47% | 81.25% | 26 |
| bundesliga | Bayer Leverkusen | Aleix Garcia | 83.33% | 91.84% | 45 |
| la-liga | Málaga | Pablo Martinez | 80.0% | 72.09% | 31 |
| serie-a | Como | Luis Milla | 80.0% | 64.71% | 33 |
| ligue-1 | Lens | Florian Thauvin | 78.95% | 80.95% | 51 |
| ligue-1 | Brest | Joris Chotard | 78.57% | 90.32% | 28 |
| ligue-1 | AJ Auxerre | Romain Faivre | 78.26% | 65.71% | 23 |
| la-liga | Real Madrid | Arda Guler | 73.91% | 54.1% | 33 |
| epl | Coventry City | Jack Rudoni | 69.23% | 40.0% | 10 |
| epl | Crystal Palace | Adam Wharton | 66.67% | 57.14% | 20 |
| bundesliga | RB Leipzig | David Raum | 66.67% | 90.0% | 36 |

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
