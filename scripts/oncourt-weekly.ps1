# Il Margine - Weekly Scheduled Task (runs Sunday 03:00)
# Full refresh + weekly model feature refresh + strict signals analysis + settlement + performance

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root
. (Join-Path $root "scripts\use-local-python.ps1") -RepoRoot $root
. (Join-Path $root "scripts\task-lock.ps1")
. (Join-Path $root "scripts\_lib\run_status.ps1")

$dataDir = Join-Path $root "data"
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$logFile = Join-Path $dataDir "oncourt-weekly.log"
# Enable trimmed shadow profile by default for scheduled runs (override with env if needed)
if ([string]::IsNullOrWhiteSpace($env:STRICT_POLICY_VOLUME_MODE)) { $env:STRICT_POLICY_VOLUME_MODE = "volume_200" }
$volumeMode = "$env:STRICT_POLICY_VOLUME_MODE".ToLower()
if ([string]::IsNullOrWhiteSpace($volumeMode)) { $volumeMode = "off" }
# Scheduled runs are hard-safe: clay spread-v1 can only be enabled by a manual research run.
$env:SPREAD_V1_ENABLE_CLAY = "0"
$spreadFitFiles = @(
    "data/backtest/backtest-results-2025.csv",
    "data/backtest/backtest-results-2026.csv"
)
$claySpreadFitFiles = @(
    "data/backtest/backtest-results-2022.csv",
    "data/backtest/backtest-results-2023.csv",
    "data/backtest/backtest-results-2024.csv",
    "data/backtest/backtest-results-2025.csv"
)
$externalFetchTimeoutSeconds = 300
$spreadRefreshTimeoutSeconds = 240

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

function Invoke-LoggedProcess {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$ArgumentList,
        [Parameter(Mandatory = $true)][string]$Label,
        [int]$TimeoutSeconds = 0
    )

    $stdoutPath = Join-Path $env:TEMP ("ilmargine-" + [guid]::NewGuid().ToString() + ".out.log")
    $stderrPath = Join-Path $env:TEMP ("ilmargine-" + [guid]::NewGuid().ToString() + ".err.log")
    try {
        $proc = Start-Process -FilePath $FilePath -ArgumentList $ArgumentList -NoNewWindow -PassThru -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath
        # Windows PowerShell only preserves ExitCode reliably if the process handle is opened.
        $null = $proc.Handle
        if ($TimeoutSeconds -gt 0) {
            try {
                Wait-Process -Id $proc.Id -Timeout $TimeoutSeconds -ErrorAction Stop
            } catch {
                Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
                Log "WARNING: $Label timed out after ${TimeoutSeconds}s and was stopped."
                return 124
            }
        } else {
            Wait-Process -Id $proc.Id
        }

        if (Test-Path $stdoutPath) {
            Get-Content $stdoutPath | ForEach-Object { Log $_ }
        }
        if (Test-Path $stderrPath) {
            Get-Content $stderrPath | ForEach-Object { Log $_ }
        }
        if ($null -eq $proc.ExitCode) {
            Log "WARNING: $Label exit code was unavailable; treating as failure."
            return 1
        }
        return $proc.ExitCode
    } finally {
        Remove-Item -LiteralPath $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue
    }
}

function Set-RunStatusFailure([string]$Type, [string]$Message) {
    $script:runStatusFinal = "failed"
    $script:runStatusErrorType = $Type
    $script:runStatusErrorMessage = $Message
}

$lockHandle = Enter-TaskLock -LockName "tennis-automation" -RootPath $root -WaitSeconds 1800 -PollSeconds 10
if ($null -eq $lockHandle) {
    Log "Another tennis automation run stayed active for 30 minutes; exiting."
    exit 0
}

