# Il Margine - Goalscorer live polling task
# Purpose: refresh odds, fetch confirmed lineups, rerun live compare, log output.

param(
    [switch]$ForceAllLeagues
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root
. (Join-Path $root "scripts\task-lock.ps1")

$dataDir = Join-Path $root "data\goalscorer"
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$logFile = Join-Path $dataDir "goalscorer-live.log"
$statusFile = Join-Path $dataDir "goalscorer-live-status.json"
$scheduleStateFile = Join-Path $dataDir "goalscorer-live-schedule-state.json"
$runStartedAtUtc = (Get-Date).ToUniversalTime().ToString("o")
$lastSuccessfulFinishedAt = $null
$currentLeague = ""
$warningMessages = New-Object System.Collections.Generic.List[string]
$failureCooldownMinutes = 60
$failureThreshold = 3
$detailCadenceHotMinutes = 60
$ranLeagueCount = 0
$failedLeagueCount = 0
$schedulerLeaguesState = [ordered]@{}

function Log($msg) {
    $line = "$(Get-Date -Format 'HH:mm:ss') $msg"
    Write-Host $line
    $utf8NoBom = [System.Text.UTF8Encoding]::new($false)
    for ($attempt = 0; $attempt -lt 3; $attempt++) {
        try {
            [System.IO.File]::AppendAllText($logFile, $line + [Environment]::NewLine, $utf8NoBom)
            return
        } catch {
            if ($attempt -eq 2) {
                throw
            }
            Start-Sleep -Milliseconds 150
        }
    }
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

function Get-IsoAgeMinutes([string]$IsoValue) {
    if ([string]::IsNullOrWhiteSpace($IsoValue)) {
        return $null
    }

    try {
        $parsed = [DateTimeOffset]::Parse($IsoValue)
        return (([DateTimeOffset]::UtcNow) - $parsed.ToUniversalTime()).TotalMinutes
    } catch {
        return $null
    }
}

function Get-ExistingLeagueState($state, [string]$league) {
    if ($null -eq $state -or $null -eq $state.leagues) {
        return $null
    }

    if ($state.leagues.PSObject.Properties.Name -contains $league) {
        return $state.leagues.$league
    }

    return $null
}

function Initialize-SchedulerState {
    param(
        $PreviousState,
        [string[]]$LeagueNames
    )

    $state = [ordered]@{}
    foreach ($league in $LeagueNames) {
        $existing = Get-ExistingLeagueState $PreviousState $league
        $state[$league] = [ordered]@{
            last_successful_run_at = if ($existing) { [string]$existing.last_successful_run_at } else { "" }
            last_detail_run_at = if ($existing) { [string]$existing.last_detail_run_at } else { "" }
            last_failure_at = if ($existing) { [string]$existing.last_failure_at } else { "" }
            consecutive_failures = if ($existing -and $existing.consecutive_failures -ne $null) { [int]$existing.consecutive_failures } else { 0 }
            last_tier = if ($existing) { [string]$existing.last_tier } else { "" }
            last_decision = if ($existing) { [string]$existing.last_decision } else { "" }
            last_message = if ($existing) { [string]$existing.last_message } else { "" }
            next_kickoff_utc = if ($existing) { [string]$existing.next_kickoff_utc } else { "" }
        }
    }
    return $state
}

function Save-SchedulerState([string]$Reason) {
    $payload = [ordered]@{
        updated_at = (Get-Date).ToUniversalTime().ToString("o")
        reason = $Reason
        leagues = $schedulerLeaguesState
    }
    ($payload | ConvertTo-Json -Depth 6) | Set-Content -Path $scheduleStateFile -Encoding UTF8
}

function Update-LeagueState {
    param(
        [string]$League,
        [string]$Tier,
        [string]$Decision,
        [string]$Message,
        [string]$NextKickoffUtc = "",
        [Nullable[int]]$ConsecutiveFailures = $null,
        [string]$LastFailureAt = $null,
        [string]$LastSuccessfulRunAt = $null,
        [string]$LastDetailRunAt = $null
    )

    if (-not ($schedulerLeaguesState.Keys -contains $League)) {
        $schedulerLeaguesState[$League] = [ordered]@{}
    }

    $record = $schedulerLeaguesState[$League]
    if ($Tier -ne $null) { $record.last_tier = $Tier }
    if ($Decision -ne $null) { $record.last_decision = $Decision }
    if ($Message -ne $null) { $record.last_message = $Message }
    if ($NextKickoffUtc -ne $null) { $record.next_kickoff_utc = $NextKickoffUtc }
    if ($ConsecutiveFailures -ne $null) { $record.consecutive_failures = [int]$ConsecutiveFailures }
    if ($LastFailureAt -ne $null) { $record.last_failure_at = $LastFailureAt }
    if ($LastSuccessfulRunAt -ne $null) { $record.last_successful_run_at = $LastSuccessfulRunAt }
    if ($LastDetailRunAt -ne $null) { $record.last_detail_run_at = $LastDetailRunAt }
}

function Write-Status {
    param(
        [string]$State,
        [string]$Message = "",
        [int]$ExitCode = 0
    )

    $nowUtc = (Get-Date).ToUniversalTime().ToString("o")
    $status = [ordered]@{
        state = $State
        updated_at = $nowUtc
        last_started_at = $runStartedAtUtc
        last_finished_at = if ($State -eq "running") { $null } else { $nowUtc }
        last_successful_finished_at = $lastSuccessfulFinishedAt
        current_league = $currentLeague
        bookmaker = $bookmaker
        leagues = @($leagues)
        warnings = @($warningMessages)
        message = $Message
        last_exit_code = $ExitCode
    }

    ($status | ConvertTo-Json -Depth 4) | Set-Content -Path $statusFile -Encoding UTF8
}

function Resolve-PythonExe {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source) {
        return $cmd.Source
    }

    $fallbacks = @(
        "C:\Python314\python.exe",
        "C:\Python313\python.exe",
        "C:\Python312\python.exe",
        "C:\Python311\python.exe"
    )

    foreach ($candidate in $fallbacks) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    throw "Python executable not found for goalscorer live task."
}

function Get-SchedulePlan {
    $json = & $pythonExe scripts\goalscorer-live-schedule.py --leagues ($leagues -join ",") --json 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "goalscorer-live-schedule failed (exit $LASTEXITCODE): $($json -join [Environment]::NewLine)"
    }

    $payload = ($json -join [Environment]::NewLine).Trim()
    if ([string]::IsNullOrWhiteSpace($payload)) {
        throw "goalscorer-live-schedule returned no payload."
    }

    try {
        return $payload | ConvertFrom-Json
    } catch {
        throw "Failed to parse goalscorer-live-schedule JSON payload."
    }
}

