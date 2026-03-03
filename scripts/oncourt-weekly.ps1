# Il Margine — Weekly Scheduled Task (runs Sunday 22:00)
#
# Full load: re-syncs ALL data including 1M+ games and stats rows.
# This catches any historical corrections from OnCourt updates.
#
# Windows Task Scheduler runs this via:
#   powershell.exe -ExecutionPolicy Bypass -NoProfile -File "...\oncourt-weekly.ps1"

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$logFile = Join-Path $root "data\oncourt-weekly.log"

function Log($msg) {
    $line = "$(Get-Date -Format 'HH:mm:ss') $msg"
    Write-Host $line
    Add-Content -Path $logFile -Value $line
}

Log "============================================"
Log "  Weekly Full Load started at $timestamp"
Log "============================================"

# Step 1: Extract from OnCourt (32-bit Python for .mdb)
Log "=== Step 1/3: OnCourt extract ==="
$py32 = "C:\Python312-32\python.exe"
if (Test-Path $py32) {
    & $py32 scripts\oncourt-extract-all.py 2>&1 | ForEach-Object { Log $_ }
    if ($LASTEXITCODE -ne 0) {
        Log "WARNING: OnCourt extract had errors (exit $LASTEXITCODE), continuing..."
    }
} else {
    Log "WARNING: 32-bit Python not found at $py32, skipping extract"
}

# Step 2: FULL sync to Supabase (all tables including games + stat)
Log "=== Step 2/3: Supabase FULL sync ==="
& python scripts\oncourt-load-supabase.py 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "ERROR: Supabase full sync failed (exit $LASTEXITCODE)"
    exit 1
}

# Step 3: Compute player stats
Log "=== Step 3/3: Compute player stats ==="
& python scripts\oncourt-compute-player-stats.py 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: Player stats failed (exit $LASTEXITCODE), continuing..."
}

Log "============================================"
Log "  Weekly Full Load finished at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Log "============================================"
