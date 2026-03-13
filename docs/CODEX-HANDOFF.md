# Codex handoff: full project brief + H2H & advanced stats

**Use this as the single document for Codex.** It explains the repo, the project, the pipeline, and exactly what to build. All code must be **output as pasteable blocks in chat** — do not write or edit files in the repo.

---

# Part 0 — Repo and what Codex can see

## Branch and visibility

- **Branch to use:** `golden-with-speed-insights`
- **Everything below is committed and pushed** on that branch. Codex can see:
  - All pipeline scripts (fair-odds, OnCourt extract/load, Pinnacle scrape, daily runner)
  - Fair-odds app and API (`src/app/fair-odds/`, `src/app/api/fair-odds/`)
  - Docs and SQL schemas under `docs/`
  - This handoff and the debrief (`docs/DEBRIEF-H2H-AND-ADVANCED-STATS.md`)

## Key file map (where everything lives)

| Purpose | Path |
|--------|------|
| **Fair-odds computation** (main script to extend) | `scripts/oncourt-compute-fair-odds.py` |
| **Daily odds pipeline** (runs fair-odds + Pinnacle) | `scripts/run-daily-odds.py` |
| **Pinnacle odds scraper** | `scripts/pinnacle-scrape-odds.py` |
| **OnCourt: extract CSV from Access** | `scripts/oncourt-extract-all.py`, `scripts/oncourt-extract-rest.py` |
| **OnCourt: load CSV → Supabase** | `scripts/oncourt-load-supabase.py` |
| **OnCourt: player surface stats** (reference only) | `scripts/oncourt-compute-player-stats.py` |
| **OnCourt: league/tournament/recent** | `scripts/oncourt-compute-league-avg.py`, `scripts/oncourt-compute-tournament-avg-games.py`, `scripts/oncourt-compute-recent-activity.py` |
| **Fair-odds page** | `src/app/fair-odds/page.tsx`, `src/app/fair-odds/layout.tsx` |
| **Fair-odds API** | `src/app/api/fair-odds/route.ts` |
| **Supabase schemas (OnCourt, daily_fair_odds, etc.)** | `docs/supabase-oncourt-schema.sql`, `docs/supabase-ou-columns.sql`, `docs/supabase-daily-fair-odds-confidence.sql`, etc. |
| **Python deps** | `scripts/requirements.txt` |
| **OnCourt run instructions** | `scripts/README-oncourt.md` |
| **OnCourt rankings handoff** (extract rank + points, wire to fair-odds) | [docs/CODEX-ONCOURT-RANKINGS-HANDOFF.md](CODEX-ONCOURT-RANKINGS-HANDOFF.md) |

## Environment

- Scripts that talk to Supabase use **`.env.local`** in the project root: `NEXT_PUBLIC_SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`.
- OnCourt extract needs **32-bit Python** and `ONCOURT_PWD` (see `scripts/README-oncourt.md`).

---

# Part 1 — What this project is and what we do

## The product: Il Margine

Il Margine is a **tennis betting dashboard**. For each day’s ATP/Challenger matches we show:

- **Our “fair” odds** (match winner and over/under total games).
- **Pinnacle’s odds** (scraped from their public API).
- **Value %** = how much better (or worse) Pinnacle’s price is vs our fair price.

So we **predict** match outcomes and totals; then we compare our numbers to the bookmaker. The goal of the work described here is to **improve our match-winner (ML) predictions** by using two things we don’t use yet: **head-to-head (H2H)** and **advanced serve/return stats**.

## How we get to “fair odds” today (simplified)

1. **Fixtures**  
   We get “today’s matches” from a Supabase view **oncourt_today** (player1_id, player2_id, tour_id, surface, etc.). Those IDs are **OnCourt** player IDs (integers).

2. **Player stats**  
   For each player we have **player_surface_stats** in Supabase: hold_pct, return_pct, match_count, etc. by surface. These are computed from **OnCourt** match data (scripts read `data/oncourt/` CSVs and push to Supabase). In the DB, hold_pct/return_pct are **point-level** (serve point win % and return point win %), not game-level hold %.

3. **Elo**  
   We have **player_elo** in Supabase (by surface and overall). Again keyed by **OnCourt** player_id.

