param([switch]$CoreOnly, [switch]$NoTelegram, [switch]$OnDemand)

# Il Margine - AM Tennis Refresh
# Lighter daytime refresh: refresh today's OnCourt schedule/tours, then odds/fair-odds/shadow append.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root
. (Join-Path $root "scripts\use-local-python.ps1") -RepoRoot $root
. (Join-Path $root "scripts\tennis-priority.ps1")
. (Join-Path $root "scripts\_lib\run_status.ps1")

$dataDir = Join-Path $root "data"
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$logFile = Join-Path $dataDir $(if ($OnDemand) { "tennis-on-demand.log" } else { "oncourt-am-refresh.log" })
$manualRequest = if ($OnDemand) { Get-TennisPriorityRequest $root } else { $null }
if ($OnDemand -and $null -eq $manualRequest) { throw "No valid on-demand request; refusing an untracked run." }
Write-TennisManualProgress $root $manualRequest "waiting_for_lock" "Waiting for the current shared-file operation to finish; historical reports yield between steps."

if ([string]::IsNullOrWhiteSpace($env:STRICT_POLICY_VOLUME_MODE)) { $env:STRICT_POLICY_VOLUME_MODE = "volume_200" }
$volumeMode = "$env:STRICT_POLICY_VOLUME_MODE".ToLower()
if ([string]::IsNullOrWhiteSpace($volumeMode)) { $volumeMode = "off" }
if ([string]::IsNullOrWhiteSpace($env:STRICT_SPREAD_V1_SHADOW_ENABLED)) { $env:STRICT_SPREAD_V1_SHADOW_ENABLED = "1" }
if ([string]::IsNullOrWhiteSpace($env:CHALLENGER_ML_ENABLE)) { $env:CHALLENGER_ML_ENABLE = "1" }
if ([string]::IsNullOrWhiteSpace($env:STRICT_SPREAD_V1_CLAY_FAV_ENABLED)) { $env:STRICT_SPREAD_V1_CLAY_FAV_ENABLED = "0" }
if ([string]::IsNullOrWhiteSpace($env:STRICT_CLAY_BO3_ENABLED)) { $env:STRICT_CLAY_BO3_ENABLED = "1" }
if ([string]::IsNullOrWhiteSpace($env:STRICT_GRASS_BO3_ENABLED)) { $env:STRICT_GRASS_BO3_ENABLED = "1" }
if ([string]::IsNullOrWhiteSpace($env:STRICT_CPI_SPEED_SHADOW_ENABLED)) { $env:STRICT_CPI_SPEED_SHADOW_ENABLED = "0" }
if ([string]::IsNullOrWhiteSpace($env:CLAY_BO3_ML_ENABLE)) { $env:CLAY_BO3_ML_ENABLE = "0" }
if ([string]::IsNullOrWhiteSpace($env:STRICT_POLICY_HARD_CALIBRATION_MODE)) { $env:STRICT_POLICY_HARD_CALIBRATION_MODE = "off" }
if ([string]::IsNullOrWhiteSpace($env:STRICT_HARD_CALIBRATION_LIVE)) { $env:STRICT_HARD_CALIBRATION_LIVE = "0" }
if ([string]::IsNullOrWhiteSpace($env:STRICT_HARD_CALIBRATION_PROFILES)) { $env:STRICT_HARD_CALIBRATION_PROFILES = "strict" }
# Scheduled runs are hard-safe: clay spread-v1 can only be enabled by a manual research run.
$env:SPREAD_V1_ENABLE_CLAY = "0"
$dailyOddsTimeoutSeconds = 1200
$supabaseSyncTimeoutSeconds = 600
$strictReportTimeoutSeconds = 600
$shadowLaneTimeoutSeconds = 300
if (-not [string]::IsNullOrWhiteSpace($env:TENNIS_DAILY_ODDS_TOTAL_TIMEOUT_SECONDS)) {
    $parsedDailyOddsTimeout = 0
    if ([int]::TryParse($env:TENNIS_DAILY_ODDS_TOTAL_TIMEOUT_SECONDS, [ref]$parsedDailyOddsTimeout) -and $parsedDailyOddsTimeout -gt 0) {
        $dailyOddsTimeoutSeconds = $parsedDailyOddsTimeout
    }
}
if (-not [string]::IsNullOrWhiteSpace($env:TENNIS_SUPABASE_SYNC_TIMEOUT_SECONDS)) {
    $parsedSupabaseSyncTimeout = 0
    if ([int]::TryParse($env:TENNIS_SUPABASE_SYNC_TIMEOUT_SECONDS, [ref]$parsedSupabaseSyncTimeout) -and $parsedSupabaseSyncTimeout -gt 0) {
        $supabaseSyncTimeoutSeconds = $parsedSupabaseSyncTimeout
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
    if ($TimeoutSeconds -le 0) { $TimeoutSeconds = 1800 }
    $runtimeLabel = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($Label))
    $runtimeScript = [IO.Path]::GetFileName($ArgumentList[0])
    $runtimeToken = & python scripts/tennis_runtime_health.py begin --label64 $runtimeLabel --script $runtimeScript --timeout $TimeoutSeconds
    if ($LASTEXITCODE -ne 0) { throw "Could not record start of $Label" }
    $runtimeExit = 1
    try {
        $proc = Start-Process -FilePath $FilePath -ArgumentList $ArgumentList -NoNewWindow -PassThru -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath
        # Windows PowerShell only preserves ExitCode reliably if the process handle is opened.
        $null = $proc.Handle
        $timedOut = $false
        if ($TimeoutSeconds -gt 0) {
            if (-not $proc.WaitForExit($TimeoutSeconds * 1000)) {
                $timedOut = $true
                try {
                    # Kill the complete Python process tree. The venv launcher can
                    # otherwise leave a child running after the wrapper times out.
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
            $runtimeExit = 124
            return 124
        }
        if ($null -eq $proc.ExitCode) {
            Log "WARNING: $Label exit code was unavailable; treating as failure."
            return 1
        }
        $runtimeExit = $proc.ExitCode
        return $proc.ExitCode
    } finally {
        & python scripts/tennis_runtime_health.py finish --token $runtimeToken --exit-code $runtimeExit | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Could not record completion of $Label" }
        Remove-Item -LiteralPath $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue
    }
}

function Set-RunStatusFailure([string]$Type, [string]$Message) {
    $script:runStatusFinal = "failed"
    $script:runStatusErrorType = $Type
    $script:runStatusErrorMessage = $Message
}

$lockHandle = Enter-TennisPriorityLock -RootPath $root -Priority:$OnDemand
if ($null -eq $lockHandle) {
    Log "Another tennis automation run stayed active for 15 minutes; exiting."
    exit 0
}

$runStatus = Start-RunStatus -Pipeline "oncourt-am-refresh" -Trigger $(if ($OnDemand) { "manual" } else { "schedule" })
$refreshStartedAt = (Get-Date).ToUniversalTime().ToString("o")
$refreshId = [guid]::NewGuid().ToString()
$refreshDate = [datetime]::UtcNow.ToString("yyyy-MM-dd")
$env:TENNIS_REFRESH_STARTED_AT = $refreshStartedAt
$env:TENNIS_RUNTIME_RUN_ID = [guid]::NewGuid().ToString()
$runStatusFinal = "failed"
$runStatusErrorRecord = $null
$runStatusErrorType = $null
$runStatusErrorMessage = $null
$privateSnapshotAttempted = $false

try {
    $sourceDatabase = Get-Item -LiteralPath "C:\Program Files (x86)\OnCourt\OnCourt.mdb" -ErrorAction Stop
    $sourceDatabaseUpdatedAt = $sourceDatabase.LastWriteTimeUtc.ToString("o")
    Log "============================================"
    Log "  AM Tennis Refresh started at $timestamp"
    Log "============================================"

    Write-TennisManualProgress $root $manualRequest "extracting" "Importing the current saved OnCourt database."
    Log "=== Step 1/8: Fresh OnCourt extraction (run $refreshId) ==="
    Log "Source database last updated UTC: $sourceDatabaseUpdatedAt"
    $py32 = "C:\Python312-32\python.exe"
    if (-not (Test-Path -LiteralPath $py32)) {
        throw "32-bit OnCourt extractor is unavailable. Fresh refresh stopped."
    }
    $extractExit = Invoke-LoggedProcess -FilePath $py32 -ArgumentList @("scripts\oncourt-extract-all.py") -Label "Fresh OnCourt extract" -TimeoutSeconds 600
    if ($extractExit -ne 0) {
        throw "OnCourt extraction failed (exit $extractExit). Old exports will not be reused."
    }
    foreach ($csvName in @("today_atp.csv", "players_atp.csv", "tours_atp.csv", "games_atp.csv", "stat_atp.csv")) {
        $csv = Get-Item -LiteralPath (Join-Path $dataDir "oncourt\$csvName") -ErrorAction Stop
        if ($csv.LastWriteTimeUtc -lt [datetime]::Parse($refreshStartedAt).ToUniversalTime() -or $csv.Length -eq 0) {
            throw "Fresh OnCourt extraction did not replace $csvName."
        }
    }
    $afterExtractDatabase = Get-Item -LiteralPath $sourceDatabase.FullName
    if ($afterExtractDatabase.LastWriteTimeUtc.ToString("o") -ne $sourceDatabaseUpdatedAt -or $afterExtractDatabase.Length -ne $sourceDatabase.Length) {
        throw "OnCourt was updated during extraction. Wait for its update to finish and retry."
    }
    $oncourtExtractedAt = (Get-Date).ToUniversalTime().ToString("o")
    $nativePairingExit = Invoke-LoggedProcess -FilePath "python" -ArgumentList @("scripts\tennis_pairing_consistency.py") -Label "ATP/WTA native pairing freshness" -TimeoutSeconds 30
    if ($nativePairingExit -ne 0) { throw "Native pairing/identity exports are incomplete; pricing stopped." }

    Log "=== Step 2/8: Supabase sync (--quick --current-players) ==="
    $supabaseSyncExit = Invoke-LoggedProcess -FilePath "python" -ArgumentList @("scripts\oncourt-load-supabase.py", "--quick", "--current-players") -Label "Supabase quick current-player sync" -TimeoutSeconds $supabaseSyncTimeoutSeconds
    if ($supabaseSyncExit -ne 0) {
        Log "ERROR: Supabase sync failed (exit $supabaseSyncExit)"
        if ($supabaseSyncExit -eq 124) {
            $runStatusFinal = "timeout"
            $runStatusErrorType = "SupabaseSyncTimeout"
            $runStatusErrorMessage = "Supabase quick sync exceeded ${supabaseSyncTimeoutSeconds}s"
        } else {
            Set-RunStatusFailure "SupabaseSyncFailed" "Supabase sync failed (exit $supabaseSyncExit)"
        }
        exit 1
    }

    Write-TennisManualProgress $root $manualRequest "pricing" "OnCourt imported. Refreshing live inputs, prices and fair odds." @{ oncourt_database_updated_at = $sourceDatabaseUpdatedAt; oncourt_extracted_at = $oncourtExtractedAt }
    $dailyOddsArguments = @("scripts\run-daily-odds.py", "--skip-strict-report")
    if ($OnDemand) { $dailyOddsArguments += "--on-demand" }
    Log "=== Step 3/8: Pinnacle odds + fair odds ==="
    $step3Exit = Invoke-LoggedProcess -FilePath "python" -ArgumentList $dailyOddsArguments -Label "Pinnacle/fair-odds" -TimeoutSeconds $dailyOddsTimeoutSeconds
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

    # Generate every ML/spread signal before optional props work. The Telegram
    # digest must not wait behind a slow projection-board rebuild.
    Write-TennisManualProgress $root $manualRequest "signals" "Fresh match prices saved. Checking the existing selection rules." @{ oncourt_database_updated_at = $sourceDatabaseUpdatedAt; oncourt_extracted_at = $oncourtExtractedAt }
    Log "=== Step 4/8: Strict policy report (--append --compare-overlay) ==="
    $strictExit = Invoke-LoggedProcess -FilePath "python" -ArgumentList @("scripts\strict-policy-report.py", "--append", "--compare-overlay") -Label "strict policy report" -TimeoutSeconds $strictReportTimeoutSeconds
    if ($strictExit -ne 0) {
        Log "ERROR: strict-policy-report failed/timed out (exit $strictExit)"
        Set-RunStatusFailure "StrictPolicyReportFailed" "strict-policy-report failed/timed out (exit $strictExit)"
        exit 1
    }

    if ($null -ne $volumeCfg) {
        Log "=== Step 5/8: $($volumeCfg.Label) shadow (signal-profile=$($volumeCfg.Profile)) ==="
        & python scripts\strict-policy-report.py --append --signal-profile $volumeCfg.Profile --output "data\backtest\strict-signals-$($volumeCfg.Tag)-live.csv" --internal-output "data\backtest\strict-signals-$($volumeCfg.Tag)-internal-live.csv" 2>&1 | ForEach-Object { Log $_ }
        if ($LASTEXITCODE -ne 0) {
            Log "WARNING: $($volumeCfg.Profile) shadow append failed (exit $LASTEXITCODE), continuing..."
        }
    } else {
        Log "=== Step 5/8: Volume shadow skipped (STRICT_POLICY_VOLUME_MODE=$volumeMode) ==="
    }

    Log "=== Step 6/8: Research shadow lanes ==="
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
    Log "Grand Slam BO5 handicap evidence (raw probabilities, zero stake)."
    & python scripts\compute-handicap-values.py --bo5-only --allow-bo5 --disable-calibration 2>&1 | ForEach-Object { Log $_ }
    if ($LASTEXITCODE -eq 0) {
        $prevInternalResearch = $env:INTERNAL_RESEARCH_LANES
        $env:INTERNAL_RESEARCH_LANES = "1"
        try {
            & python scripts\strict-policy-report.py --append --signal-profile slam_bo5 2>&1 | ForEach-Object { Log $_ }
            if ($LASTEXITCODE -ne 0) {
                Log "WARNING: slam_bo5 evidence append failed (exit $LASTEXITCODE), continuing..."
            }
        }
        finally {
            if ($null -eq $prevInternalResearch) { Remove-Item Env:\INTERNAL_RESEARCH_LANES -ErrorAction SilentlyContinue }
            else { $env:INTERNAL_RESEARCH_LANES = $prevInternalResearch }
        }
    } else {
        Log "WARNING: BO5 handicap calculation failed (exit $LASTEXITCODE), continuing..."
    }
    Log "Clay calibrated legacy lane removed after failed ROI audit."
    if ($challengerMlEnabled) {
        Log "Challenger ML v2 prospective evidence (10-15% edge, HIGH coverage, zero stake)."
        & python scripts\strict-policy-report.py --append --signal-profile challenger_ml_shadow --output "data\backtest\strict-signals-challenger-ml-v2-live.csv" 2>&1 | ForEach-Object { Log $_ }
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

    $signalGeneratedAt = [datetime]::UtcNow.ToString("o")
    $signalReadyPath = Join-Path $root "data\backtest\tennis-signal-generation-status.json"
    @{
        date = $refreshDate
        status = "ok"
        completed_at = (Get-Date).ToUniversalTime().ToString("o")
        pipeline = "oncourt-am-refresh"
        refresh_id = $refreshId
        started_at = $refreshStartedAt
        oncourt_database_updated_at = $sourceDatabaseUpdatedAt
        oncourt_extracted_at = $oncourtExtractedAt
        odds_not_before = $refreshStartedAt
    } | ConvertTo-Json | Set-Content -Path $signalReadyPath -Encoding ASCII

    if ($CoreOnly) {
        Log "Core fresh refresh validated. Optional props, Telegram and Atlas publication skipped."
        $runStatusFinal = "ok"
        exit 0
    }

    Log "=== Step 7/8: Settlement/performance skipped in AM task ==="
    Log "Nightly tennis settlement/performance is handled by oncourt-daily.ps1 at 22:30 to keep AM refresh fast."

    Log "=== Post-step: spread_v1 refresh skipped in AM task (nightly/weekly only) ==="

    $matchReceiptPath = Join-Path $dataDir "backtest\tennis-manual-match-alerts.json"
    $propsReceiptPath = Join-Path $dataDir "backtest\tennis-manual-props-alerts.json"
    $matchDigestArguments = @("scripts\tennis-daily-signal-digest.py", "--date", $refreshDate, "--require-ready", "--props-pending", "--new-only")
    if ($OnDemand) { $matchDigestArguments += @("--receipt", $matchReceiptPath) }
    Log "=== Post-step: Daily tennis Telegram digest ==="
    $digestExit = 0
    if (-not $NoTelegram) { $digestExit = Invoke-LoggedProcess -FilePath "python" -ArgumentList $matchDigestArguments -Label "daily tennis Telegram digest" -TimeoutSeconds 90 }
    if ($digestExit -ne 0) {
        Log "WARNING: daily tennis Telegram digest failed/timed out (exit $digestExit); signal generation remains valid."
    }

    Write-TennisManualProgress $root $manualRequest "props" "Match prices and signals ready. Capturing fresh aces/double-fault prices and projections." @{ oncourt_database_updated_at = $sourceDatabaseUpdatedAt; oncourt_extracted_at = $oncourtExtractedAt; signal_generation_completed_at = $signalGeneratedAt; odds_not_before = $refreshStartedAt }
    Log "=== Step 8a/8: Capture tennis props prices ==="
    # Recover a missed hosted schedule once per UTC day, after the core digest.
    # The helper skips provider requests when fresh data or an active run exists.
    $hostedCaptureExit = Invoke-LoggedProcess -FilePath "python" -ArgumentList @("scripts\ensure-tennis-props-capture.py") -Label "hosted tennis props freshness recovery" -TimeoutSeconds 420
    if ($hostedCaptureExit -ne 0) {
        Log "WARNING: hosted tennis props recovery could not confirm fresh prices; comparison freshness checks remain enforced."
    }
    $tennisPropsCaptureExit = Invoke-LoggedProcess -FilePath "python" -ArgumentList @("scripts\run-tennis-props-daily.py", "--as-of", $refreshDate, "--capture-only") -Label "tennis props price capture" -TimeoutSeconds 540
    if ($tennisPropsCaptureExit -ne 0) {
        Log "WARNING: tennis props price capture failed/timed out (exit $tennisPropsCaptureExit), continuing..."
    }

    Log "=== Step 8b/8: Optional tennis props projection board ==="
    # Historical OnCourt scans are useful for the props monitor but are not
    # allowed to delay the daily ML/spread betting alert.
    $tennisPropsBoardExit = Invoke-LoggedProcess -FilePath "python" -ArgumentList @("scripts\build-tennis-props-board.py", "--as-of", $refreshDate, "--days-ahead", "3") -Label "tennis props projection board" -TimeoutSeconds 600
    if ($tennisPropsBoardExit -ne 0) {
        Log "WARNING: tennis props projection board failed/timed out (exit $tennisPropsBoardExit), continuing..."
    }
    # Capture and settlement must survive a timeout in the independent,
    # historical projection-board build.
    Log "=== Step 8c/8: Tennis props comparison and settlement ==="
    $propsCompareArguments = @("scripts\run-tennis-props-daily.py", "--as-of", $refreshDate, "--comparison-only", "--skip-derived-boards")
    if ($OnDemand) { $propsCompareArguments += "--selections-only" }
    $tennisPropsCompareExit = Invoke-LoggedProcess -FilePath "python" -ArgumentList $propsCompareArguments -Label "tennis props hosted-price comparison" -TimeoutSeconds 900
    if ($tennisPropsCompareExit -ne 0) {
        Log "WARNING: tennis props hosted-price comparison failed (exit $tennisPropsCompareExit), continuing..."
        # Coverage limitations may be expected, but stale/missing data or a
        # crashed comparison must reach the existing operations failure alert.
        $propsHealth = $null
        try { $propsHealth = Get-Content -LiteralPath (Join-Path $root "data\tennis-props\pipeline-health.json") -Raw | ConvertFrom-Json } catch {}
        $priceFreshnessFailed = $null -eq $propsHealth -or
            $propsHealth.as_of -ne $refreshDate -or
            $propsHealth.state -in @("CORE_RUN_IN_PROGRESS", "CORE_RUN_FAILED", "FEED_MISSING", "COMPARISON_MISSING", "BOARD_MATCH_FAILED") -or
            [int]$propsHealth.fresh_upcoming_line_rows -lt [int]$propsHealth.upcoming_line_rows
        if ($priceFreshnessFailed) {
            Set-RunStatusFailure "TennisPropsRefreshFailed" "Tennis props prices/comparison are stale or unavailable. Inspect data/tennis-props/pipeline-health.json."
        }
    }

    Log "=== Step 8c.1/8: Telegram tennis props delta ==="
    $propsDigestArguments = @("scripts\tennis-daily-signal-digest.py", "--date", $refreshDate, "--require-ready", "--new-only")
    if ($OnDemand) { $propsDigestArguments += @("--receipt", $propsReceiptPath) }
    $propsDigestExit = 0
    if (-not $NoTelegram) { $propsDigestExit = Invoke-LoggedProcess -FilePath "python" -ArgumentList $propsDigestArguments -Label "daily tennis Telegram props delta" -TimeoutSeconds 90 }
    if ($propsDigestExit -ne 0) {
        Log "WARNING: daily tennis Telegram props delta failed/timed out (exit $propsDigestExit); evidence collection remains valid."
    }

    if ($OnDemand) {
        # Forecast capture and registrations above are unchanged. Historical
        # settlement, CLV audits and public Atlas publication stay scheduled.
        $propsRefreshFailed = $tennisPropsCaptureExit -ne 0 -or $tennisPropsBoardExit -ne 0 -or $tennisPropsCompareExit -ne 0
        $paperSignalsExit = 0
        if (-not $NoTelegram -and -not $propsRefreshFailed) {
            $paperSignalsExit = Invoke-LoggedProcess -FilePath "python" -ArgumentList @("scripts\tennis-daily-signal-digest.py", "--date", $refreshDate, "--paper-signals-only", "--refresh-started-at", $refreshStartedAt) -Label "v4 new paper selections" -TimeoutSeconds 90
        }
        # Upload the evidence and its health flags even when an independent
        # delivery check failed. Failures still prevent a successful receipt.
        Write-TennisManualProgress $root $manualRequest "uploading" "Updating the private Monitor with current evidence and health checks."
        $privateSnapshotAttempted = $true
        $snapshotExit = Invoke-LoggedProcess -FilePath "python" -ArgumentList @("scripts\tennis-evidence-snapshot.py", "--supabase") -Label "private Monitor snapshot" -TimeoutSeconds 120
        if ($snapshotExit -ne 0) { throw "Private Monitor upload failed." }
        if ($propsRefreshFailed) {
            throw "Manual match prices refreshed, but the props refresh needs attention; old props are not reported as fresh."
        }
        if ($digestExit -ne 0 -or $propsDigestExit -ne 0) { throw "New-selection Telegram check failed." }
        if ($paperSignalsExit -ne 0) { throw "v4 new-selection check failed." }
        $receipts = @()
        if (-not $NoTelegram) {
            foreach ($receiptPath in @($matchReceiptPath, $propsReceiptPath)) {
                $receipt = Get-Content -LiteralPath $receiptPath -Raw | ConvertFrom-Json
                if ([datetime]::Parse($receipt.checked_at).ToUniversalTime() -lt [datetime]::Parse($refreshStartedAt).ToUniversalTime()) { throw "Stale Telegram receipt" }
                $receipts += $receipt
            }
        }
        & python scripts/tennis_runtime_health.py check --run-id $env:TENNIS_RUNTIME_RUN_ID | ForEach-Object { Log $_ }
        if ($LASTEXITCODE -ne 0) { throw "A tennis step failed or timed out. The refresh is incomplete; see runtime health." }
        $sent = ($receipts | Measure-Object -Property dispatched_count -Sum).Sum
        Write-TennisManualProgress $root $manualRequest "completed" "Fresh inputs, odds and signals are ready; historical reporting remains scheduled." @{
            state = "completed"; refresh_id = $refreshId; started_at = $refreshStartedAt;
            oncourt_database_updated_at = $sourceDatabaseUpdatedAt; oncourt_extracted_at = $oncourtExtractedAt;
            odds_not_before = $refreshStartedAt; signal_generation_completed_at = $signalGeneratedAt;
            completed_at = [datetime]::UtcNow.ToString("o"); telegram_new_signals = [int]$sent;
            telegram_status = $(if ($NoTelegram) { "disabled_for_validation" } elseif ($sent -gt 0) { "relay_queued" } else { "checked_no_new" });
        }
        $runStatusFinal = "ok"
        Log "On-demand refresh complete; no historical reporting or Atlas publication."
        exit 0
    }

    Exit-TaskLock $lockHandle
    $lockHandle = $null

    # Isolated published Elo snapshots; no live rating writer or model calls.
    # Alerts were sent and the tennis priority lock released above.
    try {
        $eloSourceExit = Invoke-LoggedProcess -FilePath "python" -ArgumentList @("scripts\tennis_elo_source.py") -Label "Published Elo research inputs" -TimeoutSeconds 90
        if ($eloSourceExit -ne 0) {
            Log "WARNING: isolated Elo source check failed/timed out; live pricing unchanged"
            $null = Invoke-LoggedProcess -FilePath "python" -ArgumentList @("scripts\tennis_elo_source.py", "--mark-interrupted") -Label "Elo source interruption status" -TimeoutSeconds 10
        }
    } catch {
        Log "WARNING: isolated Elo source process error; live pricing unchanged: $($_.Exception.Message)"
    }

    # Independent adult-history source after alerts; never replaces live or frozen v1.
    try {
        $nativeEloExit = Invoke-LoggedProcess -FilePath "python" -ArgumentList @("scripts\tennis_elo_native_source.py") -Label "Adult-history Elo research source" -TimeoutSeconds 180
        if ($nativeEloExit -ne 0) { Log "WARNING: native Elo research source needs review; live ratings unchanged" }
    } catch { Log "WARNING: native Elo source process error; live ratings unchanged" }
    # Outcomes from saved raw BP quotes, no new prices or notifications.
    try {
        $bpEvidenceExit = Invoke-LoggedProcess -FilePath "python" -ArgumentList @("scripts\tennis_breakpoint_evidence.py") -Label "Break-point exact-result evidence" -TimeoutSeconds 90
        $bpForwardExit = Invoke-LoggedProcess -FilePath "python" -ArgumentList @("scripts\tennis_breakpoint_forward.py", "--refresh-history") -Label "Break-point frozen paper evidence" -TimeoutSeconds 120
        if ($bpForwardExit -ne 0) { Log "WARNING: break-point paper evidence needs review; live unchanged" }
        if ($bpEvidenceExit -ne 0) { Log "WARNING: break-point result evidence needs review" }
    } catch { Log "WARNING: break-point result evidence process error" }

    # Deliver fresh selections before the slower historical settlement pass.
    Log "=== Post-step: Settle saved model evidence independently of capture ==="
    $lockHandle = Enter-TennisPriorityLock -RootPath $root
    # Capture the frozen paper comparison after alerts. The on-demand path has
    # already returned above; no new schedule or live prediction is introduced.
    $compassCaptureExit = Invoke-LoggedProcess -FilePath "python" -ArgumentList @("scripts\tennis_ace_compass.py", "--comparison", (Join-Path $root "data\tennis-props\comparison-$refreshDate.csv")) -Label "Ace Compass native-fixture paper capture" -TimeoutSeconds 240
    if ($compassCaptureExit -ne 0) { Set-RunStatusFailure "AceCompassCaptureFailed" "Frozen Ace Compass paper capture needs attention; live pricing is unchanged." }
    $settlementEvidenceExit = Invoke-LoggedProcess -FilePath "python" -ArgumentList @("scripts\tennis-settle-model-evidence.py") -Label "saved model evidence settlement" -TimeoutSeconds 300
    if ($settlementEvidenceExit -ne 0) { Set-RunStatusFailure "TennisEvidenceSettlementFailed" "Saved tennis model evidence did not settle successfully." }

    Exit-TaskLock $lockHandle
    $lockHandle = $null

    # v4 evidence must refresh before its daily summary and selection checks.
    Log "=== Post-step: v4 paper reporting after settlement ==="
    $lockHandle = Enter-TennisPriorityLock -RootPath $root
    if (-not $NoTelegram) {
        $paperSummaryExit = Invoke-LoggedProcess -FilePath "python" -ArgumentList @("scripts\tennis-daily-signal-digest.py", "--paper-summary-only") -Label "v4 daily evidence summary" -TimeoutSeconds 90
        $paperSignalsExit = Invoke-LoggedProcess -FilePath "python" -ArgumentList @("scripts\tennis-daily-signal-digest.py", "--date", $refreshDate, "--paper-signals-only", "--refresh-started-at", $refreshStartedAt) -Label "v4 fresh paper selections" -TimeoutSeconds 90
        if ($paperSummaryExit -ne 0 -or $paperSignalsExit -ne 0) { Log "WARNING: v4 paper reporting failed; existing relay dedup permits a safe retry." }
    }

    Exit-TaskLock $lockHandle
    $lockHandle = Enter-TennisPriorityLock -RootPath $root
    Log "=== Step 8d/8: Append Pinnacle history capture (daily) ==="
    & python scripts\pinnacle-capture-history.py --capture-mode daily 2>&1 | ForEach-Object { Log $_ }
    if ($LASTEXITCODE -ne 0) {
        Log "WARNING: Pinnacle history append failed (exit $LASTEXITCODE), continuing..."
    }

    Exit-TaskLock $lockHandle
    $lockHandle = Enter-TennisPriorityLock -RootPath $root
    Log "=== Step 8c.2/8: Compact tennis evidence snapshot ==="
    $evidenceSnapshotExit = Invoke-LoggedProcess -FilePath "python" -ArgumentList @("scripts\tennis-evidence-snapshot.py", "--supabase") -Label "tennis evidence snapshot" -TimeoutSeconds 120
    if ($evidenceSnapshotExit -ne 0) {
        Log "WARNING: tennis evidence snapshot failed/timed out (exit $evidenceSnapshotExit), continuing..."
    }

    Exit-TaskLock $lockHandle
    $lockHandle = Enter-TennisPriorityLock -RootPath $root
    # Return Atlas uses the existing hidden morning job, after all betting alerts.
    # The machine-local config opts this host in; no secret belongs in this file.
    $atlasConfigPath = "D:\IlMargine\return-atlas-automation\config.json"
    $atlasRunnerPath = "D:\IlMargine\return-atlas-automation\checkout\scripts\refresh-return-atlas.py"
    if (Test-Path -LiteralPath $atlasConfigPath) {
        Log "=== Post-step: validated Return Atlas refresh ==="
        $atlasExit = Invoke-LoggedProcess -FilePath "C:\Python314\python.exe" -ArgumentList @($atlasRunnerPath, "--config", $atlasConfigPath) -Label "Return Atlas automatic publication" -TimeoutSeconds 3600
        if ($atlasExit -ne 0) {
            Set-RunStatusFailure "ReturnAtlasRefreshFailed" "Return Atlas refresh failed; inspect D:\IlMargine\return-atlas-automation\status.json."
            Log "WARNING: Return Atlas refresh failed (exit $atlasExit); the last validated public archive is retained."
        }
    }

    Log "============================================"
    Log "  AM Tennis Refresh finished at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    Log "============================================"
    & python scripts/tennis_runtime_health.py check --run-id $env:TENNIS_RUNTIME_RUN_ID | ForEach-Object { Log $_ }
    if ($LASTEXITCODE -ne 0) { Set-RunStatusFailure "TennisStepFailed" "A tennis step failed or exceeded its deadline; see runtime health." }
    if ([string]::IsNullOrWhiteSpace($runStatusErrorType)) {
        $runStatusFinal = "ok"
        $runStatusErrorMessage = $null
    }
}
catch {
    $runStatusErrorRecord = $_
    Write-TennisManualProgress $root $manualRequest "failed" $_.Exception.Message @{ state = "failed"; error = $_.Exception.Message; completed_at = [datetime]::UtcNow.ToString("o") }
    Set-RunStatusFailure "UnhandledException" $_.Exception.Message
    throw
}
finally {
    try {
        # Explicit exit 1 bypasses catch. Always close the Admin progress record,
        # including early source outages, without relabelling stale prices fresh.
        if ($OnDemand -and $runStatusFinal -ne "ok") {
            $failureMessage = if ($runStatusErrorMessage) { $runStatusErrorMessage } else { "Fresh tennis refresh did not complete. Check the run log." }
            Write-TennisManualProgress $root $manualRequest "failed" $failureMessage @{ state = "failed"; error = $failureMessage; completed_at = [datetime]::UtcNow.ToString("o") }
            if (-not $privateSnapshotAttempted) {
                $privateSnapshotAttempted = $true
                try {
                    $failureSnapshotExit = Invoke-LoggedProcess -FilePath "python" -ArgumentList @("scripts\tennis-evidence-snapshot.py", "--supabase") -Label "private Monitor failure health" -TimeoutSeconds 120
                    if ($failureSnapshotExit -ne 0) { Log "WARNING: failure health snapshot upload failed (exit $failureSnapshotExit)." }
                } catch { Log "WARNING: failure health upload failed: $($_.Exception.Message)" }
            }
        }
        try {
            $runtimeWatchArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', 'scripts/tennis-health-check.ps1', '-RuntimeOnly')
            if ($NoTelegram) { $runtimeWatchArgs += '-NoNotify' }
            & powershell.exe @runtimeWatchArgs
        }
        catch { Log "WARNING: runtime watchdog failed: $($_.Exception.Message)" }
        Complete-RunStatus -Run $runStatus -Status $runStatusFinal -ErrorRecord $runStatusErrorRecord -ErrorType $runStatusErrorType -ErrorMessage $runStatusErrorMessage
    } finally {
        Exit-TaskLock $lockHandle
    }
}

if ($runStatusFinal -ne "ok") { exit 1 }
