# Rewrite Pinnacle Scraper — `scripts/pinnacle-scrape-odds.py`

## Context

The scraper file reverted to an old 234-line sync version after Cursor OOM crashes. We need the full async version rewritten from scratch with all fixes baked in. The route.ts and page.tsx are restored and working — the fair-odds page loads data but shows "0 Pinnacle matches loaded" because this scraper is broken.

## Current broken scraper (what's on disk now)

The old version uses `sync_playwright`, `argparse` with only `--inspect`, `--csv`, `--supabase` flags, parses HTML with BeautifulSoup in a very naive way (regex for odds in container text), does one POST per row to Supabase without proper upsert, has no league detection, no O/U scraping, no name cleaning. It doesn't work — it finds matches but the parsing is unreliable and the upsert fails with 409s.

## What we need — full rewrite with these features

### CLI flags
- `--dry-run` — scrape only, don't write to DB
- `--save-html` — always save page HTML for debugging
- `--verbose` / `-v` — extra debug output
- No positional args needed

### Architecture
- Use `async_playwright` (async, not sync)
- Single file, no external dependencies beyond `playwright` and `requests`
- Load `.env.local` from project root for Supabase credentials
- Constants at top: `SUPABASE_URL`, `SUPABASE_KEY`, `DRY_RUN`, `SAVE_HTML`, `VERBOSE`, `HTML_DIR` (= `data/pinnacle-html/`)

### Scraping flow
1. Launch headless Chromium, navigate to `https://www.pinnacle.com/en/tennis/matchups/`
2. Wait for page load (try `networkidle`, fall back to `domcontentloaded` + wait)
3. Save HTML if `--save-html`
4. Find match rows using selectors: `[data-test-id="event-row"]`, `[class*="eventRow"]`, `[class*="matchup"]`, `div[class*="gameInfo"]`, fallback to `div[class*="row"]:has(button[class*="market"])`
5. For each row, extract via `page.evaluate()` JavaScript:
   - Player names (from text content, split on "(Sets)" delimiter that Pinnacle uses)
   - Match-winner odds (two decimal numbers)
   - League detection: walk up DOM ancestors looking for "ATP"/"MEN'S" or "WTA"/"WOMEN" in text, prefer shortest ancestor text to avoid false positives from page-wide content

### Name cleaning (`_clean_name` function)
```python
def _clean_name(n: str) -> str:
    n = re.sub(r"\s*\([^)]*\)", "", n)  # strip (8), (WC), (Sets), etc.
    n = re.sub(r"\s+(Sunday|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday),.*$", "", n, flags=re.I)
    n = re.sub(r"\s+(Sunday|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday)\s*$", "", n, flags=re.I)
    n = re.sub(r"\s+vs\s+at\s*$", "", n, flags=re.I)
    n = re.sub(r"\s+at\s*$", "", n, flags=re.I)
    return n.strip()
```

### Row parsing (`_parse_row_from_html`)
- Extract text from HTML (strip tags)
- Split on "(Sets)" to find player names
- Find decimal odds (1.01–20.0 range)
- Find O/U line (15.5–35.5 range) and associated over/under odds
- Filter: skip doubles (names containing "/" or "&"), skip names shorter than 2 chars or longer than 60
- Calculate margin: `1/odds1 + 1/odds2 - 1`

### O/U scraping — Phase 2
After scraping match-winner rows, attempt to click Pinnacle's "Total Games" market tab:
- Try selectors in order: `button:has-text("Total")`, `[data-test-id*="total"]`, `button:has-text("Total Games")`, `a:has-text("Total")`, `[class*="market"] button:has-text("Total")`, `div[role="tab"]:has-text("Total")`
- If found, click it, wait 2s, scrape O/U rows from the totals view
- Merge O/U data into match-winner results by normalised player name
- If no Total tab found, log warning and auto-save HTML for debugging

### Deduplication
- Dedupe results by `(player1_name, player2_name)` keeping the entry with lowest margin (sharpest odds)

### Upsert to Supabase
**Critical fix:** `on_conflict` must be a URL query parameter, NOT in the Prefer header (PostgREST ignores it in the header).

```python
conflict_cols = "capture_date,bookmaker,league,player1_name,player2_name"
url = f"{SUPABASE_URL}/rest/v1/bookmaker_odds_snapshot?on_conflict={conflict_cols}"
headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates",
}
```

- Batch all rows in a single POST (not one-at-a-time)
- Retry up to 3 times with exponential backoff
- If 409: print message about missing UNIQUE constraint with the SQL to fix it

### Required UNIQUE constraint (user should have this already, but remind):
```sql
ALTER TABLE bookmaker_odds_snapshot
ADD CONSTRAINT bookmaker_odds_snapshot_upsert_key
UNIQUE (capture_date, bookmaker, league, player1_name, player2_name);
```

### CSV backup
Always write a CSV backup to `data/pinnacle-odds-YYYY-MM-DD.csv` with columns: player1_name, player2_name, odds1, odds2, pinnacle_margin, ou_line, ou_over, ou_under, league

### Summary output
Print a clean summary at the end:
```
Summary: 10 matches (9 ATP, 1 WTA), 3 with O/U
```

### Error handling
- Clear error messages for missing credentials
- If 0 matches scraped: suggest checking saved HTML, no tennis today, or VPN needed
- If 0 O/U: warn that Total Games tab selectors may need updating, auto-save HTML

## Important notes
- The scraper previously worked and successfully scraped 10 matches and upserted them. The structure is proven — it just needs to be rebuilt as a single clean file.
- League detection via DOM ancestor walking is important — it's how we tag rows as ATP vs WTA
- The `_clean_name` parenthetical strip is critical — without it, names like "Medvedev (8)" get stored in the DB and break surname matching in the API route
- Entry point: `asyncio.run(main())`

## Please give me the complete file, ready to save as `scripts/pinnacle-scrape-odds.py`.
