# Il Margine - Weekly Scheduled Task (runs Sunday 22:00)
# Full refresh + weekly model feature refresh + strict signals analysis + settlement + performance

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

$dataDir = Join-Path $root "data"
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$logFile = Join-Path $dataDir "oncourt-weekly.log"

function Log($msg) {
    $line = "$(Get-Date -Format 'HH:mm:ss') $msg"
    Write-Host $line
    Add-Content -Path $logFile -Value $line
}

Log "============================================"
Log "  Weekly Full Load started at $timestamp"
Log "============================================"

# Step 1: Extract from OnCourt (32-bit Python for .mdb)
Log "=== Step 1/11: OnCourt extract ==="
$py32 = "C:\Python312-32\python.exe"
if (Test-Path $py32) {
    & $py32 scripts\oncourt-extract-all.py 2>&1 | ForEach-Object { Log $_ }
    if ($LASTEXITCODE -ne 0) {
        Log "WARNING: OnCourt extract had errors (exit $LASTEXITCODE), continuing..."
    }
} else {
    Log "WARNING: 32-bit Python not found at $py32, skipping extract"
}

# Step 2: FULL sync to Supabase
Log "=== Step 2/11: Supabase FULL sync ==="
& python scripts\oncourt-load-supabase.py 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "ERROR: Supabase full sync failed (exit $LASTEXITCODE)"
    exit 1
}

# Step 3: Compute player stats
Log "=== Step 3/11: Compute player stats ==="
& python scripts\oncourt-compute-player-stats.py 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: Player stats failed (exit $LASTEXITCODE), continuing..."
}

# Step 4: Recompute H2H
Log "=== Step 4/11: Recompute H2H ==="
& python scripts\sackmann-compute-h2h.py 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: H2H recompute failed (exit $LASTEXITCODE), continuing..."
}

# Step 5: Recompute advanced stats
Log "=== Step 5/11: Recompute advanced stats ==="
& python scripts\sackmann-compute-advanced-stats.py 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: Advanced stats recompute failed (exit $LASTEXITCODE), continuing..."
}

# Step 6: Refresh TennisExplorer injured/returning CSV
Log "=== Step 6/11: Refresh injured players list (TennisExplorer) ==="
& python scripts\scrape-tennisexplorer-injured.py --max-pages 2 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: injured players scrape failed (exit $LASTEXITCODE), continuing..."
}

# Step 7: Refresh Tennis Abstract CPI/surface-speed table
Log "=== Step 7/11: Refresh CPI surface-speed table ==="
& python scripts\scrape-tennisabstract-surface-speed.py 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: CPI surface-speed refresh failed (exit $LASTEXITCODE), continuing..."
}

# Step 8: Weekly strict-signals analysis
Log "=== Step 8/11: Analyse strict signals ==="
& python scripts\analyse-strict-signals.py --days 7 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: strict-signals analysis failed (exit $LASTEXITCODE), continuing..."
}

# Step 9: Settle strict signals from OnCourt results
Log "=== Step 9/11: Settle strict signals (production CSV) ==="
& python scripts\settle-strict-signals.py 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: strict-signals settlement failed (exit $LASTEXITCODE), continuing..."
}

# Step 10: Settle strict signals overlay-compare rows
Log "=== Step 10/11: Settle strict signals (overlay-compare CSV) ==="
& python scripts\settle-strict-signals.py --csv data\backtest\strict-signals-overlay-compare.csv 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: strict-signals overlay-compare settlement failed (exit $LASTEXITCODE), continuing..."
}

# Step 11: Weekly settled performance (base vs overlay)
Log "=== Step 11/11: Strict policy settled performance ==="
& python scripts\strict-policy-performance.py --days 7 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: strict-policy-performance failed (exit $LASTEXITCODE), continuing..."
}

Log "============================================"
Log "  Weekly Full Load finished at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Log "============================================"
