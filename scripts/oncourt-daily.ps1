# Il Margine — Daily Scheduled Task (runs at 11:00 and 23:55)
# Fully automatic: extract -> sync -> stats -> injury/CPI refresh -> odds -> strict report append

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

# Choose sync args once here:
#   @("--quick")                  = fast daily including players/rankings
#   @("--recent")                 = last 365 days games/stat
$syncArgs = @("--recent")
$syncLabel = ($syncArgs -join " ")
# Enable trimmed shadow profile by default for scheduled runs (override with env if needed)
if ([string]::IsNullOrWhiteSpace($env:STRICT_POLICY_VOLUME_MODE)) { $env:STRICT_POLICY_VOLUME_MODE = "volume_200" }
$volumeMode = "$env:STRICT_POLICY_VOLUME_MODE".ToLower()
if ([string]::IsNullOrWhiteSpace($volumeMode)) { $volumeMode = "off" }
if ([string]::IsNullOrWhiteSpace($env:STRICT_SPREAD_V1_SHADOW_ENABLED)) { $env:STRICT_SPREAD_V1_SHADOW_ENABLED = "1" }
if ([string]::IsNullOrWhiteSpace($env:STRICT_CLAY_CALIBRATED_ENABLED)) { $env:STRICT_CLAY_CALIBRATED_ENABLED = "0" }
if ([string]::IsNullOrWhiteSpace($env:CHALLENGER_ML_ENABLE)) { $env:CHALLENGER_ML_ENABLE = "0" }
if ([string]::IsNullOrWhiteSpace($env:STRICT_SPREAD_V1_CLAY_FAV_ENABLED)) { $env:STRICT_SPREAD_V1_CLAY_FAV_ENABLED = "0" }
if ([string]::IsNullOrWhiteSpace($env:STRICT_CLAY_BO3_ENABLED)) { $env:STRICT_CLAY_BO3_ENABLED = "1" }
if ([string]::IsNullOrWhiteSpace($env:CLAY_BO3_ML_ENABLE)) { $env:CLAY_BO3_ML_ENABLE = "0" }
# Scheduled runs are hard-safe: clay spread-v1 can only be enabled by a manual research run.
$env:SPREAD_V1_ENABLE_CLAY = "0"
$spreadFitFiles = @(
    "data/backtest/backtest-results-2025.csv",
    "data/backtest/backtest-results-2026.csv"
)
$spreadRefreshTimeoutSeconds = 240
$dailyOddsTimeoutSeconds = 1800
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
$clayCalibratedEnabled = Test-EnvFlag $env:STRICT_CLAY_CALIBRATED_ENABLED
$challengerMlEnabled = Test-EnvFlag $env:CHALLENGER_ML_ENABLE
$clayFavEnabled = Test-EnvFlag $env:STRICT_SPREAD_V1_CLAY_FAV_ENABLED
$clayBo3Enabled = Test-EnvFlag $env:STRICT_CLAY_BO3_ENABLED

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
            return 0
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

# Step 3: Compute player stats (extended writes both v2 and backwards-compat tables)
Log "=== Step 3/10: Compute player stats (extended) ==="
& python scripts\oncourt-compute-player-stats-extended.py 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "ERROR: Player stats failed (exit $LASTEXITCODE)"
    exit 1
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

# Step 6: Pinnacle odds + fair odds
Log "=== Step 6/10: Pinnacle odds + fair odds ==="
$step6Exit = Invoke-LoggedProcess -FilePath "python" -ArgumentList @("scripts\run-daily-odds.py", "--skip-strict-report") -Label "Pinnacle/fair-odds" -TimeoutSeconds $dailyOddsTimeoutSeconds
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

if ($clayCalibratedEnabled) {
    Log "=== Step 8c/10: Clay 2026 shadow (new-after-calibration favorites 55-65%) ==="
    & python scripts\strict-policy-report.py --append --signal-profile clay_calibrated --output "data\backtest\strict-signals-claycal-live.csv" --internal-output "data\backtest\strict-signals-claycal-internal-live.csv" 2>&1 | ForEach-Object { Log $_ }
    if ($LASTEXITCODE -ne 0) {
        Log "WARNING: clay_calibrated append failed (exit $LASTEXITCODE), continuing..."
    }
} else {
    Log "=== Step 8c/10: Clay 2026 shadow skipped (STRICT_CLAY_CALIBRATED_ENABLED override is off) ==="
}

if ($challengerMlEnabled) {
    Log "=== Step 8d/10: Challenger ML internal shadow (10-15% edge, HIGH coverage) ==="
    & python scripts\strict-policy-report.py --append --signal-profile challenger_ml_shadow --output "data\backtest\strict-signals-challenger-ml-live.csv" 2>&1 | ForEach-Object { Log $_ }
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

if ($clayBo3Enabled) {
    Log "=== Step 8f/10: Clay bo3 internal shadow (ML 5-13%, dog HC 6-25%) ==="
    $prevInternalResearchLanes = $env:INTERNAL_RESEARCH_LANES
    $env:INTERNAL_RESEARCH_LANES = "1"
    try {
        & python scripts\strict-policy-report.py --append --signal-profile clay_bo3 --output "data\backtest\strict-signals-clay_bo3-live.csv" 2>&1 | ForEach-Object { Log $_ }
        if ($LASTEXITCODE -ne 0) {
            Log "WARNING: clay_bo3 append failed (exit $LASTEXITCODE), continuing..."
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
    Log "=== Step 8f/10: Clay bo3 shadow skipped (STRICT_CLAY_BO3_ENABLED=0) ==="
}

# Step 9: Settle/report immediately after nightly append so results are ready by the next morning.
Log "=== Step 9/10: Nightly tennis settlement/performance ==="
& powershell -ExecutionPolicy Bypass -NoProfile -File scripts\oncourt-settle-nightly.ps1 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: nightly tennis settlement failed (exit $LASTEXITCODE), continuing..."
}

Log "=== Post-step: Refresh spread_v1 calibration + correction model (non-blocking) ==="
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

Log "============================================"
Log "  Daily Pipeline finished at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
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