$runStatus = Start-RunStatus -Pipeline "oncourt-weekly" -Trigger "schedule"
$runStatusFinal = "failed"
$runStatusErrorRecord = $null
$runStatusErrorType = $null
$runStatusErrorMessage = $null

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
        Log "ERROR: OnCourt extract failed (exit $LASTEXITCODE)"
        exit 1
    }
} else {
    Log "ERROR: 32-bit Python not found at $py32"
    exit 1
}

# Step 2: FULL sync to Supabase
Log "=== Step 2/13: Supabase FULL sync ==="
& python scripts\oncourt-load-supabase.py 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "ERROR: Supabase full sync failed (exit $LASTEXITCODE)"
    Set-RunStatusFailure "SupabaseSyncFailed" "Supabase full sync failed (exit $LASTEXITCODE)"
    exit 1
}

# Step 3: Extended player stats (writes v2 plus backwards-compatible table)
Log "=== Step 3/12: Compute extended player stats ==="
& python scripts\oncourt-compute-player-stats-extended.py 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "ERROR: Extended player stats failed (exit $LASTEXITCODE)"
    exit 1
}

# Step 4: Refresh Sackmann ATP source files
Log "=== Step 4/12: Refresh Sackmann ATP source files ==="
& python scripts\sackmann-refresh-data.py --start-year 2023 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: Sackmann refresh failed (exit $LASTEXITCODE), continuing..."
}

Log "=== Post-step: Refresh match-total aces/DF holdout gate ==="
& python scripts\backtest-tennis-player-props.py --start-year 2022 --end-year 2026 --eval-years 2022 2023 2024 2025 --out-csv data\tennis-props\backtest\aces-dfs-totals-source-rows.csv --out-txt data\tennis-props\backtest\aces-dfs-totals-source-report.txt 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: tennis props totals source refresh failed (exit $LASTEXITCODE), keeping the last verified gate."
}
else {
    & python scripts\backtest-tennis-props-totals.py 2>&1 | ForEach-Object { Log $_ }
    if ($LASTEXITCODE -ne 0) {
        Log "WARNING: tennis props totals Stage-0 failed (exit $LASTEXITCODE), keeping the last verified gate."
    }
    & python scripts\backtest-tennis-props-service-points.py --source data\tennis-props\backtest\aces-dfs-totals-source-rows.csv 2>&1 | ForEach-Object { Log $_ }
    if ($LASTEXITCODE -ne 0) {
        Log "WARNING: tennis props service-point experiment failed (exit $LASTEXITCODE), keeping the last verified gate."
    }
    & python scripts\backtest-tennis-props-opponent-return.py --source data\tennis-props\backtest\aces-dfs-totals-source-rows.csv 2>&1 | ForEach-Object { Log $_ }
    if ($LASTEXITCODE -ne 0) {
        Log "WARNING: tennis props opponent-return experiment failed (exit $LASTEXITCODE), keeping the last verified gate."
    }
    & python scripts\backtest-tennis-props-rate-recency.py --source data\tennis-props\backtest\aces-dfs-totals-source-rows.csv 2>&1 | ForEach-Object { Log $_ }
    if ($LASTEXITCODE -ne 0) {
        Log "WARNING: tennis props rate-recency experiment failed (exit $LASTEXITCODE), keeping the last verified gate."
    }

    Log "=== Post-step: Refresh all-tour tennis props v3 challenger ==="
    & python scripts\build-tennis-props-v3-dataset.py --start-year 2022 --end-year 2026 --output-start-year 2023 2>&1 | ForEach-Object { Log $_ }
    if ($LASTEXITCODE -ne 0) {
        Log "WARNING: tennis props v3 dataset refresh failed (exit $LASTEXITCODE), keeping the last verified gate."
    }
    else {
        & python scripts\fit-tennis-props-v3.py 2>&1 | ForEach-Object { Log $_ }
        if ($LASTEXITCODE -ne 0) {
            Log "WARNING: tennis props v3 challenger fit failed (exit $LASTEXITCODE), keeping the last verified gate."
        }
    }
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
$tennisDataExit = Invoke-LoggedProcess -FilePath "python" -ArgumentList @("scripts\fetch-tennis-data-atp.py", "--year", "2026") -Label "tennis-data ATP refresh" -TimeoutSeconds $externalFetchTimeoutSeconds
if ($tennisDataExit -ne 0) {
    Log "WARNING: tennis-data ATP refresh failed (exit $tennisDataExit), continuing..."
}

# Step 11: Weekly strict-signals analysis
Log "=== Step 11/12: Analyse strict signals ==="
& python scripts\analyse-strict-signals.py --days 7 --input data\backtest\strict-signals-archive.csv 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: strict-signals analysis failed (exit $LASTEXITCODE), continuing..."
}