4. **Fair-odds script**  
   `scripts/oncourt-compute-fair-odds.py`:
   - Reads fixtures from Supabase (oncourt_today).
   - For each match, loads both players’ stats and Elo from Supabase.
   - Combines serve/return stats with Elo (and rank, venue, altitude, form, etc.) into a **match win probability** for player 1 (and thus player 2).
   - Converts that to fair decimal odds and expected total games (E[G]) and over/under lines.
   - Writes one row per match to **daily_fair_odds** in Supabase.

5. **Website**  
   The fair-odds page reads **daily_fair_odds** (and Pinnacle snapshot) from an API and shows the table.

**Important:** Everywhere in this pipeline we use **OnCourt player IDs** (integers). Fixtures, stats, Elo, and daily_fair_odds all refer to players by that ID.

---

# Part 2 — What we need to add (both are required)

We want **two** upgrades to the match-winner (ML) side. Neither is optional.

## Upgrade 1: Head-to-head (H2H)

- **Idea:** If player A has beaten player B many times in the past (e.g. 6–2 on clay), we should nudge our probability a bit toward A when we predict A vs B on clay.
- **What we need:**
  - A **Supabase table** that stores, for each pair of players (and optionally surface): how many times each won (e.g. wins_a, wins_b, match_count, surface).
  - A **script** that builds this table from historical match results. Those results live in **Sackmann** and **TML** CSV files (winner_id, loser_id, surface, date), not in OnCourt. So we must **map** Sackmann/TML player IDs to **OnCourt** player IDs (e.g. by matching player names), then aggregate and upsert.
  - **Integration in fair-odds:** When we compute p1_win for a fixture (p1, p2, surface), we look up H2H for (p1, p2, surface). If they have enough meetings (e.g. at least 5), we apply a small adjustment to p1_win (e.g. based on p1’s win rate in the H2H), capped so we don’t over-trust a small sample.

## Upgrade 2: Advanced serve/return stats

- **Idea:** Right now we only use “hold_pct” and “return_pct” (point-level SPW/RPW) from OnCourt. Sackmann and TML match CSVs have **more** columns we don’t use: first serve %, first serve win %, second serve win %, aces, double faults, break points saved, break points faced, etc. We want to **aggregate** these per player per surface and **use** them in the model (e.g. to refine serve/return strength or add a “clutch” factor).
- **What we need:**
  - A **Supabase table** for “advanced” stats per (player_id, surface): e.g. 1st_serve_pct, 1st_serve_win_pct, 2nd_serve_win_pct, ace_rate, df_rate, bp_save_pct, bp_convert_pct (or similar names). Again **player_id must be OnCourt** so fair-odds can join.
  - A **script** that reads Sackmann (and TML) match CSVs, aggregates these stats per player per surface, maps player IDs to OnCourt, and upserts to this table.
  - **Integration in fair-odds:** Use these stats as extra inputs: e.g. adjust serve/return strength or add a small adjustment for break-point or serve-dominance matchups. Design can follow the previous plan (e.g. first/second serve split, BP clutch); the debrief from the other Claude can guide the exact formula.

So: **both H2H and advanced stats are required.** Implement H2H first (table + script + fair-odds integration), then advanced stats (table + script + fair-odds integration).

---

# Part 3 — Data we have (from scratch)

## Three data sources

| Name      | What it is | Where on disk | Player IDs | Used in live pipeline? |
|-----------|------------|----------------|------------|------------------------|
| **OnCourt** | Match/player data from OnCourt | `data/oncourt/` (e.g. games_atp.csv, stat_atp.csv, tours_atp.csv, courts.csv). Players also in Supabase **oncourt_players**. | **OnCourt IDs** (integers) | **Yes.** Fixtures, player_surface_stats, Elo, fair-odds all use these. |
| **Sackmann** | Jeff Sackmann ATP match CSVs | `data/sackmann/` — e.g. atp_matches_2023.csv, atp_matches_2024.csv, atp_matches_qual_chall_2023.csv, atp_matches_qual_chall_2024.csv, atp_players.csv | **Sackmann IDs** (numeric, e.g. 105777) | **No.** We have the files but don’t use them in the live pipeline yet. |
| **TML**   | Tennis My Life — same CSV layout as Sackmann | `tml-data/` — e.g. 2025.csv, 2026.csv, 2025_challenger.csv, 2026_challenger.csv, and many years 1968–2026 | **TML IDs** (alphanumeric, e.g. CD85) | **No.** Same as Sackmann; we want to use for 2025+ so H2H and advanced stats are up to date. |

