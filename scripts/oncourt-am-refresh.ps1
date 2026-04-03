# Il Margine - AM Tennis Refresh
# Lighter daytime refresh: odds/fair-odds/shadow append/settlement without a full OnCourt sync.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root
. (Join-Path $root "scripts\task-lock.ps1")

$dataDir = Join-Path $root "data"
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$logFile = Join-Path $dataDir "oncourt-am-refresh.log"

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

$lockHandle = Enter-TaskLock -LockName "tennis-automation" -RootPath $root
if ($null -eq $lockHandle) {
    Log "Another tennis automation run is already active; exiting."
    exit 0
}

try {
    Log "============================================"
    Log "  AM Tennis Refresh started at $timestamp"
    Log "============================================"

    Log "=== Step 1/6: Pinnacle odds + fair odds ==="
    $step1Output = & python scripts\run-daily-odds.py --skip-strict-report 2>&1
    $step1Exit = $LASTEXITCODE
    $step1Lines = @($step1Output | ForEach-Object { "$_" })
    $step1Lines | ForEach-Object { Log $_ }
    if ($step1Exit -ne 0) {
        Log "ERROR: Pinnacle/fair-odds failed (exit $step1Exit)"
        exit 1
    }
    $step1Synced = $step1Lines | Select-String -SimpleMatch "Synced daily_fair_odds:"
    if (-not $step1Synced) {
        Log "ERROR: Pinnacle/fair-odds completed without confirming daily_fair_odds sync"
        exit 1
    }

    Log "=== Step 2/6: Append Pinnacle history capture (daily) ==="
    & python scripts\pinnacle-capture-history.py --capture-mode daily 2>&1 | ForEach-Object { Log $_ }
    if ($LASTEXITCODE -ne 0) {
        Log "WARNING: Pinnacle history append failed (exit $LASTEXITCODE), continuing..."
    }

    Log "=== Step 3/6: Strict policy report (--append --compare-overlay) ==="
    & python scripts\strict-policy-report.py --append --compare-overlay 2>&1 | ForEach-Object { Log $_ }
    if ($LASTEXITCODE -ne 0) {
        Log "ERROR: strict-policy-report failed (exit $LASTEXITCODE)"
        exit 1
    }

    if ($null -ne $volumeCfg) {
        Log "=== Step 4/6: $($volumeCfg.Label) shadow (signal-profile=$($volumeCfg.Profile)) ==="
        & python scripts\strict-policy-report.py --append --signal-profile $volumeCfg.Profile --output "data\backtest\strict-signals-$($volumeCfg.Tag).csv" --internal-output "data\backtest\strict-signals-$($volumeCfg.Tag)-internal.csv" 2>&1 | ForEach-Object { Log $_ }
        if ($LASTEXITCODE -ne 0) {
            Log "WARNING: $($volumeCfg.Profile) shadow append failed (exit $LASTEXITCODE), continuing..."
        }
    } else {
        Log "=== Step 4/6: Volume shadow skipped (STRICT_POLICY_VOLUME_MODE=$volumeMode) ==="
    }

    Log "=== Step 5/6: Spread shadow + Clay 2026 shadow ==="
    & python scripts\strict-policy-report.py --append --signal-profile spread_shadow --output "data\backtest\strict-signals-spreadshadow.csv" 2>&1 | ForEach-Object { Log $_ }
    if ($LASTEXITCODE -ne 0) {
        Log "WARNING: spread_shadow append failed (exit $LASTEXITCODE), continuing..."
    }
    & python scripts\strict-policy-report.py --append --signal-profile clay_calibrated --output "data\backtest\strict-signals-claycal.csv" --internal-output "data\backtest\strict-signals-claycal-internal.csv" 2>&1 | ForEach-Object { Log $_ }
    if ($LASTEXITCODE -ne 0) {
        Log "WARNING: clay_calibrated append failed (exit $LASTEXITCODE), continuing..."
    }

    Log "=== Step 6/6: Nightly-style tennis settlement/performance ==="
    & powershell -ExecutionPolicy Bypass -NoProfile -File scripts\oncourt-settle-nightly.ps1 2>&1 | ForEach-Object { Log $_ }
    if ($LASTEXITCODE -ne 0) {
        Log "WARNING: nightly tennis settlement failed (exit $LASTEXITCODE), continuing..."
    }

    Log "============================================"
    Log "  AM Tennis Refresh finished at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    Log "============================================"
}
finally {
    Exit-TaskLock $lockHandle
}
