# Assist Value Set-Piece Source Audit

Fetched at UTC: `2026-09-19T11:54:17+00:00`

## Decision

Overall: **PASS_SOURCE_LAYER**

- RotoWire public player pages are accepted as the primary Big-5 role source if every team returns a set-piece block.
- Official FPL API is accepted as the Premier League validator if it returns current set-piece order fields.
- SetPieceTakers is rejected as a live primary while row timestamps are stale and CSV export is disabled.
- RotoWire week numbers can exceed domestic league matchweeks, so the feed is a role source, not a league-only historical-volume source.

## RotoWire

- Teams with set-piece blocks: `96/96`
- Player role rows extracted: `540`

| League | Teams OK | Teams | Role rows | Max latest week |
|---|---:|---:|---:|---:|
| bundesliga | 18 | 18 | 86 | 5 |
| epl | 20 | 20 | 105 | 6 |
| la-liga | 20 | 20 | 137 | 7 |
| ligue-1 | 18 | 18 | 104 | 6 |
| serie-a | 20 | 20 | 108 | 5 |

## FPL API

- Status: `PASS`
- Teams: `20`
- Players: `662`
- Players with set-piece role fields: `134`
- Registered season: `2026/27`
- Exact 20-team roster match: `YES`
- Snapshot valid until UTC: `2026-09-26T11:54:17+00:00`

## SetPieceTakers

- Pages checked: `15`
- Stale March 20 pages: `0`
- CSV-disabled pages: `0`
- Decision: `REJECT_AS_LIVE_PRIMARY`

## Top Last-5 Corner Role Shares From RotoWire

| League | Team | Player | Last-5 corner share | Season corner share | Corner total |
|---|---|---|---:|---:|---:|
| bundesliga | FSV Mainz 05 | Nadiem Amiri | 100.0% | 100.0% | 15 |
| bundesliga | RB Leipzig | David Raum | 100.0% | 100.0% | 20 |
| bundesliga | SV 07 Elversberg | Felix Keidel | 100.0% | 100.0% | 7 |
| serie-a | Frosinone | Giacomo Calo | 100.0% | 100.0% | 18 |
| ligue-1 | Angers | Branco van den Boomen | 97.14% | 97.14% | 34 |
| bundesliga | Bayer Leverkusen | Aleix Garcia | 96.0% | 96.0% | 24 |
| epl | Liverpool | Dominik Szoboszlai | 95.0% | 95.0% | 19 |
| ligue-1 | Brest | Joris Chotard | 95.0% | 95.0% | 19 |
| bundesliga | FC Schalke 04 | Adil Aouchiche | 87.5% | 87.5% | 7 |
| bundesliga | Union Berlin | Josip Juranovic | 83.33% | 83.33% | 10 |
| la-liga | Rayo Vallecano | Unai Lopez | 83.33% | 84.0% | 21 |
| epl | Aston Villa | John McGinn | 80.0% | 72.73% | 8 |
| ligue-1 | Lens | Florian Thauvin | 77.14% | 78.38% | 29 |
| bundesliga | Eintracht Frankfurt | Can Uzun | 76.92% | 76.92% | 10 |
| epl | Leeds United | Anton Stach | 76.47% | 76.47% | 13 |

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
