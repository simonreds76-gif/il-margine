# Il Margine — Daily Scheduled Task (runs at 11:00 and 23:55)
# Fully automatic: extract -> sync -> stats -> injury/CPI refresh -> odds -> strict report append

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root
. (Join-Path $root "scripts\task-lock.ps1")

$dataDir = Join-Path $root "data"
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$logFile = Join-Path $dataDir "oncourt-daily.log"

# Choose sync args once here:
#   @("--quick")                  = fast daily including players/rankings
#   @("--recent")                 = last 365 days games/stat
$syncArgs = @("--quick")
$syncLabel = ($syncArgs -join " ")
# Enable trimmed shadow profile by default for scheduled runs (override with env if needed)
if ([string]::IsNullOrWhiteSpace($env:STRICT_POLICY_VOLUME_MODE)) { $env:STRICT_POLICY_VOLUME_MODE = "volume_200" }
$volumeMode = "$env:STRICT_POLICY_VOLUME_MODE".ToLower()
if ([string]::IsNullOrWhiteSpace($volumeMode)) { $volumeMode = "off" }
if ([string]::IsNullOrWhiteSpace($env:STRICT_SPREAD_V1_SHADOW_ENABLED)) { $env:STRICT_SPREAD_V1_SHADOW_ENABLED = "1" }
if ([string]::IsNullOrWhiteSpace($env:STRICT_CLAY_CALIBRATED_ENABLED)) { $env:STRICT_CLAY_CALIBRATED_ENABLED = "0" }

function Test-EnvFlag([string]$value) {
    if ([string]::IsNullOrWhiteSpace($value)) { return $false }
    return @("1", "true", "yes", "on") -contains $value.Trim().ToLower()
}

$spreadV1ShadowEnabled = Test-EnvFlag $env:STRICT_SPREAD_V1_SHADOW_ENABLED
$clayCalibratedEnabled = Test-EnvFlag $env:STRICT_CLAY_CALIBRATED_ENABLED

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
Log "  Daily Pipeline started at $timestamp"
Log "============================================"

# Step 1: Extract from OnCourt (32-bit Python for .mdb)
Log "=== Step 1/10: OnCourt extract ==="
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
Log "=== Step 2/10: Supabase sync ($syncLabel) ==="
& python scripts\oncourt-load-supabase.py @syncArgs 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "ERROR: Supabase sync failed (exit $LASTEXITCODE)"
    exit 1
}

# Step 3: Compute player stats (extended writes both v2 and backwards-compat tables)
Log "=== Step 3/10: Compute player stats (extended) ==="
& python scripts\oncourt-compute-player-stats-extended.py 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: Player stats failed (exit $LASTEXITCODE), continuing..."
}

# Step 4: Refresh TennisExplorer injured/returning CSV
Log "=== Step 4/10: Refresh injured players list (TennisExplorer) ==="
& python scripts\scrape-tennisexplorer-injured.py --max-pages 2 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: injured players scrape failed (exit $LASTEXITCODE), continuing..."
}

# Step 5: Refresh Tennis Abstract CPI/surface-speed table
Log "=== Step 5/10: Refresh CPI surface-speed table ==="
& python scripts\scrape-tennisabstract-surface-speed.py 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: CPI surface-speed refresh failed (exit $LASTEXITCODE), continuing..."
}

Log "=== Step 5b/10: Refresh spread_v1 calibration + correction model ==="
& python scripts\handicap-calibration.py --line-source auto 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: handicap calibration refresh failed (exit $LASTEXITCODE), continuing..."
}
& python scripts\fit-spread-v1-model.py 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: spread_v1 correction fit failed (exit $LASTEXITCODE), continuing..."
}

