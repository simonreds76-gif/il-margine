# OnCourt Extraction & Load

## Prerequisites

- **32-bit Python** at `C:\Python312-32\python.exe` (for Access .mdb)
- **OnCourt** closed when extracting
- **Password:** Set `ONCOURT_PWD` env var

## Phase 1.1 – Extract to CSV

```powershell
$env:ONCOURT_PWD="your_password"
C:\Python312-32\python.exe scripts/oncourt-extract-all.py
```

Or run individually:
- `oncourt-extract-games.py` → `data/oncourt/games_atp.csv`
- `oncourt-extract-stats.py` → `data/oncourt/stat_atp.csv`
- `oncourt-extract-rest.py` → `data/oncourt/players_atp.csv`, `tours_atp.csv`, `courts.csv`, `today_atp.csv`

## Phase 1.2 – Create Supabase Tables

1. Supabase Dashboard → SQL Editor
2. Run `docs/supabase-oncourt-schema.sql`
3. Run `docs/supabase-player-hand-reference.sql` (for leftie list used by chat + fair-odds)

## Phase 1.3 – Load into Supabase

```powershell
$env:SUPABASE_URL="https://xxx.supabase.co"
$env:SUPABASE_SERVICE_ROLE_KEY="your_service_role_key"
C:\Python312-32\python.exe -m pip install supabase
C:\Python312-32\python.exe scripts/oncourt-load-supabase.py
```

Get credentials: Supabase Dashboard → Settings → API (URL + service_role key).

**player_hand_reference** is loaded from `data/oncourt/categories_atp.csv` (cat1=True = left-handed). Requires that CSV and the table from `docs/supabase-player-hand-reference.sql`. Also runnable standalone: `python scripts/oncourt-load-player-hand.py`

## One-shot: Extract + Load

```powershell
$env:ONCOURT_PWD="..."
$env:SUPABASE_URL="..."
$env:SUPABASE_SERVICE_ROLE_KEY="..."
C:\Python312-32\python.exe scripts/oncourt-extract-all.py
C:\Python312-32\python.exe scripts/oncourt-load-supabase.py
```
