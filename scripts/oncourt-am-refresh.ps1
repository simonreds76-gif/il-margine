# Il Margine - AM Tennis Refresh
# Lighter daytime refresh: refresh today's OnCourt schedule/tours, then odds/fair-odds/shadow append.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root
. (Join-Path $root "scripts\use-local-python.ps1") -RepoRoot $root
. (Join-Path $root "scripts\task-lock.ps1")
. (Join-Path $root "scripts\_lib\run_status.ps1")

$dataDir = Join-Path $root "data"
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$logFile = Join-Path $dataDir "oncourt-am-refresh.log"

if ([string]::IsNullOrWhiteSpace($env:STRICT_POLICY_VOLUME_MODE)) { $env:STRICT_POLICY_VOLUME_MODE = "volume_200" }
$volumeMode = "$env:STRICT_POLICY_VOLUME_MODE".ToLower()
if ([string]::IsNullOrWhiteSpace($volumeMode)) { $volumeMode = "off" }
if ([string]::IsNullOrWhiteSpace($env:STRICT_SPREAD_V1_SHADOW_ENABLED)) { $env:STRICT_SPREAD_V1_SHADOW_ENABLED = "1" }
if ([string]::IsNullOrWhiteSpace($env:CHALLENGER_ML_ENABLE)) { $env:CHALLENGER_ML_ENABLE = "0" }
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
                Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
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

function Set-RunStatusFailure([string]$Type, [string]$Message) {
    $script:runStatusFinal = "failed"
    $script:runStatusErrorType = $Type
    $script:runStatusErrorMessage = $Message
}

$lockHandle = Enter-TaskLock -LockName "tennis-automation" -RootPath $root -WaitSeconds 900 -PollSeconds 10
if ($null -eq $lockHandle) {
    Log "Another tennis automation run stayed active for 15 minutes; exiting."
    exit 0
}

$runStatus = Start-RunStatus -Pipeline "oncourt-am-refresh" -Trigger "schedule"
$runStatusFinal = "failed"
$runStatusErrorRecord = $null
$runStatusErrorType = $null
$runStatusErrorMessage = $null

