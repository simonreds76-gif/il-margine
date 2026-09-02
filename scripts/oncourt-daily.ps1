# Il Margine - Daily Scheduled Task (runs nightly at 22:30)
# Fast nightly path: extract -> current schedule sync -> odds/props/signals -> settlement.
# Slow model-prior refreshes (extended stats, CPI and spread refits) run weekly.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root
. (Join-Path $root "scripts\use-local-python.ps1") -RepoRoot $root
. (Join-Path $root "scripts\task-lock.ps1")
. (Join-Path $root "scripts\_lib\run_status.ps1")

$dataDir = Join-Path $root "data"
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$logFile = Join-Path $dataDir "oncourt-daily.log"

# Nightly pricing only needs current players/tours/schedule in Supabase.
# Fresh local games/stat CSVs remain available to settlement; the Sunday
# weekly task owns historical uploads and slow player-profile rebuilds.
$syncArgs = @("--quick")
$syncLabel = ($syncArgs -join " ")
# Enable trimmed shadow profile by default for scheduled runs (override with env if needed)
if ([string]::IsNullOrWhiteSpace($env:STRICT_POLICY_VOLUME_MODE)) { $env:STRICT_POLICY_VOLUME_MODE = "volume_200" }
$volumeMode = "$env:STRICT_POLICY_VOLUME_MODE".ToLower()
if ([string]::IsNullOrWhiteSpace($volumeMode)) { $volumeMode = "off" }
if ([string]::IsNullOrWhiteSpace($env:STRICT_SPREAD_V1_SHADOW_ENABLED)) { $env:STRICT_SPREAD_V1_SHADOW_ENABLED = "1" }
if ([string]::IsNullOrWhiteSpace($env:CHALLENGER_ML_ENABLE)) { $env:CHALLENGER_ML_ENABLE = "1" }
if ([string]::IsNullOrWhiteSpace($env:STRICT_SPREAD_V1_CLAY_FAV_ENABLED)) { $env:STRICT_SPREAD_V1_CLAY_FAV_ENABLED = "0" }
if ([string]::IsNullOrWhiteSpace($env:STRICT_CLAY_BO3_ENABLED)) { $env:STRICT_CLAY_BO3_ENABLED = "1" }
if ([string]::IsNullOrWhiteSpace($env:STRICT_GRASS_BO3_ENABLED)) { $env:STRICT_GRASS_BO3_ENABLED = "1" }
if ([string]::IsNullOrWhiteSpace($env:STRICT_CPI_SPEED_SHADOW_ENABLED)) { $env:STRICT_CPI_SPEED_SHADOW_ENABLED = "1" }
if ([string]::IsNullOrWhiteSpace($env:CLAY_BO3_ML_ENABLE)) { $env:CLAY_BO3_ML_ENABLE = "0" }
if ([string]::IsNullOrWhiteSpace($env:STRICT_POLICY_HARD_CALIBRATION_MODE)) { $env:STRICT_POLICY_HARD_CALIBRATION_MODE = "off" }
if ([string]::IsNullOrWhiteSpace($env:STRICT_HARD_CALIBRATION_LIVE)) { $env:STRICT_HARD_CALIBRATION_LIVE = "0" }
if ([string]::IsNullOrWhiteSpace($env:STRICT_HARD_CALIBRATION_PROFILES)) { $env:STRICT_HARD_CALIBRATION_PROFILES = "strict" }
# Scheduled runs are hard-safe: clay spread-v1 can only be enabled by a manual research run.
$env:SPREAD_V1_ENABLE_CLAY = "0"
$dailyOddsTimeoutSeconds = 1200
$shadowLaneTimeoutSeconds = 300
if (-not [string]::IsNullOrWhiteSpace($env:TENNIS_DAILY_ODDS_TOTAL_TIMEOUT_SECONDS)) {
    $parsedDailyOddsTimeout = 0
    if ([int]::TryParse($env:TENNIS_DAILY_ODDS_TOTAL_TIMEOUT_SECONDS, [ref]$parsedDailyOddsTimeout) -and $parsedDailyOddsTimeout -gt 0) {
        $dailyOddsTimeoutSeconds = $parsedDailyOddsTimeout
    }
}

