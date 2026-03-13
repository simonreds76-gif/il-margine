# Codex: Extract OnCourt Rankings and Wire to Fair Odds

## Problem

The fair-odds model uses `atp_rank`, `hard_points`, `clay_points`, `grass_points` from `oncourt_players` in Supabase. Currently these columns are **not populated** by our pipeline. We extract `players_atp` from OnCourt with only `id, name, birthdate, country` — no rank or points. As a result, rank data is stale/wrong (e.g. Dzumhur shown as rank 60 when he is ~160), causing the model to favor the wrong player.

OnCourt has a **rankings** category with official ATP rankings (including by surface). We are not extracting it.

## Task

1. **Browse OnCourt.mdb** and find the rankings table(s).
2. **Extract** the rankings data.
3. **Load** it into Supabase and wire it to the fair-odds pipeline.

---

## Step 1: List OnCourt Tables

Run:

```powershell
$env:ONCOURT_PWD="your_password"
C:\Python312-32\python.exe scripts/oncourt-list-tables.py
```

This lists all tables and columns in `C:\Program Files (x86)\OnCourt\OnCourt.mdb`. Look for tables with "rank", "point", or "ranking" in the name. Note the exact table name(s) and column names (e.g. `ID_P`, `RANK`, `POINTS`, `HARD`, `CLAY`, `GRASS`).

---

## Step 2: Add Extraction

In `scripts/oncourt-extract-rest.py`:

- Add `extract_table()` calls for the rankings table(s) you found.
- Use the same pattern as `players_atp` and `tours_atp`.
- Output to `data/oncourt/` (e.g. `rankings_atp.csv` or `player_rankings_atp.csv`).
- Ensure the output includes a **player ID** column that matches `oncourt_players.id` (OnCourt uses `ID_P` for players).
- Include columns for: overall rank, and ideally surface-specific points (hard, clay, grass) if available.

---

## Step 3: Add Migration for oncourt_players

Create `docs/supabase-migration-oncourt-players-rank.sql`:

```sql
-- Add rank and points columns to oncourt_players (run in Supabase SQL Editor).
ALTER TABLE public.oncourt_players
  ADD COLUMN IF NOT EXISTS atp_rank INTEGER,
  ADD COLUMN IF NOT EXISTS hard_points NUMERIC,
  ADD COLUMN IF NOT EXISTS clay_points NUMERIC,
  ADD COLUMN IF NOT EXISTS grass_points NUMERIC;
```

Run this in Supabase SQL Editor if the columns don't exist.

---

## Step 4: Add Load Step

In `scripts/oncourt-load-supabase.py`:

- After loading `oncourt_players` from `players_atp.csv`, load the rankings CSV.
- **Match by player ID** (OnCourt ID) to `oncourt_players.id`.
- **PATCH** (or upsert) `oncourt_players` with `atp_rank`, `hard_points`, `clay_points`, `grass_points` for each player.

Options:
- **A)** Merge rankings into the players payload before upsert (if rankings CSV has same player IDs as players_atp).
- **B)** Load rankings to a separate table `player_rankings` (player_id, atp_rank, hard_points, clay_points, grass_points), then run a second pass that PATCHes `oncourt_players` from that table.
- **C)** If OnCourt rankings table has one row per player, join it with players_atp during export and write a combined `players_atp.csv` (with rank columns). Then update the load lambda to include those columns.

---

## Step 5: Wire Fair Odds

The fair-odds script (`scripts/oncourt-compute-fair-odds.py`) already reads `atp_rank`, `hard_points`, `clay_points`, `grass_points` from `oncourt_players` (lines 1424–1457). No changes needed there — once the columns are populated, it will use them.

---

## Reference Files

| File | Purpose |
|------|---------|
| `scripts/oncourt-list-tables.py` | List OnCourt tables (run first) |
| `scripts/oncourt-extract-rest.py` | Add rankings extraction |
| `scripts/oncourt-load-supabase.py` | Add rankings load into oncourt_players |
| `docs/supabase-oncourt-schema.sql` | Base schema (oncourt_players has id, name, birthdate, country) |
| `scripts/oncourt-compute-fair-odds.py` | Consumes atp_rank, hard_points, clay_points, grass_points from oncourt_players |

---

## Environment

- **OnCourt:** 32-bit Python at `C:\Python312-32\python.exe`, pyodbc, `ONCOURT_PWD` env var.
- **Supabase:** `NEXT_PUBLIC_SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` in `.env.local`.

---

## Pipeline Order

After implementation, the daily run should:

1. `oncourt-extract-all.py` (or `oncourt-extract-rest.py`) — includes rankings extraction.
2. `oncourt-load-supabase.py` — loads players + rankings into oncourt_players.
3. `oncourt-compute-fair-odds.py` — uses fresh rank data.

---

## Success Criteria

- `oncourt-list-tables.py` run and rankings table identified.
- Rankings extracted to CSV.
- oncourt_players has atp_rank, hard_points, clay_points, grass_points populated.
- `oncourt-compute-fair-odds.py --debug Dzumhur,Wong` shows correct ranks (e.g. Dzumhur ~160, Wong ~90–130).