Log "=== Step 11b/12: Clay calibrated legacy analysis removed after failed ROI audit ==="

Log "=== Step 11c/12: Analyse clay bo3 shadow signals ==="
& python scripts\analyse-strict-signals.py --days 7 --input data\backtest\strict-signals-clay_bo3-archive.csv --report-txt data\backtest\strict-signals-clay_bo3-weekly.txt --summary-csv data\backtest\strict-signals-clay_bo3-weekly.csv 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: clay bo3 signal analysis failed (exit $LASTEXITCODE), continuing..."
}

Log "=== Step 11d/12: Replay historical extreme model/market gaps ==="
& python scripts\backtest-tennis-model-market-gap.py 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: extreme gap historical replay failed (exit $LASTEXITCODE), continuing..."
}

Log "=== Step 11e/12: Snapshot extreme model/market gap evidence ==="
& python scripts\tennis-model-market-gap-report.py --weekly-snapshot-csv data\backtest\tennis-model-market-gap-weekly.csv 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: extreme gap weekly review failed (exit $LASTEXITCODE), continuing..."
}

Log "=== Step 11f/12: Audit fair-odds guard evidence and overlap ==="
& python scripts\tennis-guard-audit.py 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: tennis guard audit failed (exit $LASTEXITCODE), keeping the previous report."
}

# Step 12: Append Pinnacle history capture (weekly checkpoint)
Log "=== Step 12/12: Append Pinnacle history capture (weekly) ==="
& python scripts\pinnacle-capture-history.py --capture-mode weekly 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: Pinnacle history append failed (exit $LASTEXITCODE), continuing..."
}

Log "=== Post-step: Refresh spread_v1 calibration + correction model ==="
$handicapArgs = @("scripts\handicap-calibration.py", "--line-source", "auto", "--files") + $spreadFitFiles
$handicapExit = Invoke-LoggedProcess -FilePath "python" -ArgumentList $handicapArgs -Label "handicap calibration refresh" -TimeoutSeconds $spreadRefreshTimeoutSeconds
if ($handicapExit -ne 0) {
    Log "WARNING: handicap calibration refresh failed (exit $handicapExit), continuing..."
}
$spreadFitArgs = @("scripts\fit-spread-v1-model.py", "--files") + $spreadFitFiles
$spreadFitExit = Invoke-LoggedProcess -FilePath "python" -ArgumentList $spreadFitArgs -Label "spread_v1 correction fit" -TimeoutSeconds $spreadRefreshTimeoutSeconds
if ($spreadFitExit -ne 0) {
    Log "WARNING: spread_v1 correction fit failed (exit $spreadFitExit), continuing..."
}

Log "=== Post-step: Clay-only spread_v1 calibration + gated correction fit ==="
$clayCalPath = "data\backtest\spread-v1-clay-calibration-params.json"
$clayCaliArgs = @("scripts\handicap-calibration.py", "--surface-filter", "clay", "--line-source", "snapshot", "--files") + $claySpreadFitFiles
$clayCaliExit = Invoke-LoggedProcess -FilePath "python" -ArgumentList $clayCaliArgs -Label "clay-only base calibration" -TimeoutSeconds $spreadRefreshTimeoutSeconds
if ($clayCaliExit -ne 0) {
    Log "WARNING: clay-only calibration failed (exit $clayCaliExit), continuing..."
}

