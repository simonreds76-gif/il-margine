# Fix O/U Scraper: Game Totals, Not Set Totals

## Problem

The scraper runs and finds matches correctly (6 singles, upsert works), but O/U is always 0. We inspected the saved HTML and found:

The `data-test-id="over-under"` sections on Pinnacle's matchups page contain **SET totals** (Over/Under 2.5 sets), NOT game totals. Example from the HTML:

```html
<div data-test-id="over-under" class="buttons-j19Jlcwsi9">
  <div class="buttonWrapper-ofFCIiahBj">
    <button title="2.5" class="market-btn ...">
      <span class="label-GT4CkXEOFj">2.5</span>
      <span class="price-r5BU0ynJha">2.760</span>
    </button>
  </div>
  ...
</div>
```

The `title="2.5"` and `label` show 2.5 (sets), not 21.5/22.5 (games). Our parser correctly skips these because it looks for lines in the 15.5–35.5 range.

However, game total lines (21.5, 30.5 etc.) DO exist in the full HTML (11 occurrences found). They appear to be in expandable match detail views or behind a "Total Games" market tab that the scraper can't find with current selectors.

## What we need

The scraper needs to find and extract **total games** O/U odds (lines like 21.5, 22.5). Options:

1. **Click into individual match pages** — each match link goes to e.g. `/en/tennis/wta-indian-wells-qualifiers/garland-vs-townsend/1625211944/` which likely shows all markets including Total Games
2. **Find the correct tab/selector** on the matchups page that switches from Set totals to Game totals
3. **Navigate to a different URL** that shows game totals directly

## Current scraper structure (for reference)

The scraper (`scripts/pinnacle-scrape-odds.py`, 752 lines) already has:
- `_parse_ou_from_html()` — structured parser looking for `data-test-id="over-under"` with lines 15.5–35.5
- Phase 2: tries clicking "Total Games" tab with multiple selectors (none found)
- `_merge_ou_into_results()` — merges O/U by normalised player name
- Flat-text fallback parser

## Key HTML details

- Match rows use `data-test-id="moneyline"` for match-winner, `data-test-id="over-under"` for sets O/U
- Match links: `<a href="/en/tennis/wta-indian-wells-qualifiers/garland-vs-townsend/1625211944/">`
- Class names: `row-u9F3b9WCM3`, `buttons-j19Jlcwsi9`, `price-r5BU0ynJha`, `label-GT4CkXEOFj`
- The "Over"/"Under" header labels are in `<span class="label-TsvXwccH9E">`

## Saved HTML

We have the full page HTML saved at `data/pinnacle-html/pinnacle-20260302-005934.html` (can paste sections if needed).

## ALSO: Scrape by league, not the generic matchups page

Currently the scraper hits `https://www.pinnacle.com/en/tennis/matchups/` which dumps all tennis together. At certain times we only get WTA qualifiers, missing ATP/Challengers entirely.

Better approach: start from `https://www.pinnacle.com/en/tennis/leagues/` which lists all tennis leagues. The scraper should:

1. Navigate to the leagues page
2. Find the ATP and Challenger league links (skip WTA for now)
3. Click into each one (e.g. `https://www.pinnacle.com/en/tennis/atp/matchups/`, `https://www.pinnacle.com/en/tennis/atp-challengers/matchups/` or whatever the URLs are)
4. Scrape odds from each league page separately
5. Tag each match with the correct league (ATP or Challenger) based on which page it came from — no more DOM ancestor walking needed

This way we never miss ATP/Challenger matches and league detection is 100% accurate.

## Please provide the code changes needed for both:
1. League-based navigation (ATP + Challengers, skip WTA)
2. Game totals O/U extraction (not set totals)