$bookmaker = if ([string]::IsNullOrWhiteSpace($env:GOALSCORER_BOOKMAKER)) { "Bet365" } else { $env:GOALSCORER_BOOKMAKER }
$oddsApiBooks = if ([string]::IsNullOrWhiteSpace($env:GOALSCORER_ODDS_API_BOOKMAKERS)) { "Bet365" } else { $env:GOALSCORER_ODDS_API_BOOKMAKERS }
$forceRunAll = $ForceAllLeagues -or ($env:GOALSCORER_FORCE_ALL -eq "1")
$leagues = if ([string]::IsNullOrWhiteSpace($env:GOALSCORER_LEAGUES)) {
    @("serie-a", "epl", "la-liga", "bundesliga", "ligue-1")
} else {
    $env:GOALSCORER_LEAGUES.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ }
}
$pythonExe = Resolve-PythonExe

$requiredPlayerLogs = @{
    "serie-a" = "data\goalscorer\serie-a-player-match-logs-2025-2026.csv"
    "epl" = "data\goalscorer\epl-player-match-logs-2025-2026.csv"
    "la-liga" = "data\goalscorer\la-liga-player-match-logs-2025-2026.csv"
    "bundesliga" = "data\goalscorer\bundesliga-player-match-logs-2025-2026.csv"
    "ligue-1" = "data\goalscorer\ligue-1-player-match-logs-2025-2026.csv"
}

$previousStatus = Read-JsonFile $statusFile
if ($previousStatus -and $previousStatus.last_successful_finished_at) {
    $lastSuccessfulFinishedAt = [string]$previousStatus.last_successful_finished_at
}
$previousScheduleState = Read-JsonFile $scheduleStateFile
$schedulerLeaguesState = Initialize-SchedulerState -PreviousState $previousScheduleState -LeagueNames $leagues

$lockHandle = Enter-TaskLock -LockName "goalscorer-automation" -RootPath $root
if ($null -eq $lockHandle) {
    Log "Another goalscorer automation run is already active; exiting."
    Write-Status -State "skipped" -Message "Another goalscorer automation run is already active" -ExitCode 0
    exit 0
}

