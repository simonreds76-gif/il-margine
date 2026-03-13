# Handoff: Injury overlay — implement and optionally weight in model

**For:** Codex  
**Goal:** Wire the TennisExplorer injured/returning list into the pipeline and, if we validate it, use it to flag or downweight players in the model or strict policy.

---

## What’s already in place (Cursor)

1. **Scraper:** `scripts/scrape-tennisexplorer-injured.py`
   - Fetches TennisExplorer “Injured players” and “Returning players”.
   - Writes `data/injured-players-tennisexplorer.csv`.
   - Columns: `scraped_at`, `date`, `player_name`, `player_slug`, `tournament`, `reason` (retired | walkover), `source` (injured | returning).
   - Run: `python scripts/scrape-tennisexplorer-injured.py` (optionally `--max-pages N`).
   - Tested; produces 100+ injured and 160+ returning rows with 2 pages.

2. **Doc:** `docs/INJURY-DATA-SOURCES.md` — context and how to use the data.

3. **Lock:** `docs/FAIR-ODDS-POLICY-LOCK.md` — any model or policy change needs approval, backtest comparison, and a note in the lock. Injury overlay should be **optional** (like the tournament-segment overlay), off by default, and validated before promotion.

---

## What we need you to implement

### 1. Pipeline: run the scraper regularly

- Add `scrape-tennisexplorer-injured.py` to the **daily** or **weekly** job (e.g. `oncourt-daily.ps1` or `oncourt-weekly.ps1`) so `data/injured-players-tennisexplorer.csv` is kept up to date.
- One run per day is enough; no need to hit TennisExplorer more often.

### 2. Load and use the injured list in the app

- **Strict policy / API:** When building strict signals (and in the API when strict mode is on), optionally consider the injured list:
  - Load `data/injured-players-tennisexplorer.csv` (or a path from env, e.g. `INJURED_PLAYERS_CSV`).
  - For each fixture, check if **either** player appears in the list with `date` within the last **N days** (e.g. 7 or 14). Use `source == "injured"` only (recent retirement/walkover); “returning” can be used later for “just came back” if we want.
  - **Matching:** Our fixtures use OnCourt player **names** (e.g. from `oncourt_players`). The CSV has `player_name` (e.g. "Altmaier D.", "Ymer E.") and `player_slug` (e.g. "altmaier", "ymer"). You’ll need a **name-matching rule**: e.g. normalize both to "last name" + "first initial", or use slug vs a slug derived from OnCourt name (e.g. lowercase, strip accents, take first word or "lastname_firstinitial"). Same idea as tennis-data → OnCourt mapping elsewhere in the repo.
- **Behaviour (choose one or both, and make it configurable):**
  - **A) Flag only:** Add a field to the strict signal (e.g. `recent_injured: true/false`) and optionally show it in the UI or report. No change to selection.
  - **B) Filter:** Skip (exclude) the match from strict signals if either player is in the injured list in the last N days. This is a **policy overlay** like the tournament-segment overlay — should be **off by default** and gated by env (e.g. `STRICT_INJURY_OVERLAY_ENABLED=true` and `STRICT_INJURY_LOOKBACK_DAYS=14`).

### 3. Optionally weight in the model (fair-odds computation)

- In `scripts/oncourt-compute-fair-odds.py` (and, if we backtest it, in `scripts/backtest-fair-odds.py`), optionally **downweight** a player’s win probability if they appear in the injured list (e.g. recent retirement/walkover in the last 7–14 days).
- **Implementation idea:** Load the injured CSV once per run. For each fixture (player1_id, player2_id, names from OnCourt), check if either player is in the list within the lookback window. If yes, apply a **small negative delta** to that player’s win prob (e.g. −0.02 or a configurable constant), capped so we don’t flip the favourite. This is a **model-level** change, so per the lock doc:
  - Make it **optional** (e.g. env `FAIR_ODDS_INJURY_DOWNWEIGHT_ENABLED=true` and `FAIR_ODDS_INJURY_LOOKBACK_DAYS=14`, `FAIR_ODDS_INJURY_DELTA=0.02`).
  - **Do not** enable by default; we should validate with a backtest or walk-forward before turning it on.
  - Add a short note to `FAIR-ODDS-POLICY-LOCK.md` under a new “Injury overlay (optional)” section once implemented: what the env vars do, that it’s off by default, and that it was added for risk control / validation.

### 4. Name matching (player identity)

- OnCourt gives us player **names** (and we have IDs). TennisExplorer CSV has **player_name** ("Altmaier D.", "Zeppieri G.") and **player_slug** ("altmaier", "zeppieri").
- We need a **deterministic** way to say “this OnCourt player is the same as this CSV row”. Options:
  - Build a **slug** from OnCourt name: e.g. "Daniel Altmaier" → "altmaier" (last word, lowercased), or use the same normalisation we use elsewhere (e.g. in backtest name mapping). Then match CSV `player_slug` to that slug.
  - Or: normalize both to "Lastname F." and match; or use existing tennis-data → OnCourt name map if TennisExplorer names align with tennis-data format.
- Prefer reusing any existing **name normalisation** in the repo (e.g. in `backtest-fair-odds.py` or `strict-policy-report.py`) so behaviour is consistent. If none fits, add a small helper that maps OnCourt name → slug (or comparable key) and match to CSV.

---

## Constraints (from lock doc)

- **No change to locked baseline** without approval and backtest. So: injury overlay and model downweight are **add-ons**, off by default.
- **Optional and gated:** Use env vars so we can turn injury overlay on/off and tune lookback/delta without code changes.
- **Validation:** Before enabling in production, we should either (a) run a backtest with injury downweight on vs off and compare ROI, or (b) run the strict report with injury filter on and compare settled base vs injury-filtered over a few weeks. Document the result and only then consider enabling by default or recommending it.

---

## Files to touch (suggested)

- **Pipeline:** `scripts/oncourt-daily.ps1` (or weekly) — add step to run `scrape-tennisexplorer-injured.py`.
- **Strict policy / API:** `scripts/strict-policy-report.py`, `src/app/api/fair-odds/route.ts` — load injured CSV, match players, add flag or filter (with env gate).
- **Model (optional):** `scripts/oncourt-compute-fair-odds.py` — load injured CSV, apply optional downweight (env-gated).
- **Backtest (optional):** `scripts/backtest-fair-odds.py` — if we want to backtest injury downweight, add same logic and a CLI flag (e.g. `--injury-downweight` + path to injured CSV or use a historical injured list).
- **Lock doc:** `docs/FAIR-ODDS-POLICY-LOCK.md` — add “Injury overlay (optional)” section with env vars and “off by default, validate before enabling”.

---

## Summary

1. Add scraper to daily/weekly pipeline.  
2. Load injured CSV in strict report and API; match players (name/slug); add **flag** and/or **filter** (filter off by default, env-gated).  
3. Optionally in fair-odds model: downweight win prob for players in injured list (env-gated, off by default).  
4. Reuse or add name/slug matching; document in lock doc; validate before enabling in production.

If anything is unclear or you prefer a different design (e.g. filter only, no model weight), we can adjust. The CSV and scraper are ready to use.
