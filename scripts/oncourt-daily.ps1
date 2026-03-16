# Il Margine — Daily Scheduled Task (runs at 11:00 and 23:55)
# Fully automatic: extract -> sync -> stats -> injury/CPI refresh -> odds -> strict report append

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

$dataDir = Join-Path $root "data"
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$logFile = Join-Path $dataDir "oncourt-daily.log"

# Choose sync args once here:
#   @("--quick","--skip-players") = fast daily (tours/today; rankings refresh weekly)
#   @("--quick")                  = fast daily including players/rankings
#   @("--recent")                 = last 365 days games/stat
$syncArgs = @("--quick", "--skip-players")
$syncLabel = ($syncArgs -join " ")
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
Log "  Daily Pipeline started at $timestamp"
Log "============================================"

# Step 1: Extract from OnCourt (32-bit Python for .mdb)
Log "=== Step 1/7: OnCourt extract ==="
$py32 = "C:\Python312-32\python.exe"
if (Test-Path $py32) {
    & $py32 scripts\oncourt-extract-all.py 2>&1 | ForEach-Object { Log $_ }
    if ($LASTEXITCODE -ne 0) {
        Log "WARNING: OnCourt extract had errors (exit $LASTEXITCODE), continuing..."
    }
} else {
    Log "WARNING: 32-bit Python not found at $py32, skipping extract"
}

# Step 2: Sync to Supabase
Log "=== Step 2/7: Supabase sync ($syncLabel) ==="
& python scripts\oncourt-load-supabase.py @syncArgs 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "ERROR: Supabase sync failed (exit $LASTEXITCODE)"
    exit 1
}

# Step 3: Compute player stats
Log "=== Step 3/7: Compute player stats ==="
& python scripts\oncourt-compute-player-stats.py 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: Player stats failed (exit $LASTEXITCODE), continuing..."
}

# Step 4: Refresh TennisExplorer injured/returning CSV
Log "=== Step 4/7: Refresh injured players list (TennisExplorer) ==="
& python scripts\scrape-tennisexplorer-injured.py --max-pages 2 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: injured players scrape failed (exit $LASTEXITCODE), continuing..."
}

# Step 5: Refresh Tennis Abstract CPI/surface-speed table
Log "=== Step 5/7: Refresh CPI surface-speed table ==="
& python scripts\scrape-tennisabstract-surface-speed.py 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: CPI surface-speed refresh failed (exit $LASTEXITCODE), continuing..."
}

# Step 6: Pinnacle odds + fair odds
Log "=== Step 6/9: Pinnacle odds + fair odds ==="
& python scripts\run-daily-odds.py --skip-strict-report 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "ERROR: Pinnacle/fair-odds failed (exit $LASTEXITCODE)"
    exit 1
}

Log "=== Step 6b/9: Append Pinnacle history capture (daily) ==="
& python scripts\pinnacle-capture-history.py --capture-mode daily 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: Pinnacle history append failed (exit $LASTEXITCODE), continuing..."
}

# Step 7: Strict policy report + overlay comparison (auto-append CSVs)
Log "=== Step 7/9: Strict policy report (--append --compare-overlay) ==="
& python scripts\strict-policy-report.py --append --compare-overlay 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "ERROR: strict-policy-report failed (exit $LASTEXITCODE)"
    exit 1
}

# Step 8: Optional shadow volume profile (env-gated)
if ($null -ne $volumeCfg) {
    Log "=== Step 8/9: $($volumeCfg.Label) shadow (signal-profile=$($volumeCfg.Profile)) ==="
    & python scripts\strict-policy-report.py --append --signal-profile $volumeCfg.Profile --output "data\backtest\strict-signals-$($volumeCfg.Tag).csv" --internal-output "data\backtest\strict-signals-$($volumeCfg.Tag)-internal.csv" 2>&1 | ForEach-Object { Log $_ }
    if ($LASTEXITCODE -ne 0) {
        Log "WARNING: $($volumeCfg.Profile) shadow append failed (exit $LASTEXITCODE), continuing..."
    }
} else {
    Log "=== Step 8/9: Volume shadow skipped (STRICT_POLICY_VOLUME_MODE=$volumeMode) ==="
}

Log "=== Step 8b/9: Spread shadow (20%+ handicap edges; Clay + non-policy tournaments) ==="
& python scripts\strict-policy-report.py --append --signal-profile spread_shadow --output "data\backtest\strict-signals-spreadshadow.csv" 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: spread_shadow append failed (exit $LASTEXITCODE), continuing..."
}

Log "============================================"
Log "  Daily Pipeline finished at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Log "============================================"