function Test-EnvFlag([string]$value) {
    if ([string]::IsNullOrWhiteSpace($value)) { return $false }
    return @("1", "true", "yes", "on") -contains $value.Trim().ToLower()
}

$spreadV1ShadowEnabled = Test-EnvFlag $env:STRICT_SPREAD_V1_SHADOW_ENABLED
$challengerMlEnabled = Test-EnvFlag $env:CHALLENGER_ML_ENABLE
$clayFavEnabled = Test-EnvFlag $env:STRICT_SPREAD_V1_CLAY_FAV_ENABLED
$clayBo3Enabled = Test-EnvFlag $env:STRICT_CLAY_BO3_ENABLED
$grassBo3Enabled = Test-EnvFlag $env:STRICT_GRASS_BO3_ENABLED
$cpiSpeedShadowEnabled = Test-EnvFlag $env:STRICT_CPI_SPEED_SHADOW_ENABLED

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
    $script:LastProcessOutputLines = @()
    try {
        $proc = Start-Process -FilePath $FilePath -ArgumentList $ArgumentList -NoNewWindow -PassThru -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath
        # Windows PowerShell only preserves ExitCode reliably if the process handle is opened.
        $null = $proc.Handle
        $timedOut = $false
        if ($TimeoutSeconds -gt 0) {
            if (-not $proc.WaitForExit($TimeoutSeconds * 1000)) {
                $timedOut = $true
                try {
                    # Stop the complete Python process tree so timed-out child stages
                    # cannot keep writing artifacts while the nightly run continues.
                    Start-Process -FilePath "taskkill.exe" -ArgumentList @("/PID", "$($proc.Id)", "/T", "/F") -WindowStyle Hidden -Wait | Out-Null
                } catch {
                    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
                }
                $proc.WaitForExit(10000) | Out-Null
                Log "WARNING: $Label timed out after ${TimeoutSeconds}s and was stopped."
            }
        } else {
            $proc.WaitForExit()
        }
        $proc.Refresh()

        if (Test-Path $stdoutPath) {
            $stdoutLines = @(Get-Content $stdoutPath)
            $script:LastProcessOutputLines += $stdoutLines
            $stdoutLines | ForEach-Object { Log $_ }
        }
        if (Test-Path $stderrPath) {
            $stderrLines = @(Get-Content $stderrPath)
            $script:LastProcessOutputLines += $stderrLines
            $stderrLines | ForEach-Object { Log $_ }
        }
        if ($timedOut) {
            return 124
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

function Invoke-LoggedProcessWithRetry {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$ArgumentList,
        [Parameter(Mandatory = $true)][string]$Label,
        [int]$TimeoutSeconds = 0,
        [int]$Attempts = 1
    )

    $maxAttempts = [Math]::Max(1, $Attempts)
    for ($attempt = 1; $attempt -le $maxAttempts; $attempt++) {
        if ($maxAttempts -gt 1) {
            Log "$Label attempt $attempt/$maxAttempts"
        }
        $exitCode = Invoke-LoggedProcess -FilePath $FilePath -ArgumentList $ArgumentList -Label $Label -TimeoutSeconds $TimeoutSeconds
        if ($exitCode -eq 0 -or $attempt -eq $maxAttempts) {
            return $exitCode
        }
        Start-Sleep -Seconds ([Math]::Min(30, 5 * $attempt))
    }

    return 1
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

$runStatus = Start-RunStatus -Pipeline "oncourt-daily" -Trigger "schedule"
$runStatusFinal = "failed"
$runStatusErrorRecord = $null
$runStatusErrorType = $null
$runStatusErrorMessage = $null

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
        Log "ERROR: OnCourt extract failed (exit $LASTEXITCODE)"
        exit 1
    }
} else {
    Log "ERROR: 32-bit Python not found at $py32"
    exit 1
}

