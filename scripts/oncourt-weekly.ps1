# Il Margine - Weekly Scheduled Task (runs Sunday 22:00)
# Full refresh + weekly model feature refresh + strict signals analysis + settlement + performance

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

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
        "volume_200" { return @{ Tag = "volume200"; Label = "Volume 200"; Profile = "volume_200" } }
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

Log "============================================"
Log "  Weekly Full Load started at $timestamp"
Log "============================================"

# Step 1: Extract from OnCourt (32-bit Python for .mdb)
Log "=== Step 1/12: OnCourt extract ==="
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
Log "=== Step 2/12: Supabase FULL sync ==="
& python scripts\oncourt-load-supabase.py 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "ERROR: Supabase full sync failed (exit $LASTEXITCODE)"
    exit 1
}

# Step 3: Compute player stats
Log "=== Step 3/12: Compute player stats ==="
& python scripts\oncourt-compute-player-stats.py 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: Player stats failed (exit $LASTEXITCODE), continuing..."
}

# Step 3b: Extended player stats (v2 table — decomposed serve profiles)
Log "=== Step 3b/12: Compute extended player stats (v2) ==="
& python scripts\oncourt-compute-player-stats-extended.py 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: Extended player stats failed (exit $LASTEXITCODE), continuing..."
}

# Step 4: Recompute H2H
Log "=== Step 4/12: Recompute H2H ==="
& python scripts\sackmann-compute-h2h.py 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: H2H recompute failed (exit $LASTEXITCODE), continuing..."
}

# Step 5: Recompute advanced stats
Log "=== Step 5/12: Recompute advanced stats ==="
& python scripts\sackmann-compute-advanced-stats.py 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: Advanced stats recompute failed (exit $LASTEXITCODE), continuing..."
}

# Step 6: Refresh TennisExplorer injured/returning CSV
Log "=== Step 6/12: Refresh injured players list (TennisExplorer) ==="
& python scripts\scrape-tennisexplorer-injured.py --max-pages 2 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: injured players scrape failed (exit $LASTEXITCODE), continuing..."
}

# Step 7: Refresh Tennis Abstract CPI/surface-speed table
Log "=== Step 7/12: Refresh CPI surface-speed table ==="
& python scripts\scrape-tennisabstract-surface-speed.py 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: CPI surface-speed refresh failed (exit $LASTEXITCODE), continuing..."
}

# Step 8: Weekly strict-signals analysis
Log "=== Step 8/14: Refresh Tennis-Data ATP season file ==="
& python scripts\fetch-tennis-data-atp.py --year 2026 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: tennis-data ATP refresh failed (exit $LASTEXITCODE), continuing..."
}

# Step 9: Weekly strict-signals analysis
Log "=== Step 9/14: Analyse strict signals ==="
& python scripts\analyse-strict-signals.py --days 7 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: strict-signals analysis failed (exit $LASTEXITCODE), continuing..."
}

# Step 10: Settle strict signals from OnCourt results
Log "=== Step 10/14: Settle strict signals (production CSV, 10%+) ==="
& python scripts\settle-strict-signals.py 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: strict-signals settlement failed (exit $LASTEXITCODE), continuing..."
}

# Step 10b: Settle internal 5%+ tracking (confirmation window)
Log "=== Step 10b/14: Settle strict signals (internal 5%+ CSV) ==="
& python scripts\settle-strict-signals.py --csv data\backtest\strict-signals-internal-5pct.csv 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: strict-signals-internal-5pct settlement failed (exit $LASTEXITCODE), continuing..."
}

# Step 11: Settle strict signals overlay-compare rows
Log "=== Step 11/14: Settle strict signals (overlay-compare CSV) ==="
& python scripts\settle-strict-signals.py --csv data\backtest\strict-signals-overlay-compare.csv 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: strict-signals overlay-compare settlement failed (exit $LASTEXITCODE), continuing..."
}

# Step 11b: Optional settle shadow-volume signals (env-gated)
if ($null -ne $volumeCfg) {
    Log "=== Step 11b/14: Settle strict signals ($($volumeCfg.Label) shadow CSV) ==="
    & python scripts\settle-strict-signals.py --csv "data\backtest\strict-signals-$($volumeCfg.Tag).csv" 2>&1 | ForEach-Object { Log $_ }
    if ($LASTEXITCODE -ne 0) {
        Log "WARNING: strict-signals-$($volumeCfg.Tag) settlement failed (exit $LASTEXITCODE), continuing..."
    }
} else {
    Log "=== Step 11b/14: Volume settlement skipped (STRICT_POLICY_VOLUME_MODE=$volumeMode) ==="
}

# Step 12: Weekly settled performance (base vs overlay)
Log "=== Step 12/14: Strict policy settled performance ==="
& python scripts\strict-policy-performance.py --days 7 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: strict-policy-performance failed (exit $LASTEXITCODE), continuing..."
}

# Step 12b: Optional weekly settled performance for shadow volume profile (env-gated)
if ($null -ne $volumeCfg) {
    Log "=== Step 12b/14: $($volumeCfg.Label) settled performance ==="
    & python scripts\strict-policy-performance.py --days 7 --signals "data\backtest\strict-signals-$($volumeCfg.Tag).csv" --compare "data\backtest\strict-signals-$($volumeCfg.Tag)-compare.csv" --report-txt "data\backtest\strict-policy-performance-$($volumeCfg.Tag)-weekly.txt" --summary-csv "data\backtest\strict-policy-performance-$($volumeCfg.Tag)-weekly.csv" 2>&1 | ForEach-Object { Log $_ }
    if ($LASTEXITCODE -ne 0) {
        Log "WARNING: strict-policy-performance $($volumeCfg.Profile) failed (exit $LASTEXITCODE), continuing..."
    }
} else {
    Log "=== Step 12b/14: Volume performance skipped (STRICT_POLICY_VOLUME_MODE=$volumeMode) ==="
}

# Step 13: Weekly CLV audit (history first, tennis-data fallback)
Log "=== Step 13/14: Strict CLV audit ==="
& python scripts\audit-strict-clv.py 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: strict CLV audit failed (exit $LASTEXITCODE), continuing..."
}

# Step 14: Append Pinnacle history capture (weekly checkpoint)
Log "=== Step 14/14: Append Pinnacle history capture (weekly) ==="
& python scripts\pinnacle-capture-history.py --capture-mode weekly 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: Pinnacle history append failed (exit $LASTEXITCODE), continuing..."
}

Log "============================================"
Log "  Weekly Full Load finished at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Log "============================================"
