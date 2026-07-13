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

Log "=== Step 1/13: Settle strict signals (production CSV) ==="
& python scripts\settle-strict-signals.py --csv data\backtest\strict-signals-archive.csv 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: strict-signals settlement failed (exit $LASTEXITCODE), continuing..."
}

Log "=== Step 2/13: Settle strict signals (internal 5% CSV) ==="
& python scripts\settle-strict-signals.py --csv data\backtest\strict-signals-internal-5pct-archive.csv 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: strict-signals-internal-5pct settlement failed (exit $LASTEXITCODE), continuing..."
}

Log "=== Step 3/13: Settle strict signals (overlay compare CSV) ==="
& python scripts\settle-strict-signals.py --csv data\backtest\strict-signals-overlay-compare.csv 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: strict-signals overlay-compare settlement failed (exit $LASTEXITCODE), continuing..."
}

if ($null -ne $volumeCfg) {
    Log "=== Step 4/13: Settle $($volumeCfg.Label) shadow CSV ==="
    & python scripts\settle-strict-signals.py --csv "data\backtest\strict-signals-$($volumeCfg.Tag)-archive.csv" 2>&1 | ForEach-Object { Log $_ }
    if ($LASTEXITCODE -ne 0) {
        Log "WARNING: strict-signals-$($volumeCfg.Tag) settlement failed (exit $LASTEXITCODE), continuing..."
    }
} else {
    Log "=== Step 4/13: Volume settlement skipped (STRICT_POLICY_VOLUME_MODE=$volumeMode) ==="
}

Log "=== Step 5/13: Settle spread v1 shadow CSV ==="
& python scripts\settle-strict-signals.py --csv data\backtest\strict-signals-spreadv1-archive.csv 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: strict-signals-spreadv1 settlement failed (exit $LASTEXITCODE), continuing..."
}

Log "=== Step 6/13: Settle legacy spread shadow CSV ==="
& python scripts\settle-strict-signals.py --csv data\backtest\strict-signals-spreadshadow-archive.csv 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: strict-signals-spreadshadow settlement failed (exit $LASTEXITCODE), continuing..."
}

Log "=== Step 7/13: Clay calibrated legacy settlement removed after failed ROI audit ==="

Log "=== Step 7b/13: Settle Challenger ML v2 prospective evidence CSV ==="
& python scripts\settle-strict-signals.py --csv data\backtest\strict-signals-challenger-ml-v2-archive.csv 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: challenger_ml settlement failed (exit $LASTEXITCODE), continuing..."
}

Log "=== Step 7c/13: Settle clay-fav CSV ==="
& python scripts\settle-strict-signals.py --csv data\backtest\strict-signals-clay-fav-archive.csv 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: clay-fav settlement failed (exit $LASTEXITCODE), continuing..."
}

Log "=== Step 7d/13: Settle clay bo3 CSV ==="
& python scripts\settle-strict-signals.py --csv data\backtest\strict-signals-clay_bo3-archive.csv 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: clay_bo3 settlement failed (exit $LASTEXITCODE), continuing..."
}

Log "=== Step 7e/13: Settle grass bo3 CSV ==="
& python scripts\settle-strict-signals.py --csv data\backtest\strict-signals-grass_bo3-archive.csv 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: grass_bo3 settlement failed (exit $LASTEXITCODE), continuing..."
}

Log "=== Step 7f/13: Settle CPI speed shadow CSV ==="
$cpiSpeedArchivePath = "data\backtest\strict-signals-cpi_speed-archive.csv"
$cpiSpeedLegacyPath = "data\backtest\strict-signals-cpi_speed.csv"
if (-not (Test-Path $cpiSpeedArchivePath) -and (Test-Path $cpiSpeedLegacyPath)) {
    Copy-Item -Path $cpiSpeedLegacyPath -Destination $cpiSpeedArchivePath
    Log "Seeded CPI speed archive from legacy mirror for first settlement run."
}
& python scripts\settle-strict-signals.py --csv $cpiSpeedArchivePath 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: cpi_speed_shadow settlement failed (exit $LASTEXITCODE), continuing..."
}

Log "=== Step 8/13: Strict policy settled performance ==="
& python scripts\strict-policy-performance.py --days 7 --signals data\backtest\strict-signals-archive.csv 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: strict-policy-performance failed (exit $LASTEXITCODE), continuing..."
}

if ($null -ne $volumeCfg) {
    Log "=== Step 9/13: $($volumeCfg.Label) settled performance ==="
    & python scripts\strict-policy-performance.py --days 7 --signals "data\backtest\strict-signals-$($volumeCfg.Tag)-archive.csv" --compare "data\backtest\strict-signals-$($volumeCfg.Tag)-compare.csv" --report-txt "data\backtest\strict-policy-performance-$($volumeCfg.Tag)-weekly.txt" --summary-csv "data\backtest\strict-policy-performance-$($volumeCfg.Tag)-weekly.csv" 2>&1 | ForEach-Object { Log $_ }
    if ($LASTEXITCODE -ne 0) {
        Log "WARNING: strict-policy-performance $($volumeCfg.Profile) failed (exit $LASTEXITCODE), continuing..."
    }
} else {
    Log "=== Step 9/13: Volume performance skipped (STRICT_POLICY_VOLUME_MODE=$volumeMode) ==="
}