# Step 2: Sync to Supabase
Log "=== Step 2/10: Supabase sync ($syncLabel) ==="
& python scripts\oncourt-load-supabase.py @syncArgs 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "ERROR: Supabase sync failed (exit $LASTEXITCODE)"
    Set-RunStatusFailure "SupabaseSyncFailed" "Supabase sync failed (exit $LASTEXITCODE)"
    exit 1
}

# Extended 12m/36m profiles are slow-moving model priors. Rebuilding them here
# added up to 15 minutes and frequently timed out; Sunday weekly owns the job.
Log "=== Step 3/10: Extended player stats skipped (weekly refresh) ==="

# Step 4: Refresh TennisExplorer injured/returning CSV
Log "=== Step 4/10: Refresh injured players list (TennisExplorer) ==="
$injuredExit = Invoke-LoggedProcess -FilePath "python" -ArgumentList @("scripts\scrape-tennisexplorer-injured.py", "--max-pages", "2") -Label "injured players scrape"
if ($injuredExit -ne 0) {
    Log "WARNING: injured players scrape failed (exit $injuredExit), continuing..."
}

# Tournament CPI is refreshed by the Sunday weekly model task. Daily pricing
# consumes the last verified table instead of spending several minutes on the
# same two season pages every night.
Log "=== Step 5/10: CPI surface-speed refresh skipped (weekly refresh) ==="

# Step 6: Pinnacle odds + fair odds
Log "=== Step 6/10: Pinnacle odds + fair odds ==="
$step6Exit = Invoke-LoggedProcessWithRetry -FilePath "python" -ArgumentList @("scripts\run-daily-odds.py", "--skip-strict-report") -Label "Pinnacle/fair-odds" -TimeoutSeconds $dailyOddsTimeoutSeconds -Attempts 1
$step6Lines = @($script:LastProcessOutputLines | ForEach-Object { "$_" })
if ($step6Exit -ne 0) {
    Log "ERROR: Pinnacle/fair-odds failed (exit $step6Exit)"
    Set-RunStatusFailure "DailyOddsFailed" "Pinnacle/fair-odds failed (exit $step6Exit)"
    exit 1
}

$step6Synced = $step6Lines | Select-String -SimpleMatch "Synced daily_fair_odds:"
if (-not $step6Synced) {
    Log "ERROR: Pinnacle/fair-odds completed without confirming daily_fair_odds sync"
    Set-RunStatusFailure "DailyOddsSyncMissing" "Pinnacle/fair-odds completed without confirming daily_fair_odds sync"
    exit 1
}

Log "=== Step 6b/10: Append Pinnacle history capture (daily) ==="
& python scripts\pinnacle-capture-history.py --capture-mode daily 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: Pinnacle history append failed (exit $LASTEXITCODE), continuing..."
}

Log "=== Step 6c/10: Tennis count-markets research board ==="
$tennisPropsExit = Invoke-LoggedProcessWithRetry -FilePath "python" -ArgumentList @("scripts\run-tennis-props-daily.py", "--days-ahead", "3", "--max-events", "128") -Label "tennis count-markets board" -TimeoutSeconds 900 -Attempts 1
if ($tennisPropsExit -ne 0) {
    Log "ERROR: tennis count-markets board failed/timed out (exit $tennisPropsExit); continuing remaining diagnostics"
    Set-RunStatusFailure "TennisPropsFailed" "tennis count-markets board failed/timed out (exit $tennisPropsExit)"
}

