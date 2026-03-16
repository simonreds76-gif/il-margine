# Il Margine - Nightly Tennis Settlement (runs daily after matches)
# Settles strict + shadow lanes and refreshes performance summaries.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

$dataDir = Join-Path $root "data"
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$logFile = Join-Path $dataDir "oncourt-settle-nightly.log"

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
Log "  Nightly tennis settlement started at $timestamp"
Log "============================================"

Log "=== Step 1/8: Settle strict signals (production CSV) ==="
& python scripts\settle-strict-signals.py 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: strict-signals settlement failed (exit $LASTEXITCODE), continuing..."
}

Log "=== Step 2/8: Settle strict signals (internal 5% CSV) ==="
& python scripts\settle-strict-signals.py --csv data\backtest\strict-signals-internal-5pct.csv 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: strict-signals-internal-5pct settlement failed (exit $LASTEXITCODE), continuing..."
}

Log "=== Step 3/8: Settle strict signals (overlay compare CSV) ==="
& python scripts\settle-strict-signals.py --csv data\backtest\strict-signals-overlay-compare.csv 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: strict-signals overlay-compare settlement failed (exit $LASTEXITCODE), continuing..."
}

if ($null -ne $volumeCfg) {
    Log "=== Step 4/8: Settle $($volumeCfg.Label) shadow CSV ==="
    & python scripts\settle-strict-signals.py --csv "data\backtest\strict-signals-$($volumeCfg.Tag).csv" 2>&1 | ForEach-Object { Log $_ }
    if ($LASTEXITCODE -ne 0) {
        Log "WARNING: strict-signals-$($volumeCfg.Tag) settlement failed (exit $LASTEXITCODE), continuing..."
    }
} else {
    Log "=== Step 4/8: Volume settlement skipped (STRICT_POLICY_VOLUME_MODE=$volumeMode) ==="
}

Log "=== Step 5/8: Settle spread shadow CSV ==="
& python scripts\settle-strict-signals.py --csv data\backtest\strict-signals-spreadshadow.csv 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: strict-signals-spreadshadow settlement failed (exit $LASTEXITCODE), continuing..."
}

Log "=== Step 6/8: Strict policy settled performance ==="
& python scripts\strict-policy-performance.py --days 7 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: strict-policy-performance failed (exit $LASTEXITCODE), continuing..."
}

if ($null -ne $volumeCfg) {
    Log "=== Step 7/8: $($volumeCfg.Label) settled performance ==="
    & python scripts\strict-policy-performance.py --days 7 --signals "data\backtest\strict-signals-$($volumeCfg.Tag).csv" --compare "data\backtest\strict-signals-$($volumeCfg.Tag)-compare.csv" --report-txt "data\backtest\strict-policy-performance-$($volumeCfg.Tag)-weekly.txt" --summary-csv "data\backtest\strict-policy-performance-$($volumeCfg.Tag)-weekly.csv" 2>&1 | ForEach-Object { Log $_ }
    if ($LASTEXITCODE -ne 0) {
        Log "WARNING: strict-policy-performance $($volumeCfg.Profile) failed (exit $LASTEXITCODE), continuing..."
    }
} else {
    Log "=== Step 7/8: Volume performance skipped (STRICT_POLICY_VOLUME_MODE=$volumeMode) ==="
}

Log "=== Step 8/8: Spread shadow settled performance ==="
& python scripts\strict-policy-performance.py --days 7 --signals data\backtest\strict-signals-spreadshadow.csv --compare data\backtest\strict-signals-spreadshadow-compare.csv --report-txt data\backtest\strict-policy-performance-spreadshadow-weekly.txt --summary-csv data\backtest\strict-policy-performance-spreadshadow-weekly.csv 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: strict-policy-performance spread_shadow failed (exit $LASTEXITCODE), continuing..."
}

Log "============================================"
Log "  Nightly tennis settlement finished at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Log "============================================"
