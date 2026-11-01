# Assist Value Set-Piece Source Audit

Fetched at UTC: `2026-11-01T14:13:31+00:00`

## Decision

Overall: **PASS_SOURCE_LAYER**

- RotoWire public player pages are accepted as the primary Big-5 role source if every team returns a set-piece block.
- Official FPL API is accepted as the Premier League validator if it returns current set-piece order fields.
- SetPieceTakers is rejected as a live primary while row timestamps are stale and CSV export is disabled.
- RotoWire week numbers can exceed domestic league matchweeks, so the feed is a role source, not a league-only historical-volume source.

## RotoWire

- Teams with set-piece blocks: `96/96`
- Player role rows extracted: `735`

| League | Teams OK | Teams | Role rows | Max latest week |
|---|---:|---:|---:|---:|
| bundesliga | 18 | 18 | 117 | 11 |
| epl | 20 | 20 | 147 | 12 |
| la-liga | 20 | 20 | 175 | 14 |
| ligue-1 | 18 | 18 | 138 | 12 |
| serie-a | 20 | 20 | 158 | 13 |

## FPL API

- Status: `PASS`
- Teams: `20`
- Players: `670`
- Players with set-piece role fields: `143`
- Registered season: `2026/27`
- Exact 20-team roster match: `YES`
- Snapshot valid until UTC: `2026-11-08T14:13:31+00:00`

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
| bundesliga | FSV Mainz 05 | Nadiem Amiri | 91.67% | 96.3% | 26 |
| serie-a | Frosinone | Giacomo Calo | 91.67% | 95.83% | 46 |
| serie-a | Como | Luis Milla | 88.89% | 67.27% | 37 |
| la-liga | Real Madrid | Arda Guler | 82.35% | 54.1% | 33 |
| bundesliga | Bayer Leverkusen | Aleix Garcia | 82.14% | 89.83% | 53 |
| ligue-1 | AJ Auxerre | Romain Faivre | 80.95% | 65.71% | 23 |
| epl | Leeds United | Anton Stach | 78.95% | 77.78% | 28 |
| ligue-1 | Lens | Florian Thauvin | 78.95% | 80.95% | 51 |
| ligue-1 | Brest | Joris Chotard | 78.57% | 90.32% | 28 |
| bundesliga | RB Leipzig | David Raum | 76.47% | 91.11% | 41 |
| ligue-1 | Troyes | Antoine Mille | 75.0% | 42.22% | 19 |
| la-liga | Málaga | Pablo Martinez | 73.91% | 70.45% | 31 |
| ligue-1 | Strasbourg | Giovanni Reyna | 71.43% | 41.67% | 5 |

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
