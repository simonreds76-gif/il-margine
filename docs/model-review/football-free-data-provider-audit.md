# Football Free-Data Provider Audit

Verified: 2026-07-14

## Decision

The next useful free source is **API-Football**, which is already partially integrated and has an `API_FOOTBALL_KEY` configured in GitHub Actions. Do not add another frequent workflow. Expand the existing capped settlement path and, once the club season starts, use one nightly collection pass for source-agreement evidence.

The most important local finding is that a new historical provider is not needed for team fouls or cards. The existing 21,589-match Football-Data archive has 100% foul coverage, 97.3% card coverage and 21.7% referee-name coverage. The blocker for a sellable fouls/cards product is captured market prices and bookmaker-definition validation, not historical outcomes.

No free provider supplies unlimited, current, top-five event data with bookmaker-grade definitions. Free sources should therefore have separate roles:

- current settlement and definition checks;
- historical count training;
- offline event-feature research;
- schedules, identity and artwork.

## Provider matrix

| Source | Free access | Useful fields | Coverage/freshness | Best repo role | Decision |
|---|---|---|---|---|---|
| [API-Football](https://www.api-football.com/pricing) | 100 requests/day; all endpoints, limited seasons | shots, SOT, blocked shots, fouls, corners, offsides, cards, saves, lineups, injuries, player match stats | Broad competition coverage; match stats update during live play | Independent current-count source and fallback settlement | **Use now.** Existing adapter and GitHub secret; cap requests and retain nulls. |
| [Football-Data.co.uk](https://www.football-data.co.uk/data.php) | Open CSV downloads | shots, SOT, corners, fouls, cards, referee, results, bookmaker prices | Top-five historical depth; current files may lag | Canonical historical training and delayed settlement | **Keep as canonical history.** It already supplies the 21k-match base. |
| [Sportmonks free plan](https://www.sportmonks.com/football-api/free-plan/) | No-expiry free plan for Danish Superliga and Scottish Premiership | fixtures, events, lineups, team/player statistics | Two leagues only | Definition and parser testing outside the target top-five | **Useful control, not production coverage.** Do not add until an agreement test needs a fourth source. |
| [StatsBomb Open Data](https://github.com/statsbomb/open-data) | Open event/lineup JSON for selected competitions | detailed events, shots, pressures, lineups and some 360 data | Selected historical competitions, not a current top-five feed | Offline feature discovery and event-definition research | **Use for research only.** It cannot settle current bets. |
| [Wyscout open event dataset](https://figshare.com/collections/Soccer_match_event_dataset/4415000/2) | Open research dataset | passes, shots, fouls and spatial event tags | One historical season across five major leagues plus tournaments | Test whether event-derived features improve count forecasts | **Candidate experiment.** Never use it as a current source or ROI record. |
| [SkillCorner Open Data](https://github.com/SkillCorner/opendata) | MIT-licensed sample | tracking, phases of play, dynamic events, physical/off-ball aggregates | Ten matches plus selected aggregates | Small-sample feature prototyping | **Research only.** Too small for model fitting or validation. |
| [Metrica Sports sample data](https://github.com/metrica-sports/sample-data) | Public sample | synchronized tracking and events | Three anonymized matches | Prototype tracking-derived concepts | **Research only.** No production coverage. |
| [football-data.org](https://www.football-data.org/pricing) | Free fixtures/results for 12 competitions | basic scores, fixtures and tables | Top competitions, delayed free scores | Schedule/identity fallback | **Do not use for counts.** Corners, fouls and shots require its paid statistics add-on. |
| [TheSportsDB](https://www.thesportsdb.com/docs_pricing.php) | Limited free API, 30 requests/minute | event search, seasons, team/player metadata and artwork | Broad but community-oriented | Crest/artwork or metadata fallback | **Not a count source.** Existing local assets are safer. |
| [Sportradar trial](https://developer.sportradar.com/soccer/reference/soccer-push-statistics) | Trial access, not a permanent free production tier | deep live team/player statistics | Strong commercial coverage | Temporary schema evaluation | **Reject as a free dependency.** A trial is not a sustainable model input. |
| FotMob internal endpoints | No key, but no supported public API | shots, SOT, corners, lineups, player events | Current and broad; definitions have already disagreed with Football-Data | Secondary fallback and disagreement detector | **Keep fail-closed.** Never make it the sole settlement source. |
| Understat internal endpoints | No key, but no supported public API | xG, npxG and shot events | Major leagues; unofficial endpoint | Existing xG/shot-event overlay | **Keep cached and replaceable.** Do not expand operational dependence. |

## Additional free features worth testing

These are features, not new betting products. Each must beat the current walk-forward baseline before model wiring.

1. **Referee tendencies.** Football-Data.co.uk already provides referee, fouls and cards. This is the cheapest path to a fouls/cards diagnostic; no new provider is needed.
2. **Confirmed lineups and injuries.** API-Football includes both on the free tier. Use only as pre-match deltas after the base count models are stable.
3. **Rest and travel.** Derive rest days from existing fixtures. Stadium coordinates can derive travel distance without scraping another statistics site.
4. **Weather.** [Open-Meteo](https://open-meteo.com/en/docs/historical-weather-api) provides historical wind, rain and temperature data. Test locally first and confirm hosted commercial-use terms before automating it on the public product.
5. **Event-style features.** StatsBomb/Wyscout can test concepts such as blocked-shot share, wide attacks, crossing volume and final-third pressure. They cannot directly calibrate current top-five prices because their samples are selected and old.

## Immediate integration rules

- Keep Football-Data.co.uk as the historical source of record.
- Use API-Football only for current/fallback rows and source-agreement tests until it reaches sufficient overlap.
- Require exact home/away identity; API response ordering is not identity.
- Preserve unavailable values as `null`. Missing SOT is not zero SOT.
- Do not pool definitions across providers until agreement is at least 97% within one count for SOT and separately audited for each new count field.
- Do not create a sellable fouls/cards lane until real market prices are captured. Predictable counts without odds are not a betting edge.
- Do not add another 10-minute scheduler. Piggyback one bounded nightly collection on the existing settlement workflow if a full current-season archive is approved.

## Recommended next acquisition

When the club season resumes, collect one API-Football post-match snapshot for every top-five fixture once per night. A normal full top-five round requires roughly five fixture-list calls plus one statistics call per match, which fits within the 100-request daily free quota. Store raw provider values and provenance, then compare API-Football against Football-Data.co.uk and FotMob before any field enters a model.

Player-level match statistics should not be collected in the same free-tier pass: one additional player-stat request per fixture can exhaust the 100-call allowance on a full weekend. Add those only for shortlisted fixtures or after a measured model need.
