# Assist Value Set-Piece Source Audit

Fetched at UTC: `2026-10-16T12:21:14+00:00`

## Decision

Overall: **PASS_SOURCE_LAYER**

- RotoWire public player pages are accepted as the primary Big-5 role source if every team returns a set-piece block.
- Official FPL API is accepted as the Premier League validator if it returns current set-piece order fields.
- SetPieceTakers is rejected as a live primary while row timestamps are stale and CSV export is disabled.
- RotoWire week numbers can exceed domestic league matchweeks, so the feed is a role source, not a league-only historical-volume source.

## RotoWire

- Teams with set-piece blocks: `96/96`
- Player role rows extracted: `639`

| League | Teams OK | Teams | Role rows | Max latest week |
|---|---:|---:|---:|---:|
| bundesliga | 18 | 18 | 103 | 7 |
| epl | 20 | 20 | 130 | 8 |
| la-liga | 20 | 20 | 152 | 10 |
| ligue-1 | 18 | 18 | 121 | 9 |
| serie-a | 20 | 20 | 133 | 8 |

## FPL API

- Status: `PASS`
- Teams: `20`
- Players: `667`
- Players with set-piece role fields: `139`
- Registered season: `2026/27`
- Exact 20-team roster match: `YES`
- Snapshot valid until UTC: `2026-10-23T12:21:14+00:00`

## SetPieceTakers

- Pages checked: `15`
- Stale March 20 pages: `0`
- CSV-disabled pages: `0`
- Decision: `REJECT_AS_LIVE_PRIMARY`

## Top Last-5 Corner Role Shares From RotoWire

| League | Team | Player | Last-5 corner share | Season corner share | Corner total |
|---|---|---|---:|---:|---:|
| bundesliga | FSV Mainz 05 | Nadiem Amiri | 100.0% | 100.0% | 19 |
| bundesliga | RB Leipzig | David Raum | 100.0% | 100.0% | 33 |
| bundesliga | SV 07 Elversberg | Felix Keidel | 100.0% | 100.0% | 11 |
| ligue-1 | Angers | Branco van den Boomen | 100.0% | 97.56% | 40 |
| serie-a | Frosinone | Giacomo Calo | 100.0% | 100.0% | 28 |
| la-liga | Rayo Vallecano | Unai Lopez | 93.75% | 85.71% | 24 |
| bundesliga | Bayer Leverkusen | Aleix Garcia | 92.59% | 91.67% | 33 |
| ligue-1 | Brest | Joris Chotard | 90.0% | 92.31% | 24 |
| epl | Leeds United | Anton Stach | 86.96% | 84.0% | 21 |
| bundesliga | Eintracht Frankfurt | Can Uzun | 84.21% | 84.21% | 16 |
| ligue-1 | Lens | Florian Thauvin | 78.79% | 83.33% | 40 |
| bundesliga | FC Schalke 04 | Adil Aouchiche | 78.57% | 78.57% | 11 |
| la-liga | Getafe | Johan Mojica | 78.57% | 51.85% | 14 |
| la-liga | Málaga | Pablo Martinez | 77.42% | 71.05% | 27 |
| ligue-1 | Strasbourg | Oso | 75.0% | 42.86% | 3 |

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
