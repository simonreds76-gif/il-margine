# Il Margine - AM Tennis Refresh
# Lighter daytime refresh: refresh today's OnCourt schedule/tours, then odds/fair-odds/shadow append/settlement.

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
if ([string]::IsNullOrWhiteSpace($env:STRICT_SPREAD_V1_SHADOW_ENABLED)) { $env:STRICT_SPREAD_V1_SHADOW_ENABLED = "1" }
if ([string]::IsNullOrWhiteSpace($env:STRICT_CLAY_CALIBRATED_ENABLED)) { $env:STRICT_CLAY_CALIBRATED_ENABLED = "0" }
$spreadFitFiles = @(
    "data/backtest/backtest-results-2025.csv",
    "data/backtest/backtest-results-2026.csv"
)
$spreadRefreshTimeoutSeconds = 240

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
        return $proc.ExitCode
    } finally {
        Remove-Item -LiteralPath $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue
    }
}

$lockHandle = Enter-TaskLock -LockName "tennis-automation" -RootPath $root -WaitSeconds 900 -PollSeconds 10
if ($null -eq $lockHandle) {
    Log "Another tennis automation run stayed active for 15 minutes; exiting."
    exit 0
}

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

    Log "=== Step 2/8: Supabase sync (--quick --skip-players) ==="
    & python scripts\oncourt-load-supabase.py --quick --skip-players 2>&1 | ForEach-Object { Log $_ }
    if ($LASTEXITCODE -ne 0) {
        Log "ERROR: Supabase sync failed (exit $LASTEXITCODE)"
        exit 1
    }

    Log "=== Step 3/8: Pinnacle odds + fair odds ==="
    $step3Output = & python scripts\run-daily-odds.py --skip-strict-report 2>&1
    $step3Exit = $LASTEXITCODE
    $step3Lines = @($step3Output | ForEach-Object { "$_" })
    $step3Lines | ForEach-Object { Log $_ }
    if ($step3Exit -ne 0) {
        Log "ERROR: Pinnacle/fair-odds failed (exit $step3Exit)"
        exit 1
    }
    $step3Synced = $step3Lines | Select-String -SimpleMatch "Synced daily_fair_odds:"
    if (-not $step3Synced) {
        Log "ERROR: Pinnacle/fair-odds completed without confirming daily_fair_odds sync"
        exit 1
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
        & python scripts\strict-policy-report.py --append --signal-profile spread_v1_shadow --output "data\backtest\strict-signals-spreadv1-live.csv" 2>&1 | ForEach-Object { Log $_ }
        if ($LASTEXITCODE -ne 0) {
            Log "WARNING: spread_v1_shadow append failed (exit $LASTEXITCODE), continuing..."
        }
    } else {
        Log "Spread v1 shadow skipped (STRICT_SPREAD_V1_SHADOW_ENABLED=0)."
    }
    if ($clayCalibratedEnabled) {
        & python scripts\strict-policy-report.py --append --signal-profile clay_calibrated --output "data\backtest\strict-signals-claycal-live.csv" --internal-output "data\backtest\strict-signals-claycal-internal-live.csv" 2>&1 | ForEach-Object { Log $_ }
        if ($LASTEXITCODE -ne 0) {
            Log "WARNING: clay_calibrated append failed (exit $LASTEXITCODE), continuing..."
        }
    } else {
        Log "Clay calibrated lane skipped by default (STRICT_CLAY_CALIBRATED_ENABLED=0)."
    }

    Log "=== Step 8/8: Nightly-style tennis settlement/performance ==="
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
    Log "  AM Tennis Refresh finished at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    Log "============================================"
}
finally {
    Exit-TaskLock $lockHandle
}
