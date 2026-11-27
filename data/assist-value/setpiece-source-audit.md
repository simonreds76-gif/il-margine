# Assist Value Set-Piece Source Audit

Fetched at UTC: `2026-11-27T17:24:24+00:00`

## Decision

Overall: **PASS_SOURCE_LAYER**

- RotoWire public player pages are accepted as the primary Big-5 role source if every team returns a set-piece block.
- Official FPL API is accepted as the Premier League validator if it returns current set-piece order fields.
- SetPieceTakers is rejected as a live primary while row timestamps are stale and CSV export is disabled.
- RotoWire week numbers can exceed domestic league matchweeks, so the feed is a role source, not a league-only historical-volume source.

## RotoWire

- Teams with set-piece blocks: `96/96`
- Player role rows extracted: `790`

| League | Teams OK | Teams | Role rows | Max latest week |
|---|---:|---:|---:|---:|
| bundesliga | 18 | 18 | 125 | 15 |
| epl | 20 | 20 | 159 | 16 |
| la-liga | 20 | 20 | 182 | 18 |
| ligue-1 | 18 | 18 | 153 | 17 |
| serie-a | 20 | 20 | 171 | 17 |

## FPL API

- Status: `PASS`
- Teams: `20`
- Players: `674`
- Players with set-piece role fields: `148`
- Registered season: `2026/27`
- Exact 20-team roster match: `YES`
- Snapshot valid until UTC: `2026-12-04T17:24:24+00:00`

## SetPieceTakers

- Pages checked: `15`
- Stale March 20 pages: `0`
- CSV-disabled pages: `0`
- Decision: `REJECT_AS_LIVE_PRIMARY`

## Top Last-5 Corner Role Shares From RotoWire

| League | Team | Player | Last-5 corner share | Season corner share | Corner total |
|---|---|---|---:|---:|---:|
| bundesliga | Eintracht Frankfurt | Fares Chaibi | 100.0% | 61.9% | 26 |
| bundesliga | RB Leipzig | David Raum | 100.0% | 93.1% | 54 |
| ligue-1 | AJ Auxerre | Romain Faivre | 100.0% | 66.67% | 24 |
| serie-a | Como | Luis Milla | 100.0% | 71.43% | 45 |
| ligue-1 | Lens | Florian Thauvin | 95.45% | 84.34% | 70 |
| bundesliga | SV 07 Elversberg | Felix Keidel | 94.12% | 96.43% | 27 |
| serie-a | Frosinone | Giacomo Calo | 94.12% | 95.45% | 63 |
| bundesliga | FSV Mainz 05 | Nadiem Amiri | 92.31% | 96.88% | 31 |
| bundesliga | Bayer Leverkusen | Aleix Garcia | 89.66% | 91.03% | 71 |
| ligue-1 | Brest | Joris Chotard | 88.89% | 91.43% | 32 |
| ligue-1 | Paris FC | Pablo Pagis | 84.21% | 69.23% | 27 |
| la-liga | Valencia | Javi Guerra | 82.35% | 37.5% | 18 |
| la-liga | Athletic | Alex Berenguer | 78.95% | 59.38% | 38 |
| bundesliga | 1. FC Köln | Borna Sosa | 78.57% | 26.09% | 12 |
| epl | Liverpool | Dominik Szoboszlai | 75.68% | 56.32% | 49 |

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
