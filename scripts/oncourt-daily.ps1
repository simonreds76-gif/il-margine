# Il Margine — Daily Scheduled Task (runs at 23:55)
#
# Quick sync: players/tours/today only (skips 1M+ games/stat rows).
# Then scrapes Pinnacle odds + computes fair odds.
#
# Windows Task Scheduler runs this via:
#   powershell.exe -ExecutionPolicy Bypass -NoProfile -File "...\oncourt-daily.ps1"

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$logFile = Join-Path $root "data\oncourt-daily.log"

function Log($msg) {
    $line = "$(Get-Date -Format 'HH:mm:ss') $msg"
    Write-Host $line
    Add-Content -Path $logFile -Value $line
}

Log "============================================"
Log "  Daily Pipeline started at $timestamp"
Log "============================================"

# Step 1: Extract from OnCourt (32-bit Python for .mdb)
Log "=== Step 1/4: OnCourt extract ==="
$py32 = "C:\Python312-32\python.exe"
if (Test-Path $py32) {
    & $py32 scripts\oncourt-extract-all.py 2>&1 | ForEach-Object { Log $_ }
    if ($LASTEXITCODE -ne 0) {
        Log "WARNING: OnCourt extract had errors (exit $LASTEXITCODE), continuing..."
    }
} else {
    Log "WARNING: 32-bit Python not found at $py32, skipping extract"
}

# Step 2: Quick sync to Supabase (players/tours/today only)
Log "=== Step 2/4: Supabase sync (quick) ==="
& python scripts\oncourt-load-supabase.py --quick 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "ERROR: Supabase sync failed (exit $LASTEXITCODE)"
    exit 1
}

# Step 3: Compute player stats
Log "=== Step 3/4: Compute player stats ==="
& python scripts\oncourt-compute-player-stats.py 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: Player stats failed (exit $LASTEXITCODE), continuing..."
}

# Step 4: Pinnacle odds + fair odds
Log "=== Step 4/4: Pinnacle odds + fair odds ==="
& python scripts\run-daily-odds.py 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "ERROR: Pinnacle/fair-odds failed (exit $LASTEXITCODE)"
    exit 1
}

Log "============================================"
Log "  Daily Pipeline finished at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Log "============================================"
