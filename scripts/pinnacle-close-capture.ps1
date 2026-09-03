# Il Margine - Pinnacle Close Capture
# Intended for a frequent scheduled task (e.g. every 15 minutes).
# Appends one full Pinnacle scrape run to bookmaker_odds_history.

$ErrorActionPreference = "Stop"
$scriptPath = $MyInvocation.MyCommand.Path
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root
. (Join-Path $root "scripts\use-local-python.ps1") -RepoRoot $root
. (Join-Path $root "scripts\task-lock.ps1")

$dataDir = Join-Path $root "data"
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null

$logFile = Join-Path $dataDir "pinnacle-close-capture.log"
$heartbeatFile = Join-Path $dataDir "pinnacle-close-capture-heartbeat.json"

function Log($msg) {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $msg"
    Write-Host $line
    Add-Content -Path $logFile -Value $line
}

function Get-LockSnapshot([string]$lockPath) {
    if ([string]::IsNullOrWhiteSpace($lockPath) -or !(Test-Path $lockPath)) {
        return $null
    }

    try {
        $item = Get-Item $lockPath
        return [ordered]@{
            path = $item.FullName
            last_write_time = $item.LastWriteTimeUtc.ToString("o")
            content = (Get-Content $lockPath -Raw -ErrorAction Stop)
        }
    } catch {
        return [ordered]@{
            path = $lockPath
            read_error = $_.Exception.Message
        }
    }
}

function Write-Heartbeat {
    param(
        [Parameter(Mandatory = $true)]
        [string]$State,
        [hashtable]$Extra = @{}
    )

    $payload = [ordered]@{
        pipeline = "pinnacle-close-capture"
        state = $State
        heartbeat_version = 1
        local_time = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
        utc_time = (Get-Date).ToUniversalTime().ToString("o")
        pid = $PID
        host = $env:COMPUTERNAME
        user = $env:USERNAME
        script = $scriptPath
        root = $root
        log_file = $logFile
    }

    foreach ($key in $Extra.Keys) {
        $payload[$key] = $Extra[$key]
    }

    $json = $payload | ConvertTo-Json -Depth 6
    [System.IO.File]::WriteAllText($heartbeatFile, $json, [System.Text.UTF8Encoding]::new($false))
}

function Resolve-PythonCommand {
    try {
        return (Get-Command python -ErrorAction Stop).Source
    } catch {
        return $null
    }
}

$pythonCommand = Resolve-PythonCommand
$lockPath = Join-Path $root "data\locks\tennis-automation.lock"
$directExitCode = $null
$movementRefreshExitCode = $null

Write-Heartbeat -State "starting" -Extra @{
    python = $pythonCommand
}

$lockHandle = Enter-TaskLock -LockName "tennis-automation" -RootPath $root
if ($null -eq $lockHandle) {
    Log "Another tennis automation run is already active; skipping close capture."
    Write-Heartbeat -State "skipped_locked" -Extra @{
        python = $pythonCommand
        lock = (Get-LockSnapshot $lockPath)
    }
    exit 0
}

try {
    Log "=== Pinnacle close capture start ==="
    Log "Task context: user=$env:USERNAME host=$env:COMPUTERNAME pid=$PID python=$pythonCommand"
    Write-Heartbeat -State "running" -Extra @{
        python = $pythonCommand
        lock = [ordered]@{
            path = $lockHandle.Path
        }
    }
    & python scripts\pinnacle-capture-history.py --capture-mode close 2>&1 | ForEach-Object { Log $_ }
    if ($LASTEXITCODE -ne 0) {
        Log "ERROR: pinnacle close capture failed (exit $LASTEXITCODE)"
        Write-Heartbeat -State "failed" -Extra @{
            python = $pythonCommand
            exit_code = $LASTEXITCODE
            lock = [ordered]@{
                path = $lockHandle.Path
            }
        }
        exit 1
    }

    $asOf = (Get-Date).ToUniversalTime().ToString("yyyy-MM-dd")
    $directScript = Join-Path $root "scripts\tennis-props-scrape-bet365-direct.py"
    if (Test-Path $directScript) {
        Log "=== Tracked Bet365 service-break close capture start ==="
        & python $directScript --date $asOf --tracked-only --max-events 20 --timeout-seconds 8 2>&1 | ForEach-Object { Log $_ }
        $directExitCode = $LASTEXITCODE
        if ($directExitCode -ne 0) {
            # A blocked browser session must not invalidate a successful Pinnacle capture.
            Log "WARNING: tracked Bet365 service-break close capture failed (exit $directExitCode)"
        } else {
            Log "=== Tracked Bet365 service-break close capture done ==="
            $historyPath = Join-Path $root "data\tennis-props\inbox\bet365-lines-history-$($asOf.Substring(0, 7)).csv"
            & python scripts\tennis-props-shadow-tracker.py --movement-history $historyPath 2>&1 | ForEach-Object { Log $_ }
            $movementRefreshExitCode = $LASTEXITCODE
            if ($movementRefreshExitCode -ne 0) {
                Log "WARNING: service-break movement refresh failed (exit $movementRefreshExitCode)"
            }
        }
    }
    Log "=== Pinnacle close capture done ==="
    Write-Heartbeat -State "ok" -Extra @{
        python = $pythonCommand
        exit_code = 0
        bet365_breaks_exit_code = $directExitCode
        movement_refresh_exit_code = $movementRefreshExitCode
        lock = [ordered]@{
            path = $lockHandle.Path
        }
    }
}
catch {
    Log "ERROR: pinnacle close capture threw exception: $($_.Exception.Message)"
    Write-Heartbeat -State "failed" -Extra @{
        python = $pythonCommand
        error = $_.Exception.Message
        error_type = $_.Exception.GetType().FullName
        lock = if ($lockHandle) {
            [ordered]@{
                path = $lockHandle.Path
            }
        } else {
            $null
        }
    }
    throw
}
finally {
    Exit-TaskLock $lockHandle
}
