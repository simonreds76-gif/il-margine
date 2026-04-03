# Il Margine - Goalscorer live polling task
# Purpose: refresh odds, fetch confirmed lineups, rerun live compare, log output.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root
. (Join-Path $root "scripts\task-lock.ps1")

$dataDir = Join-Path $root "data\goalscorer"
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$logFile = Join-Path $dataDir "goalscorer-live.log"
$statusFile = Join-Path $dataDir "goalscorer-live-status.json"
$runStartedAtUtc = (Get-Date).ToUniversalTime().ToString("o")
$lastSuccessfulFinishedAt = $null
$currentLeague = ""
$warningMessages = New-Object System.Collections.Generic.List[string]

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

$bookmaker = if ([string]::IsNullOrWhiteSpace($env:GOALSCORER_BOOKMAKER)) { "Bet365" } else { $env:GOALSCORER_BOOKMAKER }
$oddsApiBooks = if ([string]::IsNullOrWhiteSpace($env:GOALSCORER_ODDS_API_BOOKMAKERS)) { "Bet365,Ladbrokes" } else { $env:GOALSCORER_ODDS_API_BOOKMAKERS }
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
    Write-Status -State "running" -Message "Goalscorer live poll started"

    foreach ($league in $leagues) {
        $currentLeague = $league
        Write-Status -State "running" -Message "Running league pipeline for $league"
        Log "---- League: $league ----"
        $requiredLog = $requiredPlayerLogs[$league]
        if (-not [string]::IsNullOrWhiteSpace($requiredLog) -and -not (Test-Path $requiredLog)) {
            Log "SKIP: current player log missing for $league ($requiredLog)"
            continue
        }
        & $pythonExe scripts\run-goalscorer-pipeline.py --league $league --live-only --fetch-lineups --fetch-odds-api --odds-api-bookmakers $oddsApiBooks --bookmaker $bookmaker --track-shadow 2>&1 | ForEach-Object { Log $_ }
        if ($LASTEXITCODE -ne 0) {
            $message = "goalscorer live poll failed for $league (exit $LASTEXITCODE)"
            Log "ERROR: $message"
            Write-Status -State "failed" -Message $message -ExitCode $LASTEXITCODE
            exit 1
        }

        Log "---- League: $league live penalty review ----"
        & $pythonExe scripts\goalscorer-live-penalty-review.py --league $league --days-back 6 2>&1 | ForEach-Object { Log $_ }
        if ($LASTEXITCODE -ne 0) {
            $warning = "same-night penalty review failed for $league (exit $LASTEXITCODE)"
            $warningMessages.Add($warning) | Out-Null
            Log "WARNING: $warning"
            Write-Status -State "running" -Message $warning -ExitCode $LASTEXITCODE
        }

        Log "---- League: $league penalty baseline evidence ----"
        & $pythonExe scripts\build-penalty-baseline-evidence.py --league $league 2>&1 | ForEach-Object { Log $_ }
        if ($LASTEXITCODE -ne 0) {
            $warning = "penalty baseline evidence build failed for $league (exit $LASTEXITCODE)"
            $warningMessages.Add($warning) | Out-Null
            Log "WARNING: $warning"
            Write-Status -State "running" -Message $warning -ExitCode $LASTEXITCODE
        }
    }

    $currentLeague = "snapshot"
    Write-Status -State "running" -Message "Uploading hosted live snapshot"
    Log "---- Uploading hosted live snapshot ----"
    & $pythonExe scripts\goalscorer-live-snapshot.py --supabase 2>&1 | ForEach-Object { Log $_ }
    if ($LASTEXITCODE -ne 0) {
        $warning = "goalscorer live snapshot upload failed (exit $LASTEXITCODE)"
        $warningMessages.Add($warning) | Out-Null
        Log "WARNING: $warning"
    }

    $currentLeague = ""
    $lastSuccessfulFinishedAt = (Get-Date).ToUniversalTime().ToString("o")
    Write-Status -State "idle" -Message "Goalscorer live poll finished"
    Log "============================================"
    Log "  Goalscorer live poll finished at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    Log "============================================"
} catch {
    $currentLeague = if ([string]::IsNullOrWhiteSpace($currentLeague)) { "unknown" } else { $currentLeague }
    $message = $_.Exception.Message
    Log "FATAL: $message"
    Write-Status -State "failed" -Message $message -ExitCode 1
    exit 1
} finally {
    Exit-TaskLock $lockHandle
}