- **Sackmann** covers through 2024. **TML** covers 2025 (and 2026). So for H2H and advanced stats we should use **Sackmann for older years** and **TML for 2025+** (and optionally 2026).
- **Critical:** Our app and **oncourt-compute-fair-odds.py** only know **OnCourt** player IDs. So any new table (H2H or advanced stats) that fair-odds reads **must** use OnCourt player_id. The scripts that build those tables must either:
  - Map Sackmann/TML IDs → OnCourt IDs (e.g. by matching names to **oncourt_players** in Supabase) and then store only OnCourt IDs, or
  - Store a mapping table and resolve at read time (more complex). Prefer mapping once and storing OnCourt IDs.

## What’s in the Sackmann/TML match CSVs

Typical columns (names may vary slightly between Sackmann and TML):

- **Match:** tourney_id, surface, tourney_date, round, best_of, score, minutes.
- **Winner:** winner_id, winner_name, winner_hand, winner_ht, winner_age, winner_rank, …
- **Loser:** loser_id, loser_name, loser_hand, …
- **Stats (winner side):** w_ace, w_df, w_svpt, w_1stIn, w_1stWon, w_2ndWon, w_SvGms, w_bpSaved, w_bpFaced.
- **Stats (loser side):** l_ace, l_df, l_svpt, l_1stIn, l_1stWon, l_2ndWon, l_SvGms, l_bpSaved, l_bpFaced.

From these we can compute:

- **H2H:** For each (winner_id, loser_id, surface) we count wins per player; aggregate across all match files (Sackmann + TML), then map to OnCourt and store (player_a_id, player_b_id, surface, wins_a, wins_b, match_count).
- **Advanced stats per player per surface:** e.g. 1st serve % = w_1stIn / w_svpt, 1st serve win % = w_1stWon / w_1stIn, 2nd serve win % from w_2ndWon and second-serve points, ace rate, df rate, BP save % = w_bpSaved / w_bpFaced, BP conversion (from return side), etc. Aggregate over all matches for that player on that surface, then map to OnCourt and store.

There is **no** existing “player_id_map” (Sackmann or TML → OnCourt) in the repo. The implementation needs to **build** it, e.g. by loading **oncourt_players** (id, name) from Supabase and matching names to winner_name/loser_name (and Sackmann/TML player lists if available) with normalized/canonical names to handle “F. Cerundolo” vs “Francisco Cerundolo” etc.

---

# Part 4 — How we do it (step-by-step for Codex)

## Step 1: Supabase tables (you provide SQL, user runs it in Supabase)

Create two new tables.

**Table 1: player_h2h**

- Purpose: store head-to-head record for each pair of players (and surface) in **OnCourt** IDs.
- Suggested columns:  
  `player_a_id` (int), `player_b_id` (int), `surface` (text), `wins_a` (int), `wins_b` (int), `match_count` (int), `last_match_date` (date or text).  
  Constraint: always store so that `player_a_id < player_b_id` (canonical ordering) so lookup is unique.
- Primary key: e.g. (player_a_id, player_b_id, surface).

**Table 2: player_advanced_stats** (or similar name)

- Purpose: store advanced serve/return stats per player per surface in **OnCourt** IDs.
- Suggested columns:  
  `player_id` (int, OnCourt), `surface` (text), `first_serve_pct`, `first_serve_win_pct`, `second_serve_win_pct`, `ace_rate`, `df_rate`, `bp_save_pct`, `bp_convert_pct`, `match_count`, `service_points`, etc. (only include what you can compute from the CSVs).
- Primary key: (player_id, surface).

Put the SQL in a file under `docs/`, e.g. `docs/supabase-player-h2h.sql` and `docs/supabase-player-advanced-stats.sql`, and **output the SQL as pasteable blocks** so the user can run them in the Supabase SQL editor.

## Step 2: Player ID mapping (Sackmann/TML → OnCourt)

