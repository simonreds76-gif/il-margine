# Football Model Input Audit

Generated: 2026-04-25T16:06:24+00:00

## Summary

| Area | Rows | Latest date | Freshness | Notes |
| --- | ---: | --- | ---: | --- |
| team_shots_fbref_matches | 1520 | 2026-04-23 | 2 | ok |
| team_shots_football_data_matches | 1520 | 2026-04-23 | 2 | ok |
| corners_historical_matches | 21357 | 2026-04-23 | 2 | ok |
| corners_pinnacle_odds | 13738 | 2026-04-27 | -2 | ok |
| team_shots_odds_history | 1576 | 2026-04-27 | -2 | ok |
| goalscorer_odds_history | 208815 | 2026-04-27 | -2 | ok |
| goalscorer_player_logs | 148258 | 2026-04-24 | 1 | 15 files |

## Issues

- No hard input-audit issues detected.

## Dataset Coverage

### team_shots_fbref_matches

- Path: `data/team-shots/fbref/all-fbref-matches.csv`
- Owner: team-shots
- Role: FBref match-level shots, SOT, corners, xG, and 1X2 odds
- Date field: `date`

| Field group | Columns | Populated rows | Coverage |
| --- | --- | ---: | ---: |
| xg | `home_xg`, `away_xg` | 1391 | 91.51% |
| npxg | - | 0 | 0.00% |
| shots | `home_shots`, `away_shots` | 1520 | 100.00% |
| shots_on_target | `home_sot`, `away_sot` | 1520 | 100.00% |
| corners | `home_corners`, `away_corners` | 1520 | 100.00% |
| book_odds | `B365H`, `B365D`, `B365A` | 1520 | 100.00% |
| player_identity | - | 0 | 0.00% |
| minutes | - | 0 | 0.00% |

### team_shots_football_data_matches

- Path: `data/team-shots/historical/all-historical-matches.csv`
- Owner: team-shots
- Role: Football-Data match-level shots, SOT, corners, goals, and bookmaker odds
- Date field: `Date`

| Field group | Columns | Populated rows | Coverage |
| --- | --- | ---: | ---: |
| xg | - | 0 | 0.00% |
| npxg | - | 0 | 0.00% |
| shots | `HS`, `AS` | 1520 | 100.00% |
| shots_on_target | `HST`, `AST` | 1520 | 100.00% |
| corners | `HC`, `AC` | 1520 | 100.00% |
| book_odds | `B365H`, `B365D`, `B365A` | 1520 | 100.00% |
| player_identity | - | 0 | 0.00% |
| minutes | - | 0 | 0.00% |

### corners_historical_matches

- Path: `data/corners-ou/historical/all-historical-matches.csv`
- Owner: corners
- Role: Football-Data historical corners and 1X2 odds
- Date field: `Date`

| Field group | Columns | Populated rows | Coverage |
| --- | --- | ---: | ---: |
| xg | - | 0 | 0.00% |
| npxg | - | 0 | 0.00% |
| shots | `HS`, `AS` | 21355 | 99.99% |
| shots_on_target | `HST`, `AST` | 21351 | 99.97% |
| corners | `HC`, `AC` | 21355 | 99.99% |
| book_odds | `B365H`, `B365D`, `B365A` | 21351 | 99.97% |
| player_identity | - | 0 | 0.00% |
| minutes | - | 0 | 0.00% |

### corners_pinnacle_odds

- Path: `data/corners-ou/pinnacle-corners-odds.csv`
- Owner: corners
- Role: Pinnacle corners O/U snapshots for CLV and live market comparison
- Date field: `match_date`

| Field group | Columns | Populated rows | Coverage |
| --- | --- | ---: | ---: |
| xg | - | 0 | 0.00% |
| npxg | - | 0 | 0.00% |
| shots | - | 0 | 0.00% |
| shots_on_target | - | 0 | 0.00% |
| corners | - | 0 | 0.00% |
| book_odds | `odds_decimal` | 13738 | 100.00% |
| player_identity | - | 0 | 0.00% |
| minutes | - | 0 | 0.00% |

