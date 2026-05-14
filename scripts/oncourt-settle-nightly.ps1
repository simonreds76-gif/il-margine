# Il Margine - Nightly Tennis Settlement (runs daily after matches)
# Settles strict + shadow lanes and refreshes performance summaries.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root
. (Join-Path $root "scripts\use-local-python.ps1") -RepoRoot $root

$dataDir = Join-Path $root "data"
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$logFile = Join-Path $dataDir "oncourt-settle-nightly.log"

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

Log "============================================"
Log "  Nightly tennis settlement started at $timestamp"
Log "============================================"

Log "=== Step 1/10: Settle strict signals (production CSV) ==="
& python scripts\settle-strict-signals.py --csv data\backtest\strict-signals-archive.csv 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: strict-signals settlement failed (exit $LASTEXITCODE), continuing..."
}

Log "=== Step 2/10: Settle strict signals (internal 5% CSV) ==="
& python scripts\settle-strict-signals.py --csv data\backtest\strict-signals-internal-5pct-archive.csv 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: strict-signals-internal-5pct settlement failed (exit $LASTEXITCODE), continuing..."
}

Log "=== Step 3/10: Settle strict signals (overlay compare CSV) ==="
& python scripts\settle-strict-signals.py --csv data\backtest\strict-signals-overlay-compare.csv 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: strict-signals overlay-compare settlement failed (exit $LASTEXITCODE), continuing..."
}

if ($null -ne $volumeCfg) {
    Log "=== Step 4/10: Settle $($volumeCfg.Label) shadow CSV ==="
    & python scripts\settle-strict-signals.py --csv "data\backtest\strict-signals-$($volumeCfg.Tag)-archive.csv" 2>&1 | ForEach-Object { Log $_ }
    if ($LASTEXITCODE -ne 0) {
        Log "WARNING: strict-signals-$($volumeCfg.Tag) settlement failed (exit $LASTEXITCODE), continuing..."
    }
} else {
    Log "=== Step 4/10: Volume settlement skipped (STRICT_POLICY_VOLUME_MODE=$volumeMode) ==="
}

Log "=== Step 5/12: Settle spread v1 shadow CSV ==="
& python scripts\settle-strict-signals.py --csv data\backtest\strict-signals-spreadv1-archive.csv 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: strict-signals-spreadv1 settlement failed (exit $LASTEXITCODE), continuing..."
}

Log "=== Step 6/12: Settle legacy spread shadow CSV ==="
& python scripts\settle-strict-signals.py --csv data\backtest\strict-signals-spreadshadow-archive.csv 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: strict-signals-spreadshadow settlement failed (exit $LASTEXITCODE), continuing..."
}

Log "=== Step 7/12: Settle Clay 2026 shadow CSV ==="
& python scripts\settle-strict-signals.py --csv data\backtest\strict-signals-claycal-archive.csv 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: strict-signals-claycal settlement failed (exit $LASTEXITCODE), continuing..."
}

Log "=== Step 7b/12: Settle Challenger ML CSV ==="
& python scripts\settle-strict-signals.py --csv data\backtest\strict-signals-challenger-ml-archive.csv 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: challenger_ml settlement failed (exit $LASTEXITCODE), continuing..."
}

Log "=== Step 7c/12: Settle clay-fav CSV ==="
& python scripts\settle-strict-signals.py --csv data\backtest\strict-signals-clay-fav-archive.csv 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: clay-fav settlement failed (exit $LASTEXITCODE), continuing..."
}

Log "=== Step 7d/12: Settle clay bo3 CSV ==="
& python scripts\settle-strict-signals.py --csv data\backtest\strict-signals-clay_bo3-archive.csv 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: clay_bo3 settlement failed (exit $LASTEXITCODE), continuing..."
}

Log "=== Step 8/12: Strict policy settled performance ==="
& python scripts\strict-policy-performance.py --days 7 --signals data\backtest\strict-signals-archive.csv 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: strict-policy-performance failed (exit $LASTEXITCODE), continuing..."
}

