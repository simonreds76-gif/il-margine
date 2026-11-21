# Assist Value Set-Piece Source Audit

Fetched at UTC: `2026-11-21T15:15:49+00:00`

## Decision

Overall: **PASS_SOURCE_LAYER**

- RotoWire public player pages are accepted as the primary Big-5 role source if every team returns a set-piece block.
- Official FPL API is accepted as the Premier League validator if it returns current set-piece order fields.
- SetPieceTakers is rejected as a live primary while row timestamps are stale and CSV export is disabled.
- RotoWire week numbers can exceed domestic league matchweeks, so the feed is a role source, not a league-only historical-volume source.

## RotoWire

- Teams with set-piece blocks: `96/96`
- Player role rows extracted: `766`

| League | Teams OK | Teams | Role rows | Max latest week |
|---|---:|---:|---:|---:|
| bundesliga | 18 | 18 | 123 | 14 |
| epl | 20 | 20 | 153 | 15 |
| la-liga | 20 | 20 | 180 | 16 |
| ligue-1 | 18 | 18 | 145 | 15 |
| serie-a | 20 | 20 | 165 | 16 |

## FPL API

- Status: `PASS`
- Teams: `20`
- Players: `672`
- Players with set-piece role fields: `150`
- Registered season: `2026/27`
- Exact 20-team roster match: `YES`
- Snapshot valid until UTC: `2026-11-28T15:15:49+00:00`

## SetPieceTakers

- Pages checked: `15`
- Stale March 20 pages: `0`
- CSV-disabled pages: `0`
- Decision: `REJECT_AS_LIVE_PRIMARY`

## Top Last-5 Corner Role Shares From RotoWire

| League | Team | Player | Last-5 corner share | Season corner share | Corner total |
|---|---|---|---:|---:|---:|
| bundesliga | Eintracht Frankfurt | Fares Chaibi | 100.0% | 55.56% | 20 |
| bundesliga | SV 07 Elversberg | Felix Keidel | 94.12% | 96.43% | 27 |
| serie-a | Como | Luis Milla | 94.12% | 70.97% | 44 |
| ligue-1 | AJ Auxerre | Romain Faivre | 93.75% | 66.67% | 24 |
| bundesliga | FSV Mainz 05 | Nadiem Amiri | 93.33% | 96.88% | 31 |
| bundesliga | Bayer Leverkusen | Aleix Garcia | 91.67% | 91.43% | 64 |
| serie-a | Frosinone | Giacomo Calo | 91.18% | 95.16% | 59 |
| ligue-1 | Brest | Joris Chotard | 90.91% | 91.18% | 31 |
| ligue-1 | Lens | Florian Thauvin | 84.21% | 81.69% | 58 |
| ligue-1 | Angers | Branco van den Boomen | 83.33% | 92.73% | 51 |
| ligue-1 | Paris FC | Pablo Pagis | 78.95% | 64.52% | 20 |
| la-liga | Athletic | Alex Berenguer | 78.95% | 59.38% | 38 |
| epl | Coventry City | Jack Rudoni | 78.57% | 50.0% | 16 |
| bundesliga | 1. FC Köln | Borna Sosa | 78.57% | 26.09% | 12 |
| la-liga | Valencia | Javi Guerra | 75.0% | 30.23% | 13 |

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