try {
    Log "============================================"
    Log "  AM Tennis Refresh started at $timestamp"
    Log "============================================"

    Log "=== Step 1/8: OnCourt extract (fresh today/tours CSVs) ==="
    $py32 = "C:\Python312-32\python.exe"
    if (Test-Path $py32) {
        & $py32 scripts\oncourt-extract-all.py 2>&1 | ForEach-Object { Log $_ }
        if ($LASTEXITCODE -ne 0) {
            Log "WARNING: OnCourt extract had errors (exit $LASTEXITCODE), continuing..."
        }
    } else {
        Log "WARNING: 32-bit Python not found at $py32, skipping extract"
    }

    Log "=== Step 2/8: Supabase sync (--quick, includes players) ==="
    & python scripts\oncourt-load-supabase.py --quick 2>&1 | ForEach-Object { Log $_ }
    if ($LASTEXITCODE -ne 0) {
        Log "ERROR: Supabase sync failed (exit $LASTEXITCODE)"
        Set-RunStatusFailure "SupabaseSyncFailed" "Supabase sync failed (exit $LASTEXITCODE)"
        exit 1
    }

    Log "=== Step 3/8: Pinnacle odds + fair odds ==="
    $step3Exit = Invoke-LoggedProcess -FilePath "python" -ArgumentList @("scripts\run-daily-odds.py", "--skip-strict-report") -Label "Pinnacle/fair-odds" -TimeoutSeconds $dailyOddsTimeoutSeconds
    $step3Lines = @($script:LastProcessOutputLines | ForEach-Object { "$_" })
    if ($step3Exit -ne 0) {
        Log "ERROR: Pinnacle/fair-odds failed (exit $step3Exit)"
        Set-RunStatusFailure "DailyOddsFailed" "Pinnacle/fair-odds failed (exit $step3Exit)"
        exit 1
    }
    $step3Synced = $step3Lines | Select-String -SimpleMatch "Synced daily_fair_odds:"
    if (-not $step3Synced) {
        Log "ERROR: Pinnacle/fair-odds completed without confirming daily_fair_odds sync"
        Set-RunStatusFailure "DailyOddsSyncMissing" "Pinnacle/fair-odds completed without confirming daily_fair_odds sync"
        exit 1
    }

    Log "=== Step 3b/8: Tennis props projection board ==="
    # Historical OnCourt scans can slow down while the morning fair-odds job is
    # still releasing memory. Allow enough time to finish instead of retaining
    # yesterday's board after a false timeout.
    $tennisPropsBoardExit = Invoke-LoggedProcess -FilePath "python" -ArgumentList @("scripts\build-tennis-props-board.py", "--as-of", (Get-Date -Format "yyyy-MM-dd")) -Label "tennis props projection board" -TimeoutSeconds 600
    if ($tennisPropsBoardExit -ne 0) {
        Log "WARNING: tennis props projection board failed/timed out (exit $tennisPropsBoardExit), continuing..."
    }

    Log "=== Step 4/8: Append Pinnacle history capture (daily) ==="
    & python scripts\pinnacle-capture-history.py --capture-mode daily 2>&1 | ForEach-Object { Log $_ }
    if ($LASTEXITCODE -ne 0) {
        Log "WARNING: Pinnacle history append failed (exit $LASTEXITCODE), continuing..."
    }

    Log "=== Step 5/8: Strict policy report (--append --compare-overlay) ==="
    & python scripts\strict-policy-report.py --append --compare-overlay 2>&1 | ForEach-Object { Log $_ }
    if ($LASTEXITCODE -ne 0) {
        Log "ERROR: strict-policy-report failed (exit $LASTEXITCODE)"
        Set-RunStatusFailure "StrictPolicyReportFailed" "strict-policy-report failed (exit $LASTEXITCODE)"
        exit 1
    }

    if ($null -ne $volumeCfg) {
        Log "=== Step 6/8: $($volumeCfg.Label) shadow (signal-profile=$($volumeCfg.Profile)) ==="
        & python scripts\strict-policy-report.py --append --signal-profile $volumeCfg.Profile --output "data\backtest\strict-signals-$($volumeCfg.Tag)-live.csv" --internal-output "data\backtest\strict-signals-$($volumeCfg.Tag)-internal-live.csv" 2>&1 | ForEach-Object { Log $_ }
        if ($LASTEXITCODE -ne 0) {
            Log "WARNING: $($volumeCfg.Profile) shadow append failed (exit $LASTEXITCODE), continuing..."
        }
    } else {
        Log "=== Step 6/8: Volume shadow skipped (STRICT_POLICY_VOLUME_MODE=$volumeMode) ==="
    }

    Log "=== Step 7/8: Research shadow lanes ==="
    if ($spreadV1ShadowEnabled) {
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
        Log "Spread v1 shadow skipped (STRICT_SPREAD_V1_SHADOW_ENABLED=0)."
    }
    Log "Clay calibrated legacy lane removed after failed ROI audit."
    if ($challengerMlEnabled) {
        Log "Challenger ML internal shadow (10-15% edge, HIGH coverage)."
        & python scripts\strict-policy-report.py --append --signal-profile challenger_ml_shadow --output "data\backtest\strict-signals-challenger-ml-live.csv" 2>&1 | ForEach-Object { Log $_ }
        if ($LASTEXITCODE -ne 0) {
            Log "WARNING: challenger_ml_shadow append failed (exit $LASTEXITCODE), continuing..."
        }
    } else {
        Log "Challenger ML shadow skipped (CHALLENGER_ML_ENABLE=0)."
    }
    if ($clayFavEnabled) {
        Log "Spread v1 clay-favourite shadow (calibration-gated)."
        & python scripts\strict-policy-report.py --append --signal-profile spread_v1_clay_fav --output "data\backtest\strict-signals-clay-fav-live.csv" 2>&1 | ForEach-Object { Log $_ }
        if ($LASTEXITCODE -ne 0) {
            Log "WARNING: spread_v1_clay_fav append failed (exit $LASTEXITCODE), continuing..."
        }
    } else {
        Log "Spread v1 clay-favourite shadow skipped (STRICT_SPREAD_V1_CLAY_FAV_ENABLED=0)."
    }
    # Run grass before clay so a clay shadow stall cannot leave the active grass board stale.
    if ($grassBo3Enabled) {
        Log "Grass bo3 internal shadow (ATP grass warm-up ML 10-30%, favourite agreement)."
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
        Log "Grass bo3 shadow skipped (STRICT_GRASS_BO3_ENABLED=0)."
    }

    if ($clayBo3Enabled) {
        Log "Clay bo3 internal shadow (ML 5-13%, dog HC 6-25%)."
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
        Log "Clay bo3 shadow skipped (STRICT_CLAY_BO3_ENABLED=0)."
    }

    if ($cpiSpeedShadowEnabled) {
        Log "CPI speed-regime internal shadow (ATP ML, passed CPI gates, 10-30% edge)."
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
        Log "CPI speed-regime shadow skipped (STRICT_CPI_SPEED_SHADOW_ENABLED=0)."
    }

    Log "=== Step 8/8: Settlement/performance skipped in AM task ==="
    Log "Nightly tennis settlement/performance is handled by oncourt-daily.ps1 at 22:30 to keep AM refresh fast."

    Log "=== Post-step: spread_v1 refresh skipped in AM task (nightly/weekly only) ==="

    Log "=== Post-step: Daily tennis Telegram digest ==="
    $digestExit = Invoke-LoggedProcess -FilePath "python" -ArgumentList @("scripts\tennis-daily-signal-digest.py") -Label "daily tennis Telegram digest" -TimeoutSeconds 90
    if ($digestExit -ne 0) {
        Log "WARNING: daily tennis Telegram digest failed/timed out (exit $digestExit); signal generation remains valid."
    }

    Log "============================================"
    Log "  AM Tennis Refresh finished at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
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

