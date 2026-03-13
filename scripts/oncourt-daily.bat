@echo off
REM ============================================================
REM  Il Margine - Daily Pipeline
REM  Run this after updating OnCourt software.
REM
REM  Steps:
REM    1. Extract from OnCourt .mdb (needs 32-bit Python)
REM    2. Sync CSVs to Supabase
REM    3. Compute player stats (hold%/return%)
REM    4. Refresh TennisExplorer injured/returning list
REM    5. Refresh Tennis Abstract CPI/surface-speed table
REM    6. Scrape Pinnacle odds (API) + compute fair odds
REM
REM  Usage: double-click this file, or run from terminal:
REM    scripts\oncourt-daily.bat
REM ============================================================

cd /d "%~dp0\.."
echo.
echo ============================================================
echo   Il Margine Daily Pipeline
echo   %DATE% %TIME%
echo ============================================================
echo.

REM --- Step 1: Extract from OnCourt (32-bit Python required for .mdb) ---
echo === Step 1/6: OnCourt extract ===
echo.
C:\Python312-32\python.exe scripts\oncourt-extract-all.py
if %ERRORLEVEL% neq 0 (
    echo.
    echo ERROR: OnCourt extract failed. Check ONCOURT_PWD env var and .mdb path.
    pause
    exit /b 1
)
echo.

REM --- Step 2: Sync to Supabase (--quick --skip-players = tours/today only; rankings weekly) ---
REM   First time? Run: python scripts\oncourt-load-supabase.py  (full load)
echo === Step 2/6: Sync to Supabase (quick) ===
echo.
python scripts\oncourt-load-supabase.py --quick --skip-players
if %ERRORLEVEL% neq 0 (
    echo.
    echo ERROR: Supabase sync failed. Check .env.local credentials.
    pause
    exit /b 1
)
echo.

REM --- Step 3: Compute player stats ---
echo === Step 3/6: Compute player stats ===
echo.
python scripts\oncourt-compute-player-stats.py
if %ERRORLEVEL% neq 0 (
    echo.
    echo ERROR: Player stats computation failed.
    pause
    exit /b 1
)
echo.

REM --- Step 4: Pinnacle scraper + fair odds ---
echo === Step 4/6: Refresh injured players list (TennisExplorer) ===
echo.
python scripts\scrape-tennisexplorer-injured.py --max-pages 2
if %ERRORLEVEL% neq 0 (
    echo.
    echo WARNING: injured players scrape failed. Continuing...
)
echo.

REM --- Step 5: Refresh CPI/surface-speed table ---
echo === Step 5/6: Refresh CPI/surface-speed table ===
echo.
python scripts\scrape-tennisabstract-surface-speed.py
if %ERRORLEVEL% neq 0 (
    echo.
    echo WARNING: CPI surface-speed refresh failed. Continuing...
)
echo.

REM --- Step 6: Pinnacle scraper + fair odds ---
echo === Step 6/6: Pinnacle odds + fair odds ===
echo.
python scripts\run-daily-odds.py
if %ERRORLEVEL% neq 0 (
    echo.
    echo ERROR: Pinnacle/fair-odds pipeline failed.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   All done! Refresh http://localhost:3000/fair-odds
echo ============================================================
echo.
pause
