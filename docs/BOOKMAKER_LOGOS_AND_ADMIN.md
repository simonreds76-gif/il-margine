# Bookmaker thumbnails & admin dropdown

## Thumbnail sizes

Logos are rendered by `BookmakerLogo` at three sizes:

| Context | Size | CSS | Use |
|--------|------|-----|-----|
| **Tips pages** (player-props, tennis-tips, etc. – next to each bet) | `sm` | 24×24px | Bet cards, recent bets |
| **Bookmakers page** (recommended cards) | `md` | 32×32px | Card header next to bookmaker name |
| **Larger** (e.g. offer cards) | `lg` | 40×40px | When you need a bigger logo |

**Asset recommendation:** one square image per bookmaker is enough. Use **64×64px or 128×128px** (PNG with transparency or SVG). The app scales them down; 2× is enough for retina.

- **Tips pages:** 24px display → 48px or 64px source is fine.
- **Bookmakers page:** 32px display → 64px or 128px source is fine.

So a single **64×64 or 128×128 PNG (or SVG)** in `public/bookmakers/{short_name}.png` (or `.svg`) covers all uses.

---

## Logo files: what exists vs what’s missing

**In `public/bookmakers/` you already have:**

- 888sport, bet365, betfair, betfred, betmgm, betvictor, betway, coral, ladbrokes, paddypower, pinnacle, skybet, unibet, williamhill  
  (as `.png` and/or `.svg`)

**Recommended on Bookmakers page (and for tips):** Midnite, BetVictor, Unibet, Coral, Ladbrokes, BetMGM.

| Bookmaker | File expected | Status |
|-----------|----------------|--------|
| BetMGM | `betmgm.png` or `betmgm.svg` | ✅ betmgm.svg |
| BetVictor | `betvictor.png` or `betvictor.svg` | ✅ both |
| Coral | `coral.png` or `coral.svg` | ✅ coral.svg |
| Ladbrokes | `ladbrokes.png` or `ladbrokes.svg` | ✅ ladbrokes.svg |
| Midnite | `midnite.png` or `midnite.svg` | ❌ **MISSING** – add `midnite.png` or `midnite.svg` |
| Unibet | `unibet.png` or `unibet.svg` | ✅ both |

**To add:** only **Midnite**. Add `public/bookmakers/midnite.png` (or `midnite.svg`), 64×64 or 128×128, square.  
`BookmakerLogo` already maps `"Midnite"` / `"midnite"` to that filename.

---

## Admin dropdown: “Pick odds from” bookmakers

The admin “Bookmaker” dropdown is filled from the **Supabase `bookmakers` table**. Only rows in that table (with `active = true`) appear when inserting a bet.

To have **Midnite, BetVictor, Coral, Ladbrokes** (and any others) in the dropdown, add them in the database.

### Add bookmakers in Supabase (SQL)

Run in **Supabase → SQL Editor** (adjust `affiliate_link` if you have one):

```sql
-- Add Midnite, BetVictor, Coral, Ladbrokes for admin dropdown (and bookmakers page)
-- Use short_name that matches BookmakerLogo: Midnite, BetVictor, Coral, Ladbrokes
-- Skip if they already exist (check table first).

INSERT INTO bookmakers (name, short_name, affiliate_link, active)
VALUES
  ('Midnite', 'Midnite', NULL, true),
  ('BetVictor', 'BetVictor', NULL, true),
  ('Coral', 'Coral', NULL, true),
  ('Ladbrokes', 'Ladbrokes', NULL, true)
ON CONFLICT DO NOTHING;
```

If your table has no unique constraint on name/short_name, use:

```sql
INSERT INTO bookmakers (name, short_name, affiliate_link, active)
SELECT 'Midnite', 'Midnite', NULL, true WHERE NOT EXISTS (SELECT 1 FROM bookmakers WHERE short_name = 'Midnite');
INSERT INTO bookmakers (name, short_name, affiliate_link, active)
SELECT 'BetVictor', 'BetVictor', NULL, true WHERE NOT EXISTS (SELECT 1 FROM bookmakers WHERE short_name = 'BetVictor');
INSERT INTO bookmakers (name, short_name, affiliate_link, active)
SELECT 'Coral', 'Coral', NULL, true WHERE NOT EXISTS (SELECT 1 FROM bookmakers WHERE short_name = 'Coral');
INSERT INTO bookmakers (name, short_name, affiliate_link, active)
SELECT 'Ladbrokes', 'Ladbrokes', NULL, true WHERE NOT EXISTS (SELECT 1 FROM bookmakers WHERE short_name = 'Ladbrokes');
```

After that, they will:

- Appear in the **admin** “Bookmaker” dropdown when adding/editing bets.
- Show on **tips pages** (player-props, tennis-tips, etc.) with the correct logo if the bet’s `bookmaker_id` points to them.
- Show on the **Bookmakers page** with logo and “Claim offer” when the page looks up by `short_name` (Midnite, BetVictor, Coral, Ladbrokes are already in the recommended list; the page matches `getBookmakerFromDb(rec.short_name)` so the logo and affiliate link come from the same `bookmakers` table).

---

## Checklist

1. **Logos**
   - Add **Midnite**: `public/bookmakers/midnite.png` (or `.svg`), 64×64 or 128×128.
   - Others (BetVictor, Unibet, Coral, Ladbrokes, BetMGM) already have assets.

2. **Admin dropdown**
   - Run the SQL above in Supabase to add Midnite, BetVictor, Coral, Ladbrokes to `bookmakers` (if not already there).

3. **Sizes summary**
   - One asset per bookmaker: **64×64 or 128×128** (or SVG). Same file is used on tips pages (small) and bookmakers page (medium).

---

## William Hill affiliate tracking (Supabase)

**Click tracking** is handled in code: `/api/go/william-hill` redirects to the William Hill C.ashx URL. The **bookmakers page** uses that route for “Claim offer” and logo links.

So that **William Hill** is clickable when shown from the database (e.g. on the homepage in bet cards), set the link in Supabase:

| Where | What to do |
|-------|------------|
| **Table** | `bookmakers` |
| **Row** | The row where `name` = `'William Hill'` or `short_name` = `'William Hill'` (or `'WH'` if you use that). |
| **Column** | `affiliate_link` |
| **Value** | `/api/go/william-hill` |

**Supabase → Table Editor → `bookmakers`:** find the William Hill row and set `affiliate_link` to `/api/go/william-hill` (relative URL so it works on any domain).

Or run in **Supabase → SQL Editor**:

```sql
UPDATE bookmakers
SET affiliate_link = '/api/go/william-hill'
WHERE short_name IN ('William Hill', 'WH', 'williamhill') OR name ILIKE '%william hill%';
```

Nothing else needs to go in Supabase for William Hill; the C.ashx and S.ashx URLs are fixed in the codebase.