try {
    Log "============================================"
    Log "  Goalscorer live poll started at $timestamp"
    Log "============================================"
    Log "Python executable: $pythonExe"
    Log "Bookmaker filter: $bookmaker"
    Log "Odds API books:   $oddsApiBooks"
    Log "Leagues:          $($leagues -join ', ')"
    if ($forceRunAll) {
        Log "Manual mode:      Force all leagues"
    }
    Write-Status -State "running" -Message "Goalscorer live poll started"
    $schedulePlan = if ($forceRunAll) {
        [pscustomobject]@{ leagues = @() }
    } else {
        Get-SchedulePlan
    }
    $schedulePlanLookup = @{}
    foreach ($entry in $schedulePlan.leagues) {
        $schedulePlanLookup[[string]$entry.league] = $entry
    }

    foreach ($league in $leagues) {
        $currentLeague = $league
        $leaguePlan = if ($schedulePlanLookup.ContainsKey($league)) { $schedulePlanLookup[$league] } else { $null }
        $leagueState = $schedulerLeaguesState[$league]
        $tier = if ($leaguePlan -and $leaguePlan.tier) { [string]$leaguePlan.tier } else { "off" }
        $cadenceMinutes = if ($leaguePlan -and $leaguePlan.cadence_minutes -ne $null) { [int]$leaguePlan.cadence_minutes } else { 0 }
        $activeFixtureCount = if ($leaguePlan -and $leaguePlan.active_fixture_count -ne $null) { [int]$leaguePlan.active_fixture_count } else { 0 }
        $nextKickoffUtc = if ($leaguePlan) { [string]$leaguePlan.next_kickoff_utc } else { "" }
        $lastSuccessAge = Get-IsoAgeMinutes $leagueState.last_successful_run_at
        $lastDetailAge = Get-IsoAgeMinutes $leagueState.last_detail_run_at
        $lastFailureAge = Get-IsoAgeMinutes $leagueState.last_failure_at
        $consecutiveFailures = if ($leagueState.consecutive_failures -ne $null) { [int]$leagueState.consecutive_failures } else { 0 }

        if (-not $forceRunAll -and ($tier -eq "off" -or $cadenceMinutes -le 0 -or $activeFixtureCount -le 0)) {
            $message = "Skip ${league}: no upcoming fixtures inside schedule window."
            Log $message
            Update-LeagueState -League $league -Tier $tier -Decision "off" -Message $message -NextKickoffUtc $nextKickoffUtc
            continue
        }

        if (-not $forceRunAll -and $consecutiveFailures -ge $failureThreshold -and $lastFailureAge -ne $null -and $lastFailureAge -lt $failureCooldownMinutes) {
            $cooldownRemaining = [Math]::Max(1, [int][Math]::Ceiling($failureCooldownMinutes - $lastFailureAge))
            $message = "Skip ${league}: cooldown active after $consecutiveFailures consecutive failures ($cooldownRemaining min remaining)."
            Log $message
            Update-LeagueState -League $league -Tier $tier -Decision "cooldown" -Message $message -NextKickoffUtc $nextKickoffUtc
            continue
        }

        if (-not $forceRunAll -and $lastSuccessAge -ne $null -and $lastSuccessAge -lt $cadenceMinutes) {
            $waitMinutes = [Math]::Max(1, [int][Math]::Ceiling($cadenceMinutes - $lastSuccessAge))
            $message = "Skip ${league}: $tier tier cadence ${cadenceMinutes}m not due yet ($waitMinutes min remaining)."
            Log $message
            Update-LeagueState -League $league -Tier $tier -Decision "waiting" -Message $message -NextKickoffUtc $nextKickoffUtc
            continue
        }

        $effectiveTier = if ($forceRunAll) { "manual" } else { $tier }
        $effectiveFixtureCount = if ($forceRunAll) { [Math]::Max($activeFixtureCount, 1) } else { $activeFixtureCount }
        $effectiveCadence = if ($forceRunAll) { 0 } else { $cadenceMinutes }
        Write-Status -State "running" -Message "Running $league ($effectiveTier tier, $effectiveFixtureCount fixture(s), cadence ${effectiveCadence}m)"
        Log "---- League: $league [$effectiveTier tier | $effectiveFixtureCount fixture(s) | cadence ${effectiveCadence}m] ----"
        $requiredLog = $requiredPlayerLogs[$league]
        if (-not [string]::IsNullOrWhiteSpace($requiredLog) -and -not (Test-Path $requiredLog)) {
            $message = "Skip ${league}: current player log missing ($requiredLog)"
            Log $message
            Update-LeagueState -League $league -Tier $effectiveTier -Decision "missing-data" -Message $message -NextKickoffUtc $nextKickoffUtc
            continue
        }
        & $pythonExe scripts\run-goalscorer-pipeline.py --league $league --live-only --fetch-lineups --fetch-odds-api --odds-api-bookmakers $oddsApiBooks --bookmaker $bookmaker --track-shadow 2>&1 | ForEach-Object { Log $_ }
        if ($LASTEXITCODE -ne 0) {
            $message = "goalscorer live poll failed for $league (exit $LASTEXITCODE)"
            Log "ERROR: $message"
            $warningMessages.Add($message) | Out-Null
            $failedLeagueCount++
            Update-LeagueState -League $league -Tier $tier -Decision "failed" -Message $message -NextKickoffUtc $nextKickoffUtc -ConsecutiveFailures ($consecutiveFailures + 1) -LastFailureAt ((Get-Date).ToUniversalTime().ToString("o"))
            Write-Status -State "running" -Message $message -ExitCode $LASTEXITCODE
            continue
        }

        $ranLeagueCount++
        $successfulRunAt = (Get-Date).ToUniversalTime().ToString("o")
        $runDetailTasks = $true
        if (-not $forceRunAll -and $tier -eq "hot" -and $lastDetailAge -ne $null -and $lastDetailAge -lt $detailCadenceHotMinutes) {
            $runDetailTasks = $false
        }
        $detailRunAt = $null

        if ($runDetailTasks) {
            $detailSucceeded = $true

            Log "---- League: $league live penalty review ----"
            & $pythonExe scripts\goalscorer-live-penalty-review.py --league $league --days-back 6 2>&1 | ForEach-Object { Log $_ }
            if ($LASTEXITCODE -ne 0) {
                $warning = "same-night penalty review failed for $league (exit $LASTEXITCODE)"
                $warningMessages.Add($warning) | Out-Null
                Log "WARNING: $warning"
                Write-Status -State "running" -Message $warning -ExitCode $LASTEXITCODE
                $detailSucceeded = $false
            }

            Log "---- League: $league penalty baseline evidence ----"
            & $pythonExe scripts\build-penalty-baseline-evidence.py --league $league 2>&1 | ForEach-Object { Log $_ }
            if ($LASTEXITCODE -ne 0) {
                $warning = "penalty baseline evidence build failed for $league (exit $LASTEXITCODE)"
                $warningMessages.Add($warning) | Out-Null
                Log "WARNING: $warning"
                Write-Status -State "running" -Message $warning -ExitCode $LASTEXITCODE
                $detailSucceeded = $false
            }

            if ($detailSucceeded) {
                $detailRunAt = (Get-Date).ToUniversalTime().ToString("o")
            }
        } else {
            Log "Skip detail scripts for ${league}: hot tier detail cooldown still active."
        }

        $message = if ($forceRunAll) {
            "Ran $league in manual force mode."
        } else {
            "Ran $league in $tier tier (cadence ${cadenceMinutes}m, fixtures $activeFixtureCount)."
        }
        Update-LeagueState -League $league -Tier $effectiveTier -Decision "ran" -Message $message -NextKickoffUtc $nextKickoffUtc -ConsecutiveFailures 0 -LastFailureAt "" -LastSuccessfulRunAt $successfulRunAt -LastDetailRunAt $detailRunAt
    }

    Save-SchedulerState -Reason "cycle"

    if ($ranLeagueCount -gt 0) {
        $currentLeague = "snapshot"
        Write-Status -State "running" -Message "Uploading hosted live snapshot"
        Log "---- Uploading hosted live snapshot ----"
        & $pythonExe scripts\goalscorer-live-snapshot.py --supabase 2>&1 | ForEach-Object { Log $_ }
        if ($LASTEXITCODE -ne 0) {
            $warning = "goalscorer live snapshot upload failed (exit $LASTEXITCODE)"
            $warningMessages.Add($warning) | Out-Null
            Log "WARNING: $warning"
        }
    } else {
        Log "Skip hosted live snapshot upload: no league pipelines ran this cycle."
    }

    $currentLeague = ""
    if ($ranLeagueCount -gt 0) {
        $lastSuccessfulFinishedAt = (Get-Date).ToUniversalTime().ToString("o")
        $finalMessage = if ($failedLeagueCount -gt 0) {
            "Goalscorer live poll finished with warnings ($ranLeagueCount ran, $failedLeagueCount failed)."
        } else {
            "Goalscorer live poll finished ($ranLeagueCount league(s) ran)."
        }
        Write-Status -State "idle" -Message $finalMessage
    } elseif ($failedLeagueCount -gt 0) {
        $finalMessage = "Goalscorer live poll failed ($failedLeagueCount league(s) failed, none completed)."
        Write-Status -State "failed" -Message $finalMessage -ExitCode 1
        Log "============================================"
        Log "  Goalscorer live poll failed at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
        Log "============================================"
        exit 1
    } else {
        $lastSuccessfulFinishedAt = (Get-Date).ToUniversalTime().ToString("o")
        Write-Status -State "skipped" -Message "Goalscorer live poll skipped: no leagues due in current cadence window."
    }
    Log "============================================"
    Log "  Goalscorer live poll finished at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    Log "============================================"
} catch {
    $currentLeague = if ([string]::IsNullOrWhiteSpace($currentLeague)) { "unknown" } else { $currentLeague }
    $message = $_.Exception.Message
    Log "FATAL: $message"
    Save-SchedulerState -Reason "fatal"
    Write-Status -State "failed" -Message $message -ExitCode 1
    exit 1
} finally {
    Exit-TaskLock $lockHandle
}
