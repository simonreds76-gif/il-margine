# Il Margine - Goalscorer live watchdog
# Purpose: detect stale live polling during the daytime window and safely kick the
#          scheduled live task if the snapshot/heartbeat has gone stale.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

$dataDir = Join-Path $root "data\goalscorer"
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null

$psExe = "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe"
$healthLog = Join-Path $dataDir "goalscorer-health.log"
$healthFile = Join-Path $dataDir "goalscorer-health-status.json"
$statusFile = Join-Path $dataDir "goalscorer-live-status.json"
$snapshotFile = Join-Path $dataDir "goalscorer-live-snapshot.json"

$staleMinutes = 50
$runningGraceMinutes = 25
$rerunCooldownMinutes = 20
$windowStart = [TimeSpan]::Parse("12:00:00")
$windowEnd = [TimeSpan]::Parse("23:45:00")

function Log($msg) {
    $line = "$(Get-Date -Format 'HH:mm:ss') $msg"
    Write-Host $line
    Add-Content -Path $healthLog -Value $line
}

function Read-JsonFile($path) {
    if (!(Test-Path $path)) {
        return $null
    }

    try {
        return Get-Content $path -Raw | ConvertFrom-Json
    } catch {
        return $null
    }
}

function To-DateTime($value) {
    if ([string]::IsNullOrWhiteSpace($value)) {
        return $null
    }

    try {
        return [DateTimeOffset]::Parse($value).UtcDateTime
    } catch {
        return $null
    }
}

function Write-Health {
    param(
        [string]$State,
        [string]$Action,
        [string]$Message,
        [Nullable[Double]]$SnapshotAgeMinutes = $null,
        [Nullable[Double]]$HeartbeatAgeMinutes = $null,
        [object]$LiveStatus = $null,
        [string]$LastAutoRerunAt = $null
    )

    $payload = [ordered]@{
        checked_at = (Get-Date).ToUniversalTime().ToString("o")
        state = $State
        action = $Action
        message = $Message
        snapshot_age_minutes = if ($SnapshotAgeMinutes -ne $null) { [Math]::Round($SnapshotAgeMinutes, 1) } else { $null }
        heartbeat_age_minutes = if ($HeartbeatAgeMinutes -ne $null) { [Math]::Round($HeartbeatAgeMinutes, 1) } else { $null }
        last_auto_rerun_at = $LastAutoRerunAt
        live_status = $LiveStatus
    }

    ($payload | ConvertTo-Json -Depth 6) | Set-Content -Path $healthFile -Encoding UTF8
}

$now = Get-Date
$nowUtc = $now.ToUniversalTime()
$timeNow = $now.TimeOfDay
$healthState = Read-JsonFile $healthFile
$liveStatus = Read-JsonFile $statusFile
$lastAutoRerunAt = To-DateTime ($healthState.last_auto_rerun_at)

$snapshotAgeMinutes = $null
if (Test-Path $snapshotFile) {
    $snapshotAgeMinutes = ($nowUtc - (Get-Item $snapshotFile).LastWriteTimeUtc).TotalMinutes
}

$startedAt = To-DateTime ($liveStatus.last_started_at)
$finishedAt = To-DateTime ($liveStatus.last_finished_at)
$lastSuccessAt = To-DateTime ($liveStatus.last_successful_finished_at)
$heartbeatAgeMinutes = $null
if ($lastSuccessAt) {
    $heartbeatAgeMinutes = ($nowUtc - $lastSuccessAt).TotalMinutes
}

if ($timeNow -lt $windowStart -or $timeNow -gt $windowEnd) {
    $message = "Outside the live polling window. No watchdog action needed."
    Log $message
    Write-Health -State "outside_window" -Action "none" -Message $message -SnapshotAgeMinutes $snapshotAgeMinutes -HeartbeatAgeMinutes $heartbeatAgeMinutes -LiveStatus $liveStatus -LastAutoRerunAt ($healthState.last_auto_rerun_at)
    exit 0
}

if ($liveStatus -and $liveStatus.state -eq "running" -and $startedAt) {
    $runAgeMinutes = ($nowUtc - $startedAt).TotalMinutes
    if ($runAgeMinutes -le $runningGraceMinutes) {
        $message = "Live poll is currently running and still within the expected grace window."
        Log $message
        Write-Health -State "running" -Action "none" -Message $message -SnapshotAgeMinutes $snapshotAgeMinutes -HeartbeatAgeMinutes $heartbeatAgeMinutes -LiveStatus $liveStatus -LastAutoRerunAt ($healthState.last_auto_rerun_at)
        exit 0
    }

    $message = "Live poll still reports running after $([Math]::Round($runAgeMinutes, 1)) minutes. Leaving it alone to avoid duplicate concurrent runs."
    Log $message
    Write-Health -State "stale_running" -Action "none" -Message $message -SnapshotAgeMinutes $snapshotAgeMinutes -HeartbeatAgeMinutes $heartbeatAgeMinutes -LiveStatus $liveStatus -LastAutoRerunAt ($healthState.last_auto_rerun_at)
    exit 0
}

$freshEnough = $false
if ($snapshotAgeMinutes -ne $null -and $snapshotAgeMinutes -le $staleMinutes) {
    $freshEnough = $true
}
if (-not $freshEnough -and $heartbeatAgeMinutes -ne $null -and $heartbeatAgeMinutes -le $staleMinutes) {
    $freshEnough = $true
}

if ($freshEnough) {
    $message = "Goalscorer heartbeat is fresh enough. No watchdog action needed."
    Log $message
    Write-Health -State "healthy" -Action "none" -Message $message -SnapshotAgeMinutes $snapshotAgeMinutes -HeartbeatAgeMinutes $heartbeatAgeMinutes -LiveStatus $liveStatus -LastAutoRerunAt ($healthState.last_auto_rerun_at)
    exit 0
}

if ($lastAutoRerunAt -and ($nowUtc - $lastAutoRerunAt).TotalMinutes -lt $rerunCooldownMinutes) {
    $message = "Goalscorer heartbeat is stale, but the watchdog already kicked the live poll recently. Waiting for cooldown."
    Log $message
    Write-Health -State "stale_cooldown" -Action "cooldown" -Message $message -SnapshotAgeMinutes $snapshotAgeMinutes -HeartbeatAgeMinutes $heartbeatAgeMinutes -LiveStatus $liveStatus -LastAutoRerunAt ($lastAutoRerunAt.ToString("o"))
    exit 0
}

Log "Goalscorer heartbeat is stale. Triggering IlMargine-Goalscorer-Live."
$result = schtasks /Run /TN IlMargine-Goalscorer-Live 2>&1
$lastAutoRerunAtUtc = (Get-Date).ToUniversalTime().ToString("o")
foreach ($line in $result) {
    Log $line
}

$message = "Goalscorer heartbeat was stale, so the watchdog triggered the live task."
Write-Health -State "stale_restarted" -Action "run_live_task" -Message $message -SnapshotAgeMinutes $snapshotAgeMinutes -HeartbeatAgeMinutes $heartbeatAgeMinutes -LiveStatus $liveStatus -LastAutoRerunAt $lastAutoRerunAtUtc
