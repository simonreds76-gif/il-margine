# Handoff: Fix player_hand_reference and recalibrate model with complete lefties data

**For:** Codex  
**Goal:** Fix the player_hand_reference load so it works without any manual steps from the user. Then ensure the fair-odds model is recalibrated with the newly complete lefties data. The user cannot run SQL in Supabase or add env vars manually — you must fix everything so the pipeline runs end-to-end.

---

## What’s broken

### 1. player_hand_reference load fails

- **Table:** `player_hand_reference` — stores left-handed players (hand=L) for vs-leftie stats and model adjustments.
- **Source:** `data/oncourt/categories_atp.csv` (OnCourt extract). `cat1=True` = left-handed.
- **Loaders:** `scripts/oncourt-load-player-hand.py` (standalone) and `scripts/oncourt-load-supabase.py` (step 6 of full sync).

**Errors seen:**
- `null value in column "source" violates not-null constraint` — table has a `source` column that our schema didn’t define.
- `player_hand_reference_source_check` — CHECK constraint on `source` rejects our value `"oncourt"` (allowed values unknown).

**Current “fix” (not good enough):**
- Cursor added `docs/supabase-player-hand-reference-fix.sql` and auto-migration logic that runs when `DATABASE_URL` is set.
- **Problem:** The user does not have `DATABASE_URL` and cannot add it. They cannot run SQL in Supabase. The pipeline must work without any manual setup.

### 2. Lefties data was incomplete

- The leftie list feeds:
  - **Fair-odds model** (`scripts/oncourt-compute-fair-odds.py`): vs-leftie adjustment (lines ~700–766, ~1891–1897). Uses `leftie_ids` from `player_hand_reference` and `vs_leftie_lookup` from `player_vs_leftie_stats`.
  - **Chat tools** (`src/lib/chat-tools.ts`): `player_record_vs_lefties` for W-L vs left-handed opponents.
- Because the load was failing, `player_hand_reference` was empty or stale. The model fell back to `oncourt_player_extra` + `oncourt_categories`, which are incomplete (e.g. Shelton and others missing).
- **Result:** vs-leftie adjustments in the model were wrong. The model needs recalibrating with the new, complete lefties data.

---

## What you must do

### 1. Fix the load so it works with zero manual steps

**Constraint:** No `DATABASE_URL`, no Supabase SQL Editor, no env var changes by the user.

**Options to consider:**
- **A)** Ensure the table schema matches what we send. If the Supabase table was created with a different schema (e.g. `source` NOT NULL with a restrictive CHECK), we need a migration that runs automatically. The only way without `DATABASE_URL` is if the project has Supabase CLI linked and we can run `supabase db execute` or similar from the script. Check if that’s possible.
- **B)** If the table can be recreated: update `docs/supabase-player-hand-reference.sql` to include the `source` column with the right constraint, and have the load script create the table if it doesn’t exist (or use a different approach that doesn’t require DDL).
- **C)** Use a different `source` value that the existing CHECK allows. We don’t know the allowed values — you may need to inspect the constraint (e.g. via Supabase dashboard or a one-off script that uses service-role to query `information_schema.check_constraints`) or try common values like `'manual'`, `'atp'`, etc.
- **D)** If the table has no `source` column in the original schema, stop sending it. Our `docs/supabase-player-hand-reference.sql` was updated to include `source`; the live table may have been created from an older version. Align schema and payload.

**Deliverable:** `oncourt-load-supabase.py` (and `oncourt-load-player-hand.py`) must succeed when run as part of the daily pipeline, with no manual intervention.

### 2. Recompute vs-leftie stats and recalibrate the model

- **player_vs_leftie_stats:** The fair-odds model reads from this table (Supabase). It’s not clear if it’s a view or a materialized table. If it’s a view, it likely depends on `player_hand_reference` — once that’s fixed, the view should be correct. If it’s a table, there must be a script that populates it; find it and ensure it runs after `player_hand_reference` is loaded.
- **Recalibration:** After `player_hand_reference` is correctly populated:
  1. Ensure `player_vs_leftie_stats` is refreshed (or the view reflects the new data).
  2. Re-run the fair-odds computation so today’s `daily_fair_odds` uses the complete lefties data.
  3. The model uses `VS_LEFTIE_WEIGHT` and `win_pct_vs_leftie`; with more complete leftie IDs, the vs-leftie adjustments will change. No code change to the model logic is required — just ensure the pipeline runs with the fixed data.

### 3. Pipeline order

Daily pipeline (`scripts/oncourt-daily.ps1`):

1. OnCourt extract → CSVs
2. Supabase sync (`oncourt-load-supabase.py`) — includes `player_hand_reference`
3. Compute player stats (`oncourt-compute-player-stats.py`)
4. Injured players scrape
5. CPI refresh
6. Pinnacle odds + fair odds (`run-daily-odds.py` → `oncourt-compute-fair-odds.py`)
7. Strict policy report

Step 2 must succeed (including `player_hand_reference`). Step 6 reads lefties and vs-leftie stats. Fix step 2 first; then step 6 will use the correct data.

---

## Files to touch

- `scripts/oncourt-load-supabase.py` — `_load_player_hand()`, fix so it works
- `scripts/oncourt-load-player-hand.py` — standalone loader, same fix
- `docs/supabase-player-hand-reference.sql` — schema (already has `source`; align with live DB)
- `docs/supabase-player-hand-reference-fix.sql` — migration Cursor added; may need adjustment or a different approach
- Possibly: Supabase CLI / migration setup if we can run DDL from the pipeline
- `scripts/oncourt-compute-fair-odds.py` — no logic change; ensure it runs after the load with correct data
- `scripts/run-daily-odds.py` — ensure fair-odds runs after sync (it already does)

---

## Important constraints

- **User cannot:** Run SQL in Supabase, add `DATABASE_URL`, or do any manual setup.
- **You must:** Make the pipeline work end-to-end with the existing env vars (`NEXT_PUBLIC_SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`).
- **Recalibration:** The lefties data was incomplete; the model has been using wrong vs-leftie adjustments. Fix the load, then run the pipeline so the model gets the correct data. Do this now — the model needs recalibrating with the new data.

---

## Reference: current load logic

```python
# scripts/oncourt-load-supabase.py _load_player_hand()
# Reads categories_atp.csv, cat1=True → left-handed
rows.append({"player_id": pid, "hand": "L", "source": "oncourt"})
_upsert("player_hand_reference", batch, "player_id")
```

The payload is `{player_id, hand, source}`. The table expects these; the `source` CHECK is blocking us.
