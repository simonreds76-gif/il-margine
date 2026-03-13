# Tennis injury / withdrawal data — options and usefulness

## Summary for il-margine

- **We don’t have** a dedicated injury feed today. OnCourt/Sackmann give match results (retirements/walkovers are in the outcome), but not a “current injured list” or pre-match withdrawal feed.
- **Useful for us:** A small “recent retirements/walkovers” list we can use to (a) flag or downweight players in strict policy (optional), or (b) feed the chatbot (“Player X retired at Indian Wells on …”).
- **Best fit:** **TennisExplorer “Injured players”** — one scrape-friendly page, no API cost, table with Start / Name / Tournament / Reason (retired | walkover). Easy to apply (see below).

---

## Option overview (from research)

| Source | Type | Useful? | Effort |
|--------|------|--------|--------|
| **TennisExplorer – Injured players** | Scrape (HTML table) | **Yes** — recent ret/WO, good for “recent injured” list | Low: one URL, pagination, parse table |
| **TennisExplorer – Returning players** | Same site, same structure | **Yes** — “just came back” list | Same script, second URL |
| **Sackmann CSVs** | Download (match results) | **Already have** — RET/WO in match outcome; use for history, not “current list” | N/A |
| **Goalserve / Sportradar / API-Tennis** | Paid API | Only if we need match-status (walkover/retired) in real time; we don’t need it for current pipeline | Skip for now |
| **Tennis Insight / RotoWire** | Web lists / subscription | Human check only unless we add another scrape | Optional later |

**Limitation (tennis-wide):** There is no standard “injury report” with diagnosis + return date. Most structured data is “retired / walkover” at match level. TennisExplorer gives exactly that in a simple table.

---

## TennisExplorer — how easy to apply

**URLs**

- Injured: `https://www.tennisexplorer.com/list-players/injured/`
- Pagination: `?page=2`, `?page=3`, …
- Returning: `https://www.tennisexplorer.com/list-players/return-from-injury/`

**Table (same on both)**

| Column   | Example        | Notes |
|----------|----------------|--------|
| Start    | 04.03.2026     | Parse to date (DD.MM.YYYY) |
| Name     | Altmaier D.    | Link to `/player/altmaier/` → slug = `altmaier` |
| Tournament | Indian Wells | Link text; can filter ATP/Challenger by name |
| Reason   | retired / walkover | Sometimes has score prefix; normalize to retired | walkover |

**Scrape steps**

1. GET each page (page=1,2,3,… until no table or empty).
2. Parse the main content table (skip “This week’s tournaments” and other tables).
3. Per row: extract date, player name, player slug from href, tournament, reason (strip to retired/walkover).
4. Write CSV: e.g. `data/injured-players-tennisexplorer.csv` (scraped_at, date, player_name, player_slug, tournament, reason).
5. Optionally filter to ATP (+ Challenger) by tournament name or “Futures”/“ITF”/“WTA” in tournament link.

**Using the data**

- **Strict policy (optional):** When building strict signals, if a player appears in the injured list in the last N days (e.g. 7 or 14), flag or skip (configurable). Not in lock doc yet; would be an optional overlay.
- **Chatbot:** “Did [player] retire recently?” → look up by name/slug in the CSV.
- **No change to model or locked policy** until we decide to add this as an explicit overlay (with a note in the lock doc).

**Script:** `scripts/scrape-tennisexplorer-injured.py` — runs the scrape and writes the CSV. Add `beautifulsoup4` if not installed: `pip install beautifulsoup4`.