$clayBaseValid = $false
if (Test-Path $clayCalPath) {
    try {
        $clayPayload = Get-Content -Raw -Path $clayCalPath | ConvertFrom-Json
        $clayBaseValid = ($clayPayload.calibration_valid -eq $true)
    }
    catch {
        Log "WARNING: could not parse $clayCalPath, skipping clay-only correction fit."
    }
}
if ($clayBaseValid) {
    $clayFitArgs = @("scripts\fit-spread-v1-model.py", "--surface-filter", "clay", "--files") + $claySpreadFitFiles
    $clayFitExit = Invoke-LoggedProcess -FilePath "python" -ArgumentList $clayFitArgs -Label "clay-only correction fit" -TimeoutSeconds $spreadRefreshTimeoutSeconds
    if ($clayFitExit -ne 0) {
        Log "WARNING: clay-only correction fit failed (exit $clayFitExit), continuing..."
    }
}
else {
    Log "Clay-only correction fit skipped: base calibration is not valid yet."
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

Log "=== Post-step: Spread v1 shadow CLV audit ==="
& python scripts\audit-strict-clv.py --signals data\backtest\strict-signals-spreadv1-archive.csv --bet-type spread --detail-csv data\backtest\strict-clv-audit-spreadv1-2026.csv --summary-txt data\backtest\strict-clv-audit-spreadv1-2026.txt 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: spread v1 shadow CLV audit failed (exit $LASTEXITCODE), continuing..."
}

Log "=== Post-step: Challenger ML v2 verified-close CLV audit ==="
& python scripts\audit-strict-clv.py --signals data\backtest\strict-signals-challenger-ml-v2-archive.csv --detail-csv data\backtest\strict-clv-audit-challenger-ml-v2-2026.csv --summary-txt data\backtest\strict-clv-audit-challenger-ml-v2-2026.txt --require-verified-kickoff --max-close-lag-minutes 720 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: Challenger ML CLV audit failed (exit $LASTEXITCODE), continuing..."
}

Log "=== Post-step: Canonical ATP/Challenger real-price market scoring ==="
& python scripts\score-tennis-spread-history.py --start-date 2026-03-01 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: canonical tennis real-price scoring failed (exit $LASTEXITCODE), continuing..."
}

Log "=== Post-step: Clay-fav spread CLV audit ==="
& python scripts\audit-strict-clv.py --signals data\backtest\strict-signals-clay-fav-archive.csv --bet-type spread --detail-csv data\backtest\strict-clv-audit-clay-fav-2026.csv --summary-txt data\backtest\strict-clv-audit-clay-fav-2026.txt 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: clay-fav spread CLV audit failed (exit $LASTEXITCODE), continuing..."
}

Log "=== Post-step: Clay bo3 ML CLV audit ==="
& python scripts\audit-strict-clv.py --signals data\backtest\strict-signals-clay_bo3-archive.csv --detail-csv data\backtest\strict-clv-audit-clay_bo3-2026.csv --summary-txt data\backtest\strict-clv-audit-clay_bo3-2026.txt 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: clay bo3 ML CLV audit failed (exit $LASTEXITCODE), continuing..."
}

Log "=== Post-step: Clay bo3 dog-HC CLV audit ==="
& python scripts\audit-strict-clv.py --signals data\backtest\strict-signals-clay_bo3-archive.csv --bet-type spread --detail-csv data\backtest\strict-clv-audit-clay_bo3-spread-2026.csv --summary-txt data\backtest\strict-clv-audit-clay_bo3-spread-2026.txt 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: clay bo3 dog-HC CLV audit failed (exit $LASTEXITCODE), continuing..."
}