# Step 7: Strict policy report + overlay comparison (auto-append CSVs)
Log "=== Step 7/10: Strict policy report (--append --compare-overlay) ==="
& python scripts\strict-policy-report.py --append --compare-overlay 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "ERROR: strict-policy-report failed (exit $LASTEXITCODE)"
    Set-RunStatusFailure "StrictPolicyReportFailed" "strict-policy-report failed (exit $LASTEXITCODE)"
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
    $prevSpreadV1CorrectionOnly = $env:SPREAD_V1_ENABLE_CORRECTION_ONLY
    $env:SPREAD_V1_ENABLE_CORRECTION_ONLY = "1"
    try {
        & python scripts\strict-policy-report.py --append --signal-profile spread_v1_shadow --output "data\backtest\strict-signals-spreadv1-live.csv" 2>&1 | ForEach-Object { Log $_ }
        if ($LASTEXITCODE -ne 0) {
            Log "WARNING: spread_v1_shadow append failed (exit $LASTEXITCODE), continuing..."
        }
    }
    finally {
        if ($null -eq $prevSpreadV1CorrectionOnly) {
            Remove-Item Env:\SPREAD_V1_ENABLE_CORRECTION_ONLY -ErrorAction SilentlyContinue
        } else {
            $env:SPREAD_V1_ENABLE_CORRECTION_ONLY = $prevSpreadV1CorrectionOnly
        }
    }
} else {
    Log "=== Step 8b/10: Spread v1 shadow skipped (STRICT_SPREAD_V1_SHADOW_ENABLED=0) ==="
}

Log "=== Step 8c/10: Clay calibrated legacy lane removed after failed ROI audit ==="

if ($challengerMlEnabled) {
    Log "=== Step 8d/10: Challenger ML v2 prospective evidence (10-15% edge, HIGH coverage, zero stake) ==="
    & python scripts\strict-policy-report.py --append --signal-profile challenger_ml_shadow --output "data\backtest\strict-signals-challenger-ml-v2-live.csv" 2>&1 | ForEach-Object { Log $_ }
    if ($LASTEXITCODE -ne 0) {
        Log "WARNING: challenger_ml_shadow append failed (exit $LASTEXITCODE), continuing..."
    }
} else {
    Log "=== Step 8d/10: Challenger ML shadow skipped (CHALLENGER_ML_ENABLE=0) ==="
}

if ($clayFavEnabled) {
    Log "=== Step 8e/10: Spread v1 clay-favourite shadow (calibration-gated) ==="
    & python scripts\strict-policy-report.py --append --signal-profile spread_v1_clay_fav --output "data\backtest\strict-signals-clay-fav-live.csv" 2>&1 | ForEach-Object { Log $_ }
    if ($LASTEXITCODE -ne 0) {
        Log "WARNING: spread_v1_clay_fav append failed (exit $LASTEXITCODE), continuing..."
    }
} else {
    Log "=== Step 8e/10: Spread v1 clay-favourite shadow skipped (STRICT_SPREAD_V1_CLAY_FAV_ENABLED=0) ==="
}

if ($grassBo3Enabled) {
    Log "=== Step 8f/10: Grass bo3 internal shadow (ATP grass warm-up ML 10-30%, favourite agreement) ==="
    $prevInternalResearchLanes = $env:INTERNAL_RESEARCH_LANES
    $env:INTERNAL_RESEARCH_LANES = "1"
    try {
        $grassExit = Invoke-LoggedProcess -FilePath "python" -ArgumentList @("scripts\strict-policy-report.py", "--append", "--signal-profile", "grass_bo3", "--output", "data\backtest\strict-signals-grass_bo3-live.csv") -Label "grass_bo3 append" -TimeoutSeconds $shadowLaneTimeoutSeconds
        if ($grassExit -ne 0) {
            Log "WARNING: grass_bo3 append failed (exit $grassExit), continuing..."
        }
    }
    finally {
        if ($null -eq $prevInternalResearchLanes) {
            Remove-Item Env:\INTERNAL_RESEARCH_LANES -ErrorAction SilentlyContinue
        } else {
            $env:INTERNAL_RESEARCH_LANES = $prevInternalResearchLanes
        }
    }
} else {
    Log "=== Step 8f/10: Grass bo3 shadow skipped (STRICT_GRASS_BO3_ENABLED=0) ==="
}

