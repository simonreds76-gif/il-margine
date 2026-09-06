# Assist Value Set-Piece Source Audit

Fetched at UTC: `2026-09-06T11:37:19+00:00`

## Decision

Overall: **PASS_SOURCE_LAYER**

- RotoWire public player pages are accepted as the primary Big-5 role source if every team returns a set-piece block.
- Official FPL API is accepted as the Premier League validator if it returns current set-piece order fields.
- SetPieceTakers is rejected as a live primary while row timestamps are stale and CSV export is disabled.
- RotoWire week numbers can exceed domestic league matchweeks, so the feed is a role source, not a league-only historical-volume source.

## RotoWire

- Teams with set-piece blocks: `96/96`
- Player role rows extracted: `451`

| League | Teams OK | Teams | Role rows | Max latest week |
|---|---:|---:|---:|---:|
| bundesliga | 18 | 18 | 69 | 2 |
| epl | 20 | 20 | 90 | 3 |
| la-liga | 20 | 20 | 116 | 4 |
| ligue-1 | 18 | 18 | 89 | 4 |
| serie-a | 20 | 20 | 87 | 3 |

## FPL API

- Status: `PASS`
- Teams: `20`
- Players: `653`
- Players with set-piece role fields: `135`
- Registered season: `2026/27`
- Exact 20-team roster match: `YES`
- Snapshot valid until UTC: `2026-09-13T11:37:19+00:00`

## SetPieceTakers

- Pages checked: `15`
- Stale March 20 pages: `0`
- CSV-disabled pages: `0`
- Decision: `REJECT_AS_LIVE_PRIMARY`

## Top Last-5 Corner Role Shares From RotoWire

| League | Team | Player | Last-5 corner share | Season corner share | Corner total |
|---|---|---|---:|---:|---:|
| epl | Crystal Palace | Yeremy Pino | 100.0% | 100.0% | 3 |
| epl | Liverpool | Dominik Szoboszlai | 100.0% | 100.0% | 11 |
| bundesliga | Eintracht Frankfurt | Fares Chaibi | 100.0% | 100.0% | 2 |
| bundesliga | FC Schalke 04 | Adil Aouchiche | 100.0% | 100.0% | 3 |
| bundesliga | FSV Mainz 05 | Nadiem Amiri | 100.0% | 100.0% | 10 |
| bundesliga | Hamburger SV | Albert Gronbaek | 100.0% | 100.0% | 1 |
| bundesliga | RB Leipzig | David Raum | 100.0% | 100.0% | 11 |
| bundesliga | SV 07 Elversberg | Felix Keidel | 100.0% | 100.0% | 6 |
| bundesliga | Union Berlin | Josip Juranovic | 100.0% | 100.0% | 6 |
| ligue-1 | Brest | Joris Chotard | 100.0% | 100.0% | 17 |
| serie-a | Frosinone | Giacomo Calo | 100.0% | 100.0% | 8 |
| ligue-1 | Angers | Branco van den Boomen | 94.44% | 94.44% | 17 |
| ligue-1 | Lens | Florian Thauvin | 93.33% | 93.33% | 14 |
| bundesliga | Bayer Leverkusen | Aleix Garcia | 88.89% | 88.89% | 8 |
| epl | Sunderland | Granit Xhaka | 85.71% | 85.71% | 6 |

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