Log "=== Post-step: Grass bo3 ML CLV audit ==="
& python scripts\audit-strict-clv.py --signals data\backtest\strict-signals-grass_bo3-archive.csv --detail-csv data\backtest\strict-clv-audit-grass_bo3-2026.csv --summary-txt data\backtest\strict-clv-audit-grass_bo3-2026.txt --unmatched-csv data\backtest\strict-clv-audit-grass_bo3-2026-unmatched.csv 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: grass bo3 ML CLV audit failed (exit $LASTEXITCODE), continuing..."
}

Log "=== Post-step: CPI speed shadow ML CLV audit ==="
& python scripts\audit-strict-clv.py --signals data\backtest\strict-signals-cpi_speed-archive.csv --detail-csv data\backtest\strict-clv-audit-cpi_speed-2026.csv --summary-txt data\backtest\strict-clv-audit-cpi_speed-2026.txt --unmatched-csv data\backtest\strict-clv-audit-cpi_speed-2026-unmatched.csv 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: CPI speed shadow ML CLV audit failed (exit $LASTEXITCODE), continuing..."
}

Log "=== Post-step: Spread v1 shadow report ==="
$prevSpreadV1CorrectionOnly = $env:SPREAD_V1_ENABLE_CORRECTION_ONLY
$env:SPREAD_V1_ENABLE_CORRECTION_ONLY = "1"
try {
    & python scripts\spread-v1-report.py 2>&1 | ForEach-Object { Log $_ }
    if ($LASTEXITCODE -ne 0) {
        Log "WARNING: spread v1 shadow report failed (exit $LASTEXITCODE), continuing..."
    }
}
finally {
    if ($null -eq $prevSpreadV1CorrectionOnly) {
        Remove-Item Env:\SPREAD_V1_ENABLE_CORRECTION_ONLY -ErrorAction SilentlyContinue
    } else {
        $env:SPREAD_V1_ENABLE_CORRECTION_ONLY = $prevSpreadV1CorrectionOnly
    }
}

Log "=== Post-step: Tennis props v3 weekly evidence report ==="
if (Test-Path "scripts\tennis-props-v3-weekly-report.py") {
    # The consolidated tennis report below owns Telegram delivery.
    $v3WeeklyReportExit = Invoke-LoggedProcess -FilePath "python" -ArgumentList @("scripts\tennis-props-v3-weekly-report.py", "--no-telegram") -Label "tennis props v3 weekly report" -TimeoutSeconds 90
    if ($v3WeeklyReportExit -ne 0) {
        Log "ERROR: tennis props v3 weekly report failed (exit $v3WeeklyReportExit)"
        Set-RunStatusFailure "TennisPropsV3WeeklyReportFailed" "tennis props v3 weekly report failed (exit $v3WeeklyReportExit)"
    }
}
else {
    Log "Tennis props v3 report script is not installed in this checkout; canonical aces/DF evidence still reports below."
}

Log "=== Post-step: Send weekly tennis evidence to Telegram ==="
$tennisTelegramExit = Invoke-LoggedProcess -FilePath "python" -ArgumentList @("scripts\weekly-research-report.py", "--tennis-only-telegram") -Label "weekly tennis Telegram report" -TimeoutSeconds 90
if ($tennisTelegramExit -ne 0) {
    Log "WARNING: weekly tennis Telegram report failed (exit $tennisTelegramExit), continuing..."
}

Log "============================================"
Log "  Weekly Full Load finished at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Log "============================================"
    $runStatusFinal = "ok"
    $runStatusErrorType = $null
    $runStatusErrorMessage = $null
}
catch {
    $runStatusErrorRecord = $_
    Set-RunStatusFailure "UnhandledException" $_.Exception.Message
    throw
}
finally {
    Complete-RunStatus -Run $runStatus -Status $runStatusFinal -ErrorRecord $runStatusErrorRecord -ErrorType $runStatusErrorType -ErrorMessage $runStatusErrorMessage
    Exit-TaskLock $lockHandle
}