if ($null -ne $volumeCfg) {
    Log "=== Step 9/12: $($volumeCfg.Label) settled performance ==="
    & python scripts\strict-policy-performance.py --days 7 --signals "data\backtest\strict-signals-$($volumeCfg.Tag)-archive.csv" --compare "data\backtest\strict-signals-$($volumeCfg.Tag)-compare.csv" --report-txt "data\backtest\strict-policy-performance-$($volumeCfg.Tag)-weekly.txt" --summary-csv "data\backtest\strict-policy-performance-$($volumeCfg.Tag)-weekly.csv" 2>&1 | ForEach-Object { Log $_ }
    if ($LASTEXITCODE -ne 0) {
        Log "WARNING: strict-policy-performance $($volumeCfg.Profile) failed (exit $LASTEXITCODE), continuing..."
    }
} else {
    Log "=== Step 9/12: Volume performance skipped (STRICT_POLICY_VOLUME_MODE=$volumeMode) ==="
}

Log "=== Step 10/12: Spread v1 shadow settled performance ==="
& python scripts\strict-policy-performance.py --days 7 --signals data\backtest\strict-signals-spreadv1-archive.csv --compare data\backtest\strict-signals-spreadv1-compare.csv --report-txt data\backtest\strict-policy-performance-spreadv1-weekly.txt --summary-csv data\backtest\strict-policy-performance-spreadv1-weekly.csv 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: strict-policy-performance spread_v1_shadow failed (exit $LASTEXITCODE), continuing..."
}

Log "=== Step 11/12: Legacy spread shadow settled performance ==="
& python scripts\strict-policy-performance.py --days 7 --signals data\backtest\strict-signals-spreadshadow-archive.csv --compare data\backtest\strict-signals-spreadshadow-compare.csv --report-txt data\backtest\strict-policy-performance-spreadshadow-weekly.txt --summary-csv data\backtest\strict-policy-performance-spreadshadow-weekly.csv 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: strict-policy-performance spread_shadow failed (exit $LASTEXITCODE), continuing..."
}

Log "=== Step 12/12: Clay 2026 settled performance ==="
& python scripts\strict-policy-performance.py --days 7 --signals data\backtest\strict-signals-claycal-archive.csv --compare data\backtest\strict-signals-claycal-compare.csv --report-txt data\backtest\strict-policy-performance-clay2026-weekly.txt --summary-csv data\backtest\strict-policy-performance-clay2026-weekly.csv 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: strict-policy-performance clay_calibrated failed (exit $LASTEXITCODE), continuing..."
}

Log "=== Step 12b/12: Challenger ML settled performance ==="
& python scripts\strict-policy-performance.py --days 7 --signals data\backtest\strict-signals-challenger-ml-archive.csv --report-txt data\backtest\strict-policy-performance-challenger-ml-weekly.txt --summary-csv data\backtest\strict-policy-performance-challenger-ml-weekly.csv 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: strict-policy-performance challenger_ml_shadow failed (exit $LASTEXITCODE), continuing..."
}

Log "=== Step 12c/12: Clay-fav settled performance ==="
& python scripts\strict-policy-performance.py --days 7 --signals data\backtest\strict-signals-clay-fav-archive.csv --report-txt data\backtest\strict-policy-performance-clay-fav-weekly.txt --summary-csv data\backtest\strict-policy-performance-clay-fav-weekly.csv 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: strict-policy-performance spread_v1_clay_fav failed (exit $LASTEXITCODE), continuing..."
}

Log "=== Step 12d/12: Clay bo3 settled performance ==="
& python scripts\strict-policy-performance.py --days 7 --signals data\backtest\strict-signals-clay_bo3-archive.csv --report-txt data\backtest\strict-policy-performance-clay_bo3-weekly.txt --summary-csv data\backtest\strict-policy-performance-clay_bo3-weekly.csv 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: strict-policy-performance clay_bo3 failed (exit $LASTEXITCODE), continuing..."
}

Log "============================================"
Log "  Nightly tennis settlement finished at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Log "============================================"