- Load from Supabase **oncourt_players**: id, name (and any other columns that help).
- Load from match CSVs (and if available Sackmann atp_players.csv / TML equivalent) all distinct winner_id + winner_name, loser_id + loser_name. For TML the ID might be alphanumeric (e.g. CD85).
- Build a mapping: (source_id, source = "sackmann" | "tml") → oncourt_player_id.  
  Do this by **normalizing names** (lowercase, strip, maybe remove punctuation, handle “F. X” vs “First X”) and matching to oncourt_players.name. If one Sackmann/TML name matches exactly one OnCourt name, map that ID to that OnCourt id. Document that some players may not match (e.g. Challenger-only in one system); those rows are skipped for H2H/advanced stats that go into Supabase.
- The H2H and advanced-stats scripts will use this map to convert Sackmann/TML IDs to OnCourt IDs before aggregating and upserting.

## Step 3: Script to compute and upsert H2H

- **Input:** Sackmann match CSVs in `data/sackmann/` (e.g. atp_matches_2023.csv, atp_matches_2024.csv, qual_chall), and TML CSVs in `tml-data/` (e.g. 2025.csv, 2025_challenger.csv, 2026.csv if desired). Only use rows that have winner_id, loser_id, surface (and optionally tourney_date).
- **Steps:**
  1. Build the player ID map (Sackmann/TML → OnCourt) as in Step 2 (or call a small shared helper).
  2. For each match row, get winner_id and loser_id (and surface). Map both to OnCourt IDs. If either mapping is missing, skip the row.
  3. Canonicalize the pair: (a, b) with a < b (OnCourt IDs). Surface stays as-is (e.g. Hard, Clay, Grass).
  4. Aggregate: for each (player_a_id, player_b_id, surface), count how many times the winner was a and how many times the winner was b (remember: when the match had winner=W and loser=L, after mapping W might be a and L b, or the other way around).
  5. Upsert to **player_h2h** (e.g. use Supabase REST API or a Postgres client; same pattern as other scripts in the repo that use NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY from .env.local).

- **Output:** Table **player_h2h** filled with OnCourt IDs and win counts.  
  **Deliverable:** Output the full Python script as a pasteable block (e.g. `scripts/sackmann-compute-h2h.py` or similar). User will create the file and run:  
  `python scripts/sackmann-compute-h2h.py [--dry-run]`

## Step 4: Script to compute and upsert advanced stats

- **Input:** Same Sackmann and TML match CSVs. Use columns like w_svpt, w_1stIn, w_1stWon, w_2ndWon, w_ace, w_df, w_SvGms, w_bpSaved, w_bpFaced (and l_* for the loser’s serve/return stats).
- **Steps:**
  1. Use the same player ID map (Step 2).
  2. For each match row, for winner and loser separately: map to OnCourt ID, get surface. Aggregate per (OnCourt_id, surface): totals for 1st serves in, 1st serve points won, 2nd serve points, 2nd serve points won, aces, double faults, service games, BP saved, BP faced; and for return side BP conversion (loser’s BP faced = winner’s BP converted, etc.). Compute rates (e.g. first_serve_pct = 1stIn / svpt, first_serve_win_pct = 1stWon / 1stIn, bp_save_pct = bpSaved / bpFaced).
  3. Upsert to **player_advanced_stats** (again OnCourt player_id only).

- **Output:** Table **player_advanced_stats** filled per (player_id, surface).  
  **Deliverable:** Output the full Python script as a pasteable block (e.g. `scripts/sackmann-compute-advanced-stats.py`). User will run:  
  `python scripts/sackmann-compute-advanced-stats.py [--dry-run]`

## Step 5: Integrate H2H in fair-odds

- In **scripts/oncourt-compute-fair-odds.py**:
  - After loading other lookups (venue, Elo, stats, etc.), **load player_h2h** from Supabase into a dict keyed by (player_a_id, player_b_id, surface) with canonical ordering (so for fixture (p1, p2, surface) you look up (min(p1,p2), max(p1,p2), surface)).
  - In the per-fixture loop, after computing p1_win (and before or after other small adjustments): look up H2H for (p1, p2, surface). If match_count >= 5 (or another chosen threshold), compute p1’s win rate = wins_p1 / (wins_p1 + wins_p2). wins_p1 is wins_a if p1 == player_a_id else wins_b. Then e.g. delta = (win_rate - 0.5) * 0.03, clamped to ±0.02, and add delta to p1_win (and subtract from p2_win). Do not change the rest of the pipeline (O/U, confidence, etc.).

