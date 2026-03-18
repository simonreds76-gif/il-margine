# Goalscorer Model

Current scope:
- market: anytime goalscorer
- league: Serie A
- calibration mode: confirmed-lineup first

Why confirmed-lineup first:
- minutes are the biggest source of error in goalscorer pricing
- this lets us test the probability engine without pretending we already have a strong pre-lineup minutes model

Scripts:
- `scripts/fbref-scrape-serie-a.py`
  - scrapes Serie A player match logs from FBref
  - outputs `data/goalscorer/serie-a-player-match-logs-{season}.csv`
- `scripts/understat-scrape-serie-a.py`
  - practical fallback scraper when FBref blocks
  - uses Understat JSON endpoints
  - writes the same CSV shape as the model expects
- `scripts/goalscorer-model.py`
  - loads one or more historical player-log CSVs
  - processes matches chronologically
  - estimates `P(scores >= 1)` for each player-match row
  - writes calibration outputs to `data/goalscorer/`

Recommended first run:

```bash
python scripts/understat-scrape-serie-a.py --season 2023-2024
python scripts/understat-scrape-serie-a.py --season 2024-2025
python scripts/understat-scrape-serie-a.py --season 2025-2026
python scripts/goalscorer-model.py --data data/goalscorer/serie-a-player-match-logs-2023-2024.csv data/goalscorer/serie-a-player-match-logs-2024-2025.csv data/goalscorer/serie-a-player-match-logs-2025-2026.csv
```

Outputs:
- `data/goalscorer/goalscorer-backtest-results.csv`
- `data/goalscorer/goalscorer-calibration.txt`
- `data/goalscorer/goalscorer-calibration-bins.csv`

What this first version already does:
- chronological processing with no future leakage
- proper date parsing
- preserved unknown starter state
- team attack and opponent defence context
- penalty component based on team penalty rate and player share, not raw player attempts alone
- calibration summaries by probability bucket, position, minutes band, and penalty role

What still comes next:
- live odds capture for ATGS
- pre-lineup minutes model
- stronger shrinkage / tuning once real scraped data is in
- public website output once the calibration looks strong enough

Odds workflow:
- `data/goalscorer/goalscorer-odds-template.csv`
  - one-row example of the canonical ATGS odds format
- `scripts/odds-api-scrape-goalscorer.py`
  - preferred live source when `ODDS_API_KEY` is configured
  - fetches Serie A events from `odds-api.io` and extracts ATGS markets for selected bookmakers
- `scripts/pinnacle-scrape-goalscorer.py`
  - scrapes live Pinnacle Serie A `Player Props / To Score` markets
  - writes canonical ATGS rows straight into `data/goalscorer/inbox/`
- `scripts/goalscorer-odds-archive.py`
  - imports manual or scraped ATGS prices into `data/goalscorer/goalscorer-odds-history.csv`
  - optional `--supabase` upload to `goalscorer_odds_history`
- `scripts/goalscorer-compare-odds.py`
  - joins archived ATGS prices to `goalscorer-backtest-results.csv`
  - outputs model-vs-market EV and realized ROI summaries
- `scripts/goalscorer-historical-backtest.py`
  - selects one archived historical capture per player/bookmaker/match
  - reports EV, ROI, and closing-price context
- `scripts/the-odds-api-historical-goalscorer.py`
  - backfills historical Serie A ATGS snapshots from The Odds API
  - writes canonical rows ready for `goalscorer-odds-archive.py`
- `scripts/goalscorer-live-compare.py`
  - prices upcoming ATGS rows pre-match using the historical model plus live Understat roster fallback
  - tags each row with:
    - `resolver_source`
    - `signal_confidence`
    - `public_action`
  - writes both the current live comparison and a timestamped snapshot under `data/goalscorer/live-history/`
- `scripts/goalscorer-live-snapshot.py`
  - snapshots the live comparison, shadow tracker and lineup files into one JSON payload
  - optional `--supabase` upload to `goalscorer_live_snapshot`
  - intended for deployed Next.js pages that cannot see the local runtime CSVs directly

Recommended odds workflow right now:

```bash
python scripts/run-goalscorer-pipeline.py --fetch-odds-api --bookmaker Bet365
```

Historical backtest workflow:

```bash
python scripts/the-odds-api-historical-goalscorer.py --date-from 2023-08-01 --date-to 2024-05-31 --offset-minutes 60 --bookmakers fanduel,draftkings,betmgm
python scripts/goalscorer-odds-archive.py --input data/goalscorer/inbox/the-odds-api-historical-atgs-*.csv
python scripts/goalscorer-historical-backtest.py --bookmaker FanDuel --selection target_before_kickoff --target-minutes-before 60
```

Historical backtest outputs:
- `data/goalscorer/goalscorer-historical-backtest.csv`
- `data/goalscorer/goalscorer-historical-backtest.txt`
- `data/goalscorer/goalscorer-historical-backtest-segments.csv`

Supabase schema:
- `docs/supabase-goalscorer-odds-history.sql`
- `docs/supabase-goalscorer-live-snapshot.sql`

One-command workflow:
- `scripts/run-goalscorer-pipeline.py`
  - reruns the goalscorer model from the historical CSVs
  - imports any ATGS odds files found in `data/goalscorer/inbox/`
  - runs the historical comparison report automatically
  - runs the live comparison with confidence gating and snapshot logging