# Step 6: Pinnacle odds + fair odds
Log "=== Step 6/10: Pinnacle odds + fair odds ==="
$step6Output = & python scripts\run-daily-odds.py --skip-strict-report 2>&1
$step6Exit = $LASTEXITCODE
$step6Lines = @($step6Output | ForEach-Object { "$_" })
$step6Lines | ForEach-Object { Log $_ }
if ($step6Exit -ne 0) {
    Log "ERROR: Pinnacle/fair-odds failed (exit $step6Exit)"
    exit 1
}

$step6Synced = $step6Lines | Select-String -SimpleMatch "Synced daily_fair_odds:"
if (-not $step6Synced) {
    Log "ERROR: Pinnacle/fair-odds completed without confirming daily_fair_odds sync"
    exit 1
}

Log "=== Step 6b/10: Append Pinnacle history capture (daily) ==="
& python scripts\pinnacle-capture-history.py --capture-mode daily 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: Pinnacle history append failed (exit $LASTEXITCODE), continuing..."
}

# Step 7: Strict policy report + overlay comparison (auto-append CSVs)
Log "=== Step 7/10: Strict policy report (--append --compare-overlay) ==="
& python scripts\strict-policy-report.py --append --compare-overlay 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "ERROR: strict-policy-report failed (exit $LASTEXITCODE)"
    exit 1
}

# Step 8: Optional shadow volume profile (env-gated)
if ($null -ne $volumeCfg) {
    Log "=== Step 8/10: $($volumeCfg.Label) shadow (signal-profile=$($volumeCfg.Profile)) ==="
    & python scripts\strict-policy-report.py --append --signal-profile $volumeCfg.Profile --output "data\backtest\strict-signals-$($volumeCfg.Tag)-live.csv" --internal-output "data\backtest\strict-signals-$($volumeCfg.Tag)-internal-live.csv" 2>&1 | ForEach-Object { Log $_ }
    if ($LASTEXITCODE -ne 0) {
        Log "WARNING: $($volumeCfg.Profile) shadow append failed (exit $LASTEXITCODE), continuing..."
    }
} else {
    Log "=== Step 8/10: Volume shadow skipped (STRICT_POLICY_VOLUME_MODE=$volumeMode) ==="
}

if ($spreadV1ShadowEnabled) {
    Log "=== Step 8b/10: Spread v1 shadow (strict-first ATP bo3 hard/clay) ==="
    & python scripts\strict-policy-report.py --append --signal-profile spread_v1_shadow --output "data\backtest\strict-signals-spreadv1-live.csv" 2>&1 | ForEach-Object { Log $_ }
    if ($LASTEXITCODE -ne 0) {
        Log "WARNING: spread_v1_shadow append failed (exit $LASTEXITCODE), continuing..."
    }
} else {
    Log "=== Step 8b/10: Spread v1 shadow skipped (STRICT_SPREAD_V1_SHADOW_ENABLED=0) ==="
}

if ($clayCalibratedEnabled) {
    Log "=== Step 8c/10: Clay 2026 shadow (new-after-calibration favorites 55-65%) ==="
    & python scripts\strict-policy-report.py --append --signal-profile clay_calibrated --output "data\backtest\strict-signals-claycal-live.csv" --internal-output "data\backtest\strict-signals-claycal-internal-live.csv" 2>&1 | ForEach-Object { Log $_ }
    if ($LASTEXITCODE -ne 0) {
        Log "WARNING: clay_calibrated append failed (exit $LASTEXITCODE), continuing..."
    }
} else {
    Log "=== Step 8c/10: Clay 2026 shadow skipped (STRICT_CLAY_CALIBRATED_ENABLED=0) ==="
}

# Step 9: Settle/report immediately after nightly append so results are ready by the next morning.
Log "=== Step 9/10: Nightly tennis settlement/performance ==="
& powershell -ExecutionPolicy Bypass -NoProfile -File scripts\oncourt-settle-nightly.ps1 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: nightly tennis settlement failed (exit $LASTEXITCODE), continuing..."
}

Log "============================================"
Log "  Daily Pipeline finished at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Log "============================================"
}
finally {
    Exit-TaskLock $lockHandle
}
