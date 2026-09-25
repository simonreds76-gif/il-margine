# Assist Value Set-Piece Source Audit

Fetched at UTC: `2026-09-25T12:43:08+00:00`

## Decision

Overall: **PASS_SOURCE_LAYER**

- RotoWire public player pages are accepted as the primary Big-5 role source if every team returns a set-piece block.
- Official FPL API is accepted as the Premier League validator if it returns current set-piece order fields.
- SetPieceTakers is rejected as a live primary while row timestamps are stale and CSV export is disabled.
- RotoWire week numbers can exceed domestic league matchweeks, so the feed is a role source, not a league-only historical-volume source.

## RotoWire

- Teams with set-piece blocks: `96/96`
- Player role rows extracted: `577`

| League | Teams OK | Teams | Role rows | Max latest week |
|---|---:|---:|---:|---:|
| bundesliga | 18 | 18 | 93 | 5 |
| epl | 20 | 20 | 113 | 6 |
| la-liga | 20 | 20 | 143 | 8 |
| ligue-1 | 18 | 18 | 114 | 7 |
| serie-a | 20 | 20 | 114 | 6 |

## FPL API

- Status: `PASS`
- Teams: `20`
- Players: `667`
- Players with set-piece role fields: `134`
- Registered season: `2026/27`
- Exact 20-team roster match: `YES`
- Snapshot valid until UTC: `2026-10-02T12:43:08+00:00`

## SetPieceTakers

- Pages checked: `15`
- Stale March 20 pages: `0`
- CSV-disabled pages: `0`
- Decision: `REJECT_AS_LIVE_PRIMARY`

## Top Last-5 Corner Role Shares From RotoWire

| League | Team | Player | Last-5 corner share | Season corner share | Corner total |
|---|---|---|---:|---:|---:|
| bundesliga | FSV Mainz 05 | Nadiem Amiri | 100.0% | 100.0% | 17 |
| bundesliga | RB Leipzig | David Raum | 100.0% | 100.0% | 26 |
| bundesliga | SV 07 Elversberg | Felix Keidel | 100.0% | 100.0% | 10 |
| serie-a | Frosinone | Giacomo Calo | 100.0% | 100.0% | 24 |
| ligue-1 | Angers | Branco van den Boomen | 97.3% | 97.3% | 36 |
| bundesliga | Bayer Leverkusen | Aleix Garcia | 96.67% | 96.67% | 29 |
| bundesliga | FC Schalke 04 | Adil Aouchiche | 91.67% | 91.67% | 11 |
| ligue-1 | Brest | Joris Chotard | 91.3% | 91.3% | 21 |
| epl | Liverpool | Dominik Szoboszlai | 88.24% | 91.3% | 21 |
| la-liga | Getafe | Johan Mojica | 87.5% | 53.85% | 14 |
| la-liga | Rayo Vallecano | Unai Lopez | 85.71% | 85.71% | 24 |
| bundesliga | Union Berlin | Josip Juranovic | 83.33% | 83.33% | 10 |
| epl | Aston Villa | John McGinn | 81.82% | 75.0% | 9 |
| epl | Leeds United | Anton Stach | 80.95% | 80.95% | 17 |
| bundesliga | Eintracht Frankfurt | Can Uzun | 80.0% | 80.0% | 12 |

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