if ($clayBo3Enabled) {
    Log "=== Step 8g/10: Clay bo3 internal shadow (ML 5-13%, dog HC 6-25%) ==="
    $prevInternalResearchLanes = $env:INTERNAL_RESEARCH_LANES
    $env:INTERNAL_RESEARCH_LANES = "1"
    try {
        $clayExit = Invoke-LoggedProcess -FilePath "python" -ArgumentList @("scripts\strict-policy-report.py", "--append", "--signal-profile", "clay_bo3", "--output", "data\backtest\strict-signals-clay_bo3-live.csv") -Label "clay_bo3 append" -TimeoutSeconds $shadowLaneTimeoutSeconds
        if ($clayExit -ne 0) {
            Log "WARNING: clay_bo3 append failed (exit $clayExit), continuing..."
        }
    }
    finally {
        if ($null -eq $prevInternalResearchLanes) {
            Remove-Item Env:\INTERNAL_RESEARCH_LANES -ErrorAction SilentlyContinue
        } else {
            $env:INTERNAL_RESEARCH_LANES = $prevInternalResearchLanes
        }
    }
} else {
    Log "=== Step 8g/10: Clay bo3 shadow skipped (STRICT_CLAY_BO3_ENABLED=0) ==="
}

if ($cpiSpeedShadowEnabled) {
    Log "=== Step 8h/10: CPI speed-regime internal shadow (ATP ML, passed CPI gates, 10-30% edge) ==="
    $prevInternalResearchLanes = $env:INTERNAL_RESEARCH_LANES
    $env:INTERNAL_RESEARCH_LANES = "1"
    try {
        $cpiExit = Invoke-LoggedProcess -FilePath "python" -ArgumentList @("scripts\strict-policy-report.py", "--append", "--signal-profile", "cpi_speed_shadow", "--output", "data\backtest\strict-signals-cpi_speed-live.csv") -Label "cpi_speed_shadow append" -TimeoutSeconds $shadowLaneTimeoutSeconds
        if ($cpiExit -ne 0) {
            Log "WARNING: cpi_speed_shadow append failed (exit $cpiExit), continuing..."
        }
    }
    finally {
        if ($null -eq $prevInternalResearchLanes) {
            Remove-Item Env:\INTERNAL_RESEARCH_LANES -ErrorAction SilentlyContinue
        } else {
            $env:INTERNAL_RESEARCH_LANES = $prevInternalResearchLanes
        }
    }
} else {
    Log "=== Step 8h/10: CPI speed-regime shadow skipped (STRICT_CPI_SPEED_SHADOW_ENABLED=0) ==="
}

# Step 9: Settle/report immediately after nightly append so results are ready by the next morning.
Log "=== Step 9/10: Nightly tennis settlement/performance ==="
& powershell -ExecutionPolicy Bypass -NoProfile -File scripts\oncourt-settle-nightly.ps1 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: nightly tennis settlement failed (exit $LASTEXITCODE), continuing..."
}

Log "=== Step 9b/10: Compact tennis evidence snapshot ==="
$evidenceSnapshotExit = Invoke-LoggedProcessWithRetry -FilePath "python" -ArgumentList @("scripts\tennis-evidence-snapshot.py", "--supabase") -Label "tennis evidence snapshot" -TimeoutSeconds 120 -Attempts 1
if ($evidenceSnapshotExit -ne 0) {
    Log "WARNING: tennis evidence snapshot failed/timed out (exit $evidenceSnapshotExit), continuing..."
}

Log "=== Post-step: Spread calibration/refit skipped (weekly refresh) ==="

Log "============================================"
Log "  Daily Pipeline finished at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Log "============================================"
    if ([string]::IsNullOrWhiteSpace($runStatusErrorType)) {
        $runStatusFinal = "ok"
        $runStatusErrorMessage = $null
    }
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

if ($runStatusFinal -ne "ok") { exit 1 }