Log "=== Step 10/13: Spread v1 shadow settled performance ==="
& python scripts\strict-policy-performance.py --days 7 --signals data\backtest\strict-signals-spreadv1-archive.csv --compare data\backtest\strict-signals-spreadv1-compare.csv --report-txt data\backtest\strict-policy-performance-spreadv1-weekly.txt --summary-csv data\backtest\strict-policy-performance-spreadv1-weekly.csv 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: strict-policy-performance spread_v1_shadow failed (exit $LASTEXITCODE), continuing..."
}

Log "=== Step 11/13: Legacy spread shadow settled performance ==="
& python scripts\strict-policy-performance.py --days 7 --signals data\backtest\strict-signals-spreadshadow-archive.csv --compare data\backtest\strict-signals-spreadshadow-compare.csv --report-txt data\backtest\strict-policy-performance-spreadshadow-weekly.txt --summary-csv data\backtest\strict-policy-performance-spreadshadow-weekly.csv 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: strict-policy-performance spread_shadow failed (exit $LASTEXITCODE), continuing..."
}

Log "=== Step 12/13: Clay calibrated legacy performance removed after failed ROI audit ==="

Log "=== Step 12b/13: Challenger ML v2 prospective performance ==="
& python scripts\strict-policy-performance.py --days 7 --signals data\backtest\strict-signals-challenger-ml-v2-archive.csv --report-txt data\backtest\strict-policy-performance-challenger-ml-v2-weekly.txt --summary-csv data\backtest\strict-policy-performance-challenger-ml-v2-weekly.csv 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: strict-policy-performance challenger_ml_shadow failed (exit $LASTEXITCODE), continuing..."
}

Log "=== Step 12c/13: Clay-fav settled performance ==="
& python scripts\strict-policy-performance.py --days 7 --signals data\backtest\strict-signals-clay-fav-archive.csv --report-txt data\backtest\strict-policy-performance-clay-fav-weekly.txt --summary-csv data\backtest\strict-policy-performance-clay-fav-weekly.csv 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: strict-policy-performance spread_v1_clay_fav failed (exit $LASTEXITCODE), continuing..."
}

Log "=== Step 12d/13: Clay bo3 settled performance ==="
& python scripts\strict-policy-performance.py --days 7 --signals data\backtest\strict-signals-clay_bo3-archive.csv --report-txt data\backtest\strict-policy-performance-clay_bo3-weekly.txt --summary-csv data\backtest\strict-policy-performance-clay_bo3-weekly.csv 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: strict-policy-performance clay_bo3 failed (exit $LASTEXITCODE), continuing..."
}

Log "=== Step 12e/13: Grass bo3 settled performance ==="
& python scripts\strict-policy-performance.py --days 7 --signals data\backtest\strict-signals-grass_bo3-archive.csv --report-txt data\backtest\strict-policy-performance-grass_bo3-weekly.txt --summary-csv data\backtest\strict-policy-performance-grass_bo3-weekly.csv 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: strict-policy-performance grass_bo3 failed (exit $LASTEXITCODE), continuing..."
}

Log "=== Step 13/13: CPI speed shadow settled performance ==="
& python scripts\strict-policy-performance.py --days 7 --signals data\backtest\strict-signals-cpi_speed-archive.csv --report-txt data\backtest\strict-policy-performance-cpi_speed-weekly.txt --summary-csv data\backtest\strict-policy-performance-cpi_speed-weekly.csv 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: strict-policy-performance cpi_speed_shadow failed (exit $LASTEXITCODE), continuing..."
}

Log "=== Post-step: Tennis shadow proof report ==="
& python scripts\tennis-shadow-proof-report.py 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: tennis-shadow-proof-report failed (exit $LASTEXITCODE), continuing..."
}

Log "=== Post-step: Settle extreme model/market gap hypotheses ==="
& python scripts\settle-strict-signals.py --csv data\backtest\tennis-model-market-gap-archive.csv --no-backup 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: extreme-gap hypothesis settlement failed (exit $LASTEXITCODE), continuing..."
}

Log "=== Post-step: Extreme-gap ML closing-line audit ==="
& python scripts\audit-strict-clv.py --signals data\backtest\tennis-model-market-gap-archive.csv --bet-type match --detail-csv data\backtest\tennis-model-market-gap-clv-ml.csv --summary-txt data\backtest\tennis-model-market-gap-clv-ml.txt --unmatched-csv data\backtest\tennis-model-market-gap-clv-ml-unmatched.csv 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: extreme-gap ML CLV audit failed (exit $LASTEXITCODE), continuing..."
}

Log "=== Post-step: Extreme-gap spread closing-line audit ==="
& python scripts\audit-strict-clv.py --signals data\backtest\tennis-model-market-gap-archive.csv --bet-type spread --detail-csv data\backtest\tennis-model-market-gap-clv-spread.csv --summary-txt data\backtest\tennis-model-market-gap-clv-spread.txt --unmatched-csv data\backtest\tennis-model-market-gap-clv-spread-unmatched.csv 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: extreme-gap spread CLV audit failed (exit $LASTEXITCODE), continuing..."
}

Log "=== Post-step: Extreme model/market gap report ==="
& python scripts\tennis-model-market-gap-report.py 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: extreme-gap report failed (exit $LASTEXITCODE), continuing..."
}

Log "============================================"
Log "  Nightly tennis settlement finished at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Log "============================================"
