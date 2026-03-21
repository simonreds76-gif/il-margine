# Il Margine - Goalscorer live polling task
# Purpose: refresh odds, fetch confirmed lineups, rerun live compare, log output.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

$dataDir = Join-Path $root "data\goalscorer"
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$logFile = Join-Path $dataDir "goalscorer-live.log"

function Log($msg) {
    $line = "$(Get-Date -Format 'HH:mm:ss') $msg"
    Write-Host $line
    Add-Content -Path $logFile -Value $line
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
$oddsApiBooks = if ([string]::IsNullOrWhiteSpace($env:GOALSCORER_ODDS_API_BOOKMAKERS)) { "Bet365,William Hill" } else { $env:GOALSCORER_ODDS_API_BOOKMAKERS }
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

Log "============================================"
Log "  Goalscorer live poll started at $timestamp"
Log "============================================"
Log "Python executable: $pythonExe"
Log "Bookmaker filter: $bookmaker"
Log "Odds API books:   $oddsApiBooks"
Log "Leagues:          $($leagues -join ', ')"

foreach ($league in $leagues) {
    Log "---- League: $league ----"
    $requiredLog = $requiredPlayerLogs[$league]
    if (-not [string]::IsNullOrWhiteSpace($requiredLog) -and -not (Test-Path $requiredLog)) {
        Log "SKIP: current player log missing for $league ($requiredLog)"
        continue
    }
    & $pythonExe scripts\run-goalscorer-pipeline.py --league $league --live-only --fetch-lineups --fetch-odds-api --odds-api-bookmakers $oddsApiBooks --bookmaker $bookmaker --track-shadow 2>&1 | ForEach-Object { Log $_ }
    if ($LASTEXITCODE -ne 0) {
        Log "ERROR: goalscorer live poll failed for $league (exit $LASTEXITCODE)"
        exit 1
    }

    Log "---- League: $league live penalty review ----"
    & $pythonExe scripts\goalscorer-live-penalty-review.py --league $league 2>&1 | ForEach-Object { Log $_ }
    if ($LASTEXITCODE -ne 0) {
        Log "WARNING: same-night penalty review failed for $league (exit $LASTEXITCODE)"
    }

    Log "---- League: $league penalty baseline evidence ----"
    & $pythonExe scripts\build-penalty-baseline-evidence.py --league $league 2>&1 | ForEach-Object { Log $_ }
    if ($LASTEXITCODE -ne 0) {
        Log "WARNING: penalty baseline evidence build failed for $league (exit $LASTEXITCODE)"
    }
}

Log "---- Uploading hosted live snapshot ----"
& $pythonExe scripts\goalscorer-live-snapshot.py --supabase 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "WARNING: goalscorer live snapshot upload failed (exit $LASTEXITCODE)"
}

Log "============================================"
Log "  Goalscorer live poll finished at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Log "============================================"
