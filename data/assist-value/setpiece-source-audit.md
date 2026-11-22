# Assist Value Set-Piece Source Audit

Fetched at UTC: `2026-11-22T15:13:06+00:00`

## Decision

Overall: **PASS_SOURCE_LAYER**

- RotoWire public player pages are accepted as the primary Big-5 role source if every team returns a set-piece block.
- Official FPL API is accepted as the Premier League validator if it returns current set-piece order fields.
- SetPieceTakers is rejected as a live primary while row timestamps are stale and CSV export is disabled.
- RotoWire week numbers can exceed domestic league matchweeks, so the feed is a role source, not a league-only historical-volume source.

## RotoWire

- Teams with set-piece blocks: `96/96`
- Player role rows extracted: `777`

| League | Teams OK | Teams | Role rows | Max latest week |
|---|---:|---:|---:|---:|
| bundesliga | 18 | 18 | 124 | 14 |
| epl | 20 | 20 | 156 | 15 |
| la-liga | 20 | 20 | 180 | 17 |
| ligue-1 | 18 | 18 | 149 | 16 |
| serie-a | 20 | 20 | 168 | 16 |

## FPL API

- Status: `PASS`
- Teams: `20`
- Players: `674`
- Players with set-piece role fields: `148`
- Registered season: `2026/27`
- Exact 20-team roster match: `YES`
- Snapshot valid until UTC: `2026-11-29T15:13:06+00:00`

## SetPieceTakers

- Pages checked: `15`
- Stale March 20 pages: `0`
- CSV-disabled pages: `0`
- Decision: `REJECT_AS_LIVE_PRIMARY`

## Top Last-5 Corner Role Shares From RotoWire

| League | Team | Player | Last-5 corner share | Season corner share | Corner total |
|---|---|---|---:|---:|---:|
| bundesliga | Eintracht Frankfurt | Fares Chaibi | 100.0% | 61.9% | 26 |
| ligue-1 | AJ Auxerre | Romain Faivre | 100.0% | 66.67% | 24 |
| ligue-1 | Lens | Florian Thauvin | 95.65% | 83.54% | 66 |
| bundesliga | SV 07 Elversberg | Felix Keidel | 94.12% | 96.43% | 27 |
| serie-a | Como | Luis Milla | 94.12% | 70.97% | 44 |
| bundesliga | FSV Mainz 05 | Nadiem Amiri | 92.31% | 96.88% | 31 |
| serie-a | Frosinone | Giacomo Calo | 91.18% | 95.16% | 59 |
| ligue-1 | Brest | Joris Chotard | 88.89% | 91.43% | 32 |
| ligue-1 | Paris FC | Pablo Pagis | 88.89% | 71.05% | 27 |
| bundesliga | Bayer Leverkusen | Aleix Garcia | 88.46% | 90.28% | 65 |
| la-liga | Valencia | Javi Guerra | 82.35% | 37.5% | 18 |
| la-liga | Athletic | Alex Berenguer | 78.95% | 59.38% | 38 |
| bundesliga | 1. FC Köln | Borna Sosa | 78.57% | 26.09% | 12 |
| ligue-1 | Angers | Branco van den Boomen | 78.57% | 92.73% | 51 |
| bundesliga | RB Leipzig | David Raum | 76.47% | 92.45% | 49 |

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