### team_shots_odds_history

- Path: `data/team-shots/team-shots-odds-history.csv`
- Owner: team-shots
- Role: Bookmaker team-shots O/U snapshots
- Date field: `match_date`

| Field group | Columns | Populated rows | Coverage |
| --- | --- | ---: | ---: |
| xg | - | 0 | 0.00% |
| npxg | - | 0 | 0.00% |
| shots | - | 0 | 0.00% |
| shots_on_target | - | 0 | 0.00% |
| corners | - | 0 | 0.00% |
| book_odds | `odds_decimal` | 1576 | 100.00% |
| player_identity | - | 0 | 0.00% |
| minutes | - | 0 | 0.00% |

### goalscorer_odds_history

- Path: `data/goalscorer/goalscorer-odds-history.csv`
- Owner: goalscorer
- Role: Bookmaker anytime-goalscorer odds snapshots
- Date field: `match_date`

| Field group | Columns | Populated rows | Coverage |
| --- | --- | ---: | ---: |
| xg | - | 0 | 0.00% |
| npxg | - | 0 | 0.00% |
| shots | - | 0 | 0.00% |
| shots_on_target | - | 0 | 0.00% |
| corners | - | 0 | 0.00% |
| book_odds | `odds_decimal` | 208815 | 100.00% |
| player_identity | `player_name` | 208815 | 100.00% |
| minutes | - | 0 | 0.00% |

## Model Script Signal Map

| Script | Understat | FBref | FotMob | xG | Shots | Corners | Odds | Rolling | Data paths |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `scripts/team-shots-model.py` | 0 | 18 | 0 | 122 | 183 | 32 | 24 | 81 | 4 |
| `scripts/team-shots-compare.py` | 0 | 0 | 0 | 1 | 32 | 0 | 59 | 10 | 0 |
| `scripts/team-shots-shadow-tracker.py` | 0 | 1 | 0 | 0 | 18 | 2 | 37 | 0 | 0 |
| `scripts/corners-ou-model.py` | 0 | 0 | 0 | 0 | 2 | 134 | 56 | 39 | 2 |
| `scripts/corners-ou-backtest.py` | 0 | 0 | 0 | 0 | 0 | 116 | 27 | 19 | 2 |
| `scripts/matchday-shortlist.py` | 0 | 0 | 0 | 0 | 2 | 105 | 134 | 86 | 1 |
| `scripts/goalscorer-model.py` | 0 | 0 | 0 | 209 | 19 | 0 | 1 | 62 | 5 |
| `scripts/goalscorer-live-compare.py` | 10 | 0 | 2 | 143 | 2 | 0 | 129 | 60 | 6 |
| `scripts/goalscorer-shadow-tracker.py` | 1 | 0 | 0 | 0 | 0 | 0 | 70 | 3 | 3 |
| `scripts/understat-scrape-serie-a.py` | 13 | 0 | 0 | 68 | 10 | 0 | 0 | 0 | 1 |
| `scripts/fbref-download-shooting.py` | 16 | 6 | 0 | 59 | 15 | 12 | 20 | 1 | 1 |
| `scripts/fbref-scrape-serie-a.py` | 0 | 15 | 0 | 47 | 16 | 0 | 0 | 3 | 2 |
| `scripts/fotmob_match_stats.py` | 0 | 0 | 13 | 0 | 27 | 30 | 0 | 3 | 2 |
| `scripts/fotmob-fetch-lineups.py` | 3 | 0 | 21 | 0 | 0 | 0 | 0 | 9 | 2 |

## Immediate Interpretation

- Team shots already has an xG-enriched FBref source, but xG is blended inside the model rather than supplied by a canonical team-form table.
- Corners is currently mostly corners-history plus 1X2 market context; it does not consume xG/pressure features directly.
- Goalscorer already consumes player xG/npxG, team_xg, and team_xga, but the team form layer is embedded in the goalscorer script.
- The next implementation step should create a generated team-match/team-form table, then backtest consumers before replacing any model inputs.
