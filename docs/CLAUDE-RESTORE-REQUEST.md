# URGENT: Files Lost — Please Regenerate

## What happened

Cursor IDE crashed multiple times (OOM) and wiped all unsaved/uncommitted files. We lost two critical files you built:

1. **`src/app/api/fair-odds/route.ts`** — completely gone (directory doesn't exist)
2. **`src/app/fair-odds/page.tsx`** — reverted to a mock/demo stub with hardcoded fake data

The scraper (`scripts/pinnacle-scrape-odds.py`) also reverted to the old 234-line sync version, but we have the patches for that.

## What we need you to regenerate

### FILE 1: `src/app/api/fair-odds/route.ts`

This was the Next.js API route that:
- Queries Supabase `daily_fair_odds` table for today's date (UTC)
- Queries Supabase `oncourt_players` to build a player ID → name map
- Queries Supabase `bookmaker_odds_snapshot` filtered by `capture_date = today`, `bookmaker = 'Pinnacle'`
- Has a `normaliseSurname(name)` function that extracts the last word of a name, lowercased
- Has a `normaliseFirstWord(name)` function for first-name fallback
- Has a `matchPinnacle(fairOddsRows, pinRows, players)` function that:
  - Builds a lookup map from Pinnacle rows keyed by `surname1|surname2`
  - For each fair-odds row, looks up player names from the oncourt_players map
  - Tries to match by surname pair (both orderings)
  - Falls back to first-word matching
  - Returns a Map of matched rows with pinnacle odds merged in
- Returns JSON with the merged data (fair odds + pinnacle odds + value%)
- Uses `SUPABASE_SERVICE_ROLE_KEY` (not anon key) for reading bookmaker_odds_snapshot

### FILE 2: `src/app/fair-odds/page.tsx`

This was the live fair-odds page that:
- Is a `"use client"` React component
- Fetches from `/api/fair-odds` on mount (useEffect + useState)
- Displays a table with columns: Match, Surface, Fair P1, Fair P2, PIN P1, PIN P2, Value%, O/U Fair, O/U
- Shows loading state and error state
- Groups or lists matches
- Has breadcrumb nav (Home / Fair Odds)
- Dark theme matching the rest of the site (bg-[#0f1117], slate colors, emerald accents)
- Value% calculated as `(pinnacleOdds / fairOdds - 1) * 100`
- Green highlight for value >= 2%, red for < -5%
- Shows "—" dash when Pinnacle data is missing for a match
- Includes Footer component
- Surface shown as a small pill/badge

### Important details for route.ts

The Supabase queries used PostgREST REST API (fetch calls), not the JS client. Pattern was:

```typescript
const res = await fetch(
  `${supabaseUrl}/rest/v1/daily_fair_odds?select=*&match_date=eq.${today}`,
  {
    headers: {
      apikey: supabaseKey,
      Authorization: `Bearer ${supabaseKey}`,
    },
  }
);
```

Environment variables:
- `process.env.NEXT_PUBLIC_SUPABASE_URL`
- `process.env.SUPABASE_SERVICE_ROLE_KEY`

The `daily_fair_odds` table columns include:
- match_date, player1_id, player2_id, surface, league
- fair_odds1, fair_odds2 (match winner fair odds)
- ou_line, ou_over, ou_under (over/under fair odds from our model)
- tournament_name

The `bookmaker_odds_snapshot` table columns include:
- capture_date, bookmaker, league
- player1_name, player2_name
- odds1, odds2 (match winner odds from Pinnacle)
- ou_line, ou_over, ou_under (O/U from Pinnacle — often null, scraper WIP)
- pinnacle_margin

The `oncourt_players` table has: player_id, name (format: "First Last" e.g. "Daniil Medvedev")

### Patches to apply AFTER regeneration

Once you give me these two files, we have 7 patches ready to apply to the scraper and route.ts. The key ones for route.ts are:

**Patch 4a** — `normaliseSurname` should strip parenthetical text:
```typescript
const raw = (name ?? "").trim().replace(/\s*\([^)]*\)/g, "");
```

**Patch 4b** — Inside `matchPinnacle`, the loop must use the function parameter `pinRows`, not an outer-scope `pinnacleRows` variable.

**Patch 4c** — Add logging for unmatched Pinnacle rows (console.log with surname keys for debugging).

**Patch 4d** — Add a Levenshtein distance fuzzy fallback when exact surname matching fails (accept edit distance <= 2 on each surname).

## Please regenerate both files exactly as they were. We can apply the patches after.
