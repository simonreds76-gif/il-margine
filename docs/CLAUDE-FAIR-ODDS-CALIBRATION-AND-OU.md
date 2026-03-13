# Fair Odds Calibration Issues + O/U Display

Two issues with the fair-odds page (http://localhost:3000/fair-odds):

---

## Issue 1: Fair odds wildly miscalibrated — Value% showing +242%, +492%

The `oncourt-compute-fair-odds.py` model is producing fair odds that are way off Pinnacle's market odds for many matches. Examples of Value% on the page: +242%, +492%, -65%. These are unrealistically large — a well-calibrated model should show Value% mostly in the ±2–10% range, with occasional outliers up to ±15–20%.

### What the pipeline produces today (2026-03-02):

- **Fixtures loaded**: 178 (ATP/Challenger only, after filtering)
- **Computed**: 95 fair odds rows
- **Skipped**: 83 (49 missing stats for both players, 16 missing P1 only, 18 missing P2 only)
- **Pinnacle scraped**: 57 matches (all with O/U), 22 of which are non-Challenger ATP

### Sample fair odds output (from the compute script log):
```
P1=18771 P2=44990 surface=Clay  P1_prob=0.5034  odds1=1.99  odds2=2.01
P1=30743 P2=61537 surface=Clay  P1_prob=0.3224  odds1=3.10  odds2=1.48
P1=32764 P2=96934 surface=Clay  P1_prob=0.7323  odds1=1.37  odds2=3.74
```

### Sample Pinnacle odds (same day):
```
Patrick Kypson vs Daniel Merida Aguilar    pin: 1.457 / 2.800  O/U=21.0
Benjamin Bonzi vs Jack Pinnington Jones    pin: 1.980 / 1.855  O/U=22.5
Luca Nardi vs Trevor Svajda               pin: 1.397 / 3.050  O/U=21.0
Nicolas Jarry vs Francesco Maestrelli      pin: 2.090 / 1.775  O/U=23.0
Leandro Riedi vs Rinky Hijikata           pin: 1.847 / 1.990  O/U=22.5
```

### How the model works (from `oncourt-compute-fair-odds.py`):
1. Reads fixtures from `oncourt_today` → filters to ATP/Challenger
2. Loads `player_surface_stats` (hold%, return%, match_count for 12m and 36m windows)
3. Loads `player_elo` (surface + Overall, blended 50/50)
4. Computes point probabilities p_A, p_B via Barnett-Clarke ratio method using league avg SPW
5. Hybrid blend: 40% Elo + 60% serve/return (adaptive by sample size — leans more on Elo when fewer matches)
6. Shrinkage to surface average when match_count is low (shrinkage_N = 15)
7. Adjustments: lefties, big servers, venue, altitude, age, form/fatigue
8. `tennis_prob.py`: K-M recursion for match win probability + expected total games
9. Upserts to `daily_fair_odds`

### What I think is wrong:
- **Challenger players with thin stats**: Many fixtures have match_count < 5. The shrinkage (N=15) pulls heavily toward surface average, making most players look similar → odds near 2.0 (coin flip). Meanwhile Pinnacle has strong opinions (1.30 vs 3.50).
- **Elo defaulting to 1500**: When a Challenger player has no Elo in the DB, `DEFAULT_ELO = 1500` is used. Two players both at 1500 → Elo says 50/50, even if one is a heavy favourite.
- **Name matching might pair wrong matches**: If the surname normalisation matches "Smith vs Jones" to the wrong Pinnacle row, the Value% would be extreme. The `normaliseSurname` function doesn't strip parenthetical text like `(8)` or `(WC)` — Patch 4a was supposed to add `.replace(/\s*\([^)]*\)/g, "")` but it's missing from the current `route.ts`.

### What I need you to check/fix:
1. **Apply Patch 4a to `normaliseSurname` in `src/app/api/fair-odds/route.ts`** — add `.replace(/\s*\([^)]*\)/g, "")` to strip parenthetical text before extracting surname.
2. **Review the hybrid model calibration** — is 40/60 Elo/serve-return the right split? Should we trust Pinnacle more as a prior when our data is thin?
3. **Do NOT skip Challenger matches.** Instead, compute fair odds with broader defaults so more matches get covered (see Issue 3 below).
4. **Consider a "confidence" column** — if match_count < N for either player, flag as low-confidence so the page can grey them out or show a warning instead of misleading Value%.

---

## Issue 3: Too many fixtures skipped — need Elo-only fallback for missing stats

Currently, 83 out of 178 ATP/Challenger fixtures are **skipped entirely** because one or both players lack `player_surface_stats` data. This means Indian Wells qualifying matches (which start today), most Challenger matches, and any match involving a less-established player simply don't appear on the fair-odds page.

### Current logic (lines 662-669 of `oncourt-compute-fair-odds.py`):
```python
if s1 is None or s2 is None:
    if s1 is None and s2 is None:
        skip_missing_both += 1
    elif s1 is None:
        skip_missing_p1 += 1
    else:
        skip_missing_p2 += 1
    continue   # <-- entire fixture skipped
```

### What I want instead:
When one or both players are missing serve/return stats, **don't skip**. Instead:
1. **Use surface averages as defaults** for the missing player's hold%/return% (the `SURFACE_AVG_HOLD` / `SURFACE_AVG_RETURN` constants are already defined).
2. **Lean heavily on Elo** when stats are missing — push `elo_weight` up to 0.7–0.8 instead of the normal 0.4.
3. **If Elo is also missing** (both players at default 1500), use ATP ranking if available to derive a probability (the rank-based probability code already exists further down in the script).
4. **Flag these as low-confidence** — add a column like `confidence` (or `data_quality`) to `daily_fair_odds`. Values: `"high"` (both players have 10+ matches on surface), `"medium"` (5–10 matches or one player missing), `"low"` (both missing stats, using Elo/rank only). The page can then show a visual indicator.

This way:
- Indian Wells qualies appear on the page (even if less precise)
- Challenger matches get odds (Elo-heavy, flagged as lower confidence)
- The user can see at a glance which odds to trust more

---

## Issue 2: O/U display — want actual O/U lines, not just E[G]

Currently the page shows:
- **E[G]** column: expected total games from the model (e.g. 24.8, 21.2)
- **O/U Fair** columns: `ou_line_1/2/3` from `daily_fair_odds` — these are mostly NULL because the compute script doesn't populate them

The user wants:
- **Fair O/U line**: computed from E[G]. If E[G] = 22.3, the fair line is 22.5, and fair over/under odds can be derived from the model's game distribution.
- **Pinnacle O/U**: the scraper already gets this (line + over/under prices). It's stored in `bookmaker_odds_snapshot` as `ou_line`, `ou_over`, `ou_under`. The route.ts already reads these and passes them as `pinnacle_ou_line`, `pinnacle_ou_over`, `pinnacle_ou_under`.
- **O/U Value%**: compare our fair O/U line against Pinnacle's O/U line and prices.

### What the scraper provides (from `bookmaker_odds_snapshot`):
```
ou_line=21.0  ou_over=1.901  ou_under=1.917
ou_line=22.5  ou_over=1.962  ou_under=1.862
ou_line=23.0  ou_over=1.952  ou_under=1.862
```

### What needs to happen:
1. **In `oncourt-compute-fair-odds.py`**: After computing `expected_total_games`, derive O/U fair odds. E.g. for E[G]=22.3: line = 22.5, P(over) = P(total > 22.5) from the model, fair_over = 1/P(over), fair_under = 1/P(under). Write these to `ou_line_1, ou_over_1, ou_under_1`.
2. **In the page**: Show both fair O/U (from model) and Pinnacle O/U side by side with value%.

### `tennis_prob.py` already has the building blocks:
- `expected_total_games_best_of_3(p_a, p_b)` returns E[G]
- But we need `P(total > X)` for a given line X. This requires computing the full game distribution, not just the expected value. A new function like `prob_over_games(p_a, p_b, line)` would do it — sum the probability of all outcomes where total games > line.

---

## Summary of all changes needed:

### 1. `oncourt-compute-fair-odds.py` — the big one
- Remove the `continue` when stats are missing → use surface avg defaults + Elo-heavy weighting
- Add `confidence` field ("high"/"medium"/"low") based on data availability
- Populate `ou_line_1, ou_over_1, ou_under_1` from the model (not just `expected_total_games`)

### 2. `src/lib/tennis_prob.py`
- Add `prob_over_games(p_a, p_b, line)` function: P(total games > line) for best-of-3
- This requires computing the full game-count distribution, not just E[G]

### 3. `src/app/api/fair-odds/route.ts`
- Fix `normaliseSurname`: add `.replace(/\s*\([^)]*\)/g, "")` (Patch 4a)
- Pass through `confidence` field from daily_fair_odds to the frontend
- Pass through `ou_line_1/ou_over_1/ou_under_1` (already partially done)

### 4. `src/app/fair-odds/page.tsx`
- Show confidence indicator (colour/icon) per row
- Show fair O/U line + fair over/under odds alongside Pinnacle O/U
- Show O/U Value% (compare fair vs Pinnacle O/U)
- Grey out or dim low-confidence rows

### 5. Database migration (run in Supabase SQL Editor):
```sql
ALTER TABLE daily_fair_odds ADD COLUMN IF NOT EXISTS confidence TEXT DEFAULT 'high';
```

## Files you need to read:
- `scripts/oncourt-compute-fair-odds.py` (936 lines) — fair odds model, main changes here
- `src/lib/tennis_prob.py` (120 lines) — K-M recursion, add prob_over_games
- `src/app/api/fair-odds/route.ts` (404 lines) — API route, Patch 4a + confidence pass-through
- `src/app/fair-odds/page.tsx` — display page, O/U and confidence UI
- `scripts/pinnacle-scrape-odds.py` (541 lines) — API scraper (working fine, no changes needed)

## Database schema (relevant columns):
**`daily_fair_odds`**: id, tour_id, player1_id, player2_id, surface, round_id, draw, p1_win_prob, p2_win_prob, p_serve_return, p_elo, odds1, odds2, computed_at, expected_total_games, ou_line_1, ou_over_1, ou_under_1, ou_line_2, ou_over_2, ou_under_2, ou_line_3, ou_over_3, ou_under_3, **confidence** (new: TEXT, "high"/"medium"/"low")

**`bookmaker_odds_snapshot`**: capture_date, bookmaker, league, player1_name, player2_name, odds1, odds2, pinnacle_margin, ou_line, ou_over, ou_under

**`player_surface_stats`**: player_id, surface, hold_pct, return_pct, match_count, service_pts, return_pts

**`player_elo`**: player_id, surface, elo_rating

## Important constraints:
- **Do not modify `pinnacle-scrape-odds.py`** — it's working perfectly (57 matches with O/U via API).
- **Do not modify the Supabase schema** beyond the one ALTER TABLE above — the existing column names must stay.
- **Send complete replacement code** for any file you change (not diffs). This avoids merge errors on my end.
- **Keep the existing model adjustments** (lefties, big servers, venue, altitude, age, form/fatigue) — only change the missing-stats fallback logic and add the O/U computation.