- **Deliverable:** Output the exact code changes (pasteable diff or full modified sections) so the user can apply them to `oncourt-compute-fair-odds.py`.

## Step 6: Integrate advanced stats in fair-odds

- In **scripts/oncourt-compute-fair-odds.py**:
  - Load **player_advanced_stats** from Supabase (keyed by (player_id, surface)).
  - In the per-fixture loop, for each player get their row (if any). Use these stats as **extra inputs**: e.g. refine serve/return strength (first/second serve split) or add a small “clutch” or “matchup” adjustment (e.g. BP save vs opponent’s BP conversion). The exact formula can follow the previous Claude’s plan (first/second serve, BP clutch). Keep the existing Barnett–Clarke and Elo logic; add advanced stats as an **additional** small adjustment so we don’t break current behavior.

- **Deliverable:** Output the exact code changes as pasteable blocks.

---

# Part 5 — What not to change

- **O/U (totals)** logic in fair-odds — already updated (standard lines, median). Do not touch.
- **Confidence = "none"** and zero-data handling — leave as is.
- **player_surface_stats** and **oncourt-compute-player-stats.py** — do not replace; H2H and advanced stats are **add-ons**.
- **Barnett–Clarke** formula and point-level hold_pct/return_pct usage — keep; only **add** H2H and advanced-stats adjustments on top.

---

# Part 6 — Rule for Codex: paste only, do not write to repo

**Do not write, edit, or create any files in the repository.** Do not push, commit, or change the repo on disk or via GitHub.

Instead, output all code (SQL, Python, and any edits to existing files) as **pasteable blocks in the chat** (e.g. markdown code blocks with file paths). The user will review and copy the code into the project themselves.

**Example instruction to give Codex:**  
“Implement the H2H and advanced stats pipeline exactly as described in docs/CODEX-HANDOFF.md (or docs/DEBRIEF-H2H-AND-ADVANCED-STATS.md). Do Part 4 step by step: create the two SQL files, then the ID mapping and two Python scripts, then the two integrations in oncourt-compute-fair-odds.py. **Do not write or edit any files — output all code in the chat so I can paste it in myself.**”

---

# Part 7 — One-paragraph summary (for paste)

**Instruction for the AI:** Do not write or edit any files in the repo. Output all code (SQL, Python, edits) as pasteable blocks in the chat so the user can apply them manually.

We run a tennis fair-odds pipeline that uses **OnCourt** data only (fixtures, player_surface_stats, Elo) and write to **daily_fair_odds**. We want to **add H2H and advanced serve/return stats** (both required): (1) Create Supabase tables **player_h2h** (player_a_id, player_b_id, surface, wins_a, wins_b, match_count) and **player_advanced_stats** (player_id, surface, first_serve_pct, first_serve_win_pct, second_serve_win_pct, ace_rate, df_rate, bp_save_pct, bp_convert_pct, …), both using **OnCourt** player IDs. (2) Build a Sackmann/TML → OnCourt player ID map (e.g. by matching names to oncourt_players). (3) Script 1: read Sackmann + TML match CSVs, map IDs, aggregate H2H by (player_a, player_b, surface), upsert to player_h2h. (4) Script 2: same CSVs, map IDs, aggregate advanced stats per (player_id, surface), upsert to player_advanced_stats. (5) In **scripts/oncourt-compute-fair-odds.py**, load player_h2h and apply a small capped adjustment to p1_win when match_count >= 5. (6) Load player_advanced_stats and use as extra inputs (e.g. first/second serve split, BP clutch) with a small adjustment. Do not change O/U, confidence, or the OnCourt stats pipeline.

---

# Part 8 — Run order (for the user)

1. Run the two new SQL scripts in Supabase (create `player_h2h` and `player_advanced_stats`).
2. Run: `python scripts/sackmann-compute-h2h.py` (or the name Codex suggests).
3. Run: `python scripts/sackmann-compute-advanced-stats.py` (or the name Codex suggests).
4. Run fair-odds as usual (e.g. via `scripts/run-daily-odds.py` or `npm run daily-odds`). No change to the rest of the pipeline.

If Codex gets stuck on the ID map, suggest: “Match by normalizing names (lowercase, strip accents if needed, compare surname and initial/first name) between oncourt_players and winner_name/loser_name from the CSVs; keep the first match or the best match per Sackmann/TML ID.”
