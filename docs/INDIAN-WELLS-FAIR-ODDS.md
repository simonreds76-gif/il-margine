# Indian Wells & Fair Odds

## Why Indian Wells might not appear

### 1. Our fair odds (daily_fair_odds)

Fair odds are computed **only for fixtures that exist in OnCourt’s “today” export**:

- **Source:** `oncourt_today` in Supabase, loaded from `data/oncourt/today_atp.csv`.
- **That CSV** is produced by `scripts/oncourt-extract-rest.py` from the **OnCourt desktop app** (`OnCourt.mdb` → table `today_atp`).

So Indian Wells appears in our fair-odds table only if:

1. OnCourt has Indian Wells in its “today” matches when you run the extract, and  
2. You run the daily pipeline: OnCourt extract → Supabase sync (`--quick`) → fair-odds script.

If OnCourt’s “today” doesn’t list Indian Wells (e.g. date/timezone, or the event isn’t in the DB), we will have **no rows** for those matches in `daily_fair_odds`.

### 2. Pinnacle (bookmaker_odds_snapshot)

The Pinnacle scraper:

- Calls the guest API: `sports/33/leagues?all=true` (default is now **all=true** so we include leagues like Indian Wells even if not “active” in the UI).
- Includes any league whose name contains “ATP” or “Challenger” (or WTA if `--include-wta`).
- Indian Wells is typically one league (e.g. “ATP Indian Wells” or “Indian Wells”); if the name has no “ATP”, we still **include** it (default is include unless ITF/WTA).

So Indian Wells **should** be scraped if Pinnacle lists it. To verify:

```bash
python scripts/pinnacle-scrape-odds.py --list-leagues
```

This prints all tennis leagues (both `all=false` and `all=true`) and highlights any name containing “Indian” or “Wells”.

### 3. What you see on the Fair Odds page

- **Rows with fair odds:** From `daily_fair_odds` (OnCourt today → our model). Pinnacle odds are attached when we can match by player names.
- **“Pinnacle only” section:** Matches that are in **Pinnacle’s snapshot** but **not** in `daily_fair_odds` (e.g. Indian Wells when OnCourt today has no Indian Wells). These show Pinnacle odds and O/U only; no fair odds.

So even if we don’t have OnCourt data for Indian Wells, you should now see Indian Wells in the **“Pinnacle only”** block after running the daily odds (Pinnacle scrape + fair-odds script).

## Checklist

1. **See Indian Wells from Pinnacle**
   - Run: `python scripts/pinnacle-scrape-odds.py --list-leagues` and confirm an Indian Wells–related league is listed and included.
   - Run the full daily pipeline (e.g. `scripts/oncourt-daily.bat` or Pinnacle scrape then fair-odds). Open Fair Odds page → check **“Pinnacle only”** for Indian Wells matches.

2. **See Indian Wells with fair odds**
   - Ensure OnCourt’s “today” export includes Indian Wells (run OnCourt extract when the app’s date shows the correct day and the event is in the DB).
   - Run: OnCourt extract → `oncourt-load-supabase.py --quick` → `oncourt-compute-fair-odds.py` (or use the daily .bat). Then refresh the Fair Odds page.

3. **Scraper options**
   - `--list-leagues`: print leagues and exit (no scrape, no DB).
   - `--active-leagues-only`: use `all=false` (only “active” leagues). Default is `all=true` to include Indian Wells etc.
