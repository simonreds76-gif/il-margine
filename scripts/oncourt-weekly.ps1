# Il Margine - Weekly Scheduled Task (runs Sunday 03:00)
# Full refresh + weekly model feature refresh + strict signals analysis + settlement + performance

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root
. (Join-Path $root "scripts\task-lock.ps1")

$dataDir = Join-Path $root "data"
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$logFile = Join-Path $dataDir "oncourt-weekly.log"
# Enable trimmed shadow profile by default for scheduled runs (override with env if needed)
if ([string]::IsNullOrWhiteSpace($env:STRICT_POLICY_VOLUME_MODE)) { $env:STRICT_POLICY_VOLUME_MODE = "volume_200" }
$volumeMode = "$env:STRICT_POLICY_VOLUME_MODE".ToLower()
if ([string]::IsNullOrWhiteSpace($volumeMode)) { $volumeMode = "off" }

function Get-VolumeShadowConfig([string]$mode) {
    switch ($mode) {
        "volume_200" { return @{ Tag = "volume200"; Label = "ATP ML Research"; Profile = "volume_200" } }
        "volume_275" { return @{ Tag = "volume275"; Label = "Volume 275"; Profile = "volume_275" } }
        default { return $null }
    }
}

$volumeCfg = Get-VolumeShadowConfig $volumeMode

function Log($msg) {
    $line = "$(Get-Date -Format 'HH:mm:ss') $msg"
    Write-Host $line
    Add-Content -Path $logFile -Value $line
}

$lockHandle = Enter-TaskLock -LockName "tennis-automation" -RootPath $root -WaitSeconds 1800 -PollSeconds 10
if ($null -eq $lockHandle) {
    Log "Another tennis automation run stayed active for 30 minutes; exiting."
    exit 0
}

try {

Log "============================================"
Log "  Weekly Full Load started at $timestamp"
Log "============================================"

# Step 1: Extract from OnCourt (32-bit Python for .mdb)
Log "=== Step 1/13: OnCourt extract ==="
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
Log "=== Step 2/13: Supabase FULL sync ==="
& python scripts\oncourt-load-supabase.py 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "ERROR: Supabase full sync failed (exit $LASTEXITCODE)"
    exit 1
}

# Step 3: Extended player stats (writes v2 plus backwards-compatible table)
Log "=== Step 3/12: Compute extended player stats ==="
& python scripts\oncourt-compute-player-stats-extended.py 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: Extended player stats failed (exit $LASTEXITCODE), continuing..."
}

# Step 4: Refresh Sackmann ATP source files
Log "=== Step 4/12: Refresh Sackmann ATP source files ==="
& python scripts\sackmann-refresh-data.py --start-year 2023 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: Sackmann refresh failed (exit $LASTEXITCODE), continuing..."
}

# Step 5: Recompute H2H
Log "=== Step 5/12: Recompute H2H ==="
& python scripts\sackmann-compute-h2h.py 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: H2H recompute failed (exit $LASTEXITCODE), continuing..."
}

# Step 6: Recompute advanced stats
Log "=== Step 6/12: Recompute advanced stats ==="
& python scripts\sackmann-compute-advanced-stats.py 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: Advanced stats recompute failed (exit $LASTEXITCODE), continuing..."
}

# Step 7: Refresh TennisExplorer injured/returning CSV
Log "=== Step 7/12: Refresh injured players list (TennisExplorer) ==="
& python scripts\scrape-tennisexplorer-injured.py --max-pages 2 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: injured players scrape failed (exit $LASTEXITCODE), continuing..."
}

# Step 8: Refresh Tennis Abstract CPI/surface-speed table
Log "=== Step 8/12: Refresh CPI surface-speed table ==="
& python scripts\scrape-tennisabstract-surface-speed.py 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: CPI surface-speed refresh failed (exit $LASTEXITCODE), continuing..."
}

# Step 9: Run settlement/performance before slower external fetches.
Log "=== Step 9/12: Nightly-style settlement/performance refresh ==="
& powershell -ExecutionPolicy Bypass -NoProfile -File scripts\oncourt-settle-nightly.ps1 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: nightly settlement refresh failed (exit $LASTEXITCODE), continuing..."
}

# Step 10: Weekly strict-signals analysis
Log "=== Step 10/12: Refresh Tennis-Data ATP season file ==="
& python scripts\fetch-tennis-data-atp.py --year 2026 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: tennis-data ATP refresh failed (exit $LASTEXITCODE), continuing..."
}

# Step 11: Weekly strict-signals analysis
Log "=== Step 11/12: Analyse strict signals ==="
& python scripts\analyse-strict-signals.py --days 7 --input data\backtest\strict-signals-archive.csv 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: strict-signals analysis failed (exit $LASTEXITCODE), continuing..."
}

# Step 12: Append Pinnacle history capture (weekly checkpoint)
Log "=== Step 12/12: Append Pinnacle history capture (weekly) ==="
& python scripts\pinnacle-capture-history.py --capture-mode weekly 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: Pinnacle history append failed (exit $LASTEXITCODE), continuing..."
}

# Weekly CLV audits (captured history first, tennis-data fallback)
Log "=== Post-step: Strict CLV audit ==="
& python scripts\audit-strict-clv.py --signals data\backtest\strict-signals-archive.csv 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: strict CLV audit failed (exit $LASTEXITCODE), continuing..."
}

Log "=== Post-step: ATP ML Research CLV audit ==="
& python scripts\audit-strict-clv.py --signals data\backtest\strict-signals-volume200-archive.csv --detail-csv data\backtest\strict-clv-audit-volume200-2026.csv --summary-txt data\backtest\strict-clv-audit-volume200-2026.txt 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: ATP ML research CLV audit failed (exit $LASTEXITCODE), continuing..."
}

Log "============================================"
Log "  Weekly Full Load finished at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Log "============================================"
}
finally {
    Exit-TaskLock $lockHandle
}

