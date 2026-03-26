# Il Margine - Goalscorer shadow settlement task
# Purpose: refresh current-season Understat logs, settle shadow picks, update summary.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

$dataDir = Join-Path $root "data\goalscorer"
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$logFile = Join-Path $dataDir "goalscorer-live.log"
$leagues = if ([string]::IsNullOrWhiteSpace($env:GOALSCORER_LEAGUES)) {
    @("serie-a", "epl", "la-liga", "bundesliga", "ligue-1")
} else {
    $env:GOALSCORER_LEAGUES.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ }
}

$dataGlobs = @{
    "serie-a" = "data\goalscorer\serie-a-player-match-logs-*.csv"
    "epl" = "data\goalscorer\epl-player-match-logs-*.csv"
    "la-liga" = "data\goalscorer\la-liga-player-match-logs-*.csv"
    "bundesliga" = "data\goalscorer\bundesliga-player-match-logs-*.csv"
    "ligue-1" = "data\goalscorer\ligue-1-player-match-logs-*.csv"
}

$shadowOutputs = @{
    "serie-a" = "data\goalscorer\goalscorer-shadow-signals.csv"
    "epl" = "data\goalscorer\epl-shadow-signals.csv"
    "la-liga" = "data\goalscorer\la-liga-shadow-signals.csv"
    "bundesliga" = "data\goalscorer\bundesliga-shadow-signals.csv"
    "ligue-1" = "data\goalscorer\ligue-1-shadow-signals.csv"
}

$shadowSummaries = @{
    "serie-a" = "data\goalscorer\goalscorer-shadow-performance.txt"
    "epl" = "data\goalscorer\epl-shadow-performance.txt"
    "la-liga" = "data\goalscorer\la-liga-shadow-performance.txt"
    "bundesliga" = "data\goalscorer\bundesliga-shadow-performance.txt"
    "ligue-1" = "data\goalscorer\ligue-1-shadow-performance.txt"
}

$penaltyContextCurrent = @{
    "serie-a" = "data\goalscorer\penalty-duty-context.json"
    "epl" = "data\goalscorer\epl\penalty-duty-context.json"
    "la-liga" = "data\goalscorer\la-liga\penalty-duty-context.json"
    "bundesliga" = "data\goalscorer\bundesliga\penalty-duty-context.json"
    "ligue-1" = "data\goalscorer\ligue-1\penalty-duty-context.json"
}

$penaltyContextHistory = @{
    "serie-a" = "data\goalscorer\live-history\penalty-duty-context-*.json"
    "epl" = "data\goalscorer\epl\live-history\penalty-duty-context-*.json"
    "la-liga" = "data\goalscorer\la-liga\live-history\penalty-duty-context-*.json"
    "bundesliga" = "data\goalscorer\bundesliga\live-history\penalty-duty-context-*.json"
    "ligue-1" = "data\goalscorer\ligue-1\live-history\penalty-duty-context-*.json"
}

$penaltyReviewOutputs = @{
    "serie-a" = "data\goalscorer\penalty-duty-review.csv"
    "epl" = "data\goalscorer\epl-penalty-duty-review.csv"
    "la-liga" = "data\goalscorer\la-liga-penalty-duty-review.csv"
    "bundesliga" = "data\goalscorer\bundesliga-penalty-duty-review.csv"
    "ligue-1" = "data\goalscorer\ligue-1-penalty-duty-review.csv"
}

$penaltyReviewJsonOutputs = @{
    "serie-a" = "data\goalscorer\penalty-duty-review.json"
    "epl" = "data\goalscorer\epl-penalty-duty-review.json"
    "la-liga" = "data\goalscorer\la-liga-penalty-duty-review.json"
    "bundesliga" = "data\goalscorer\bundesliga-penalty-duty-review.json"
    "ligue-1" = "data\goalscorer\ligue-1-penalty-duty-review.json"
}

$requiredPlayerLogs = @{
    "serie-a" = "data\goalscorer\serie-a-player-match-logs-2025-2026.csv"
    "epl" = "data\goalscorer\epl-player-match-logs-2025-2026.csv"
    "la-liga" = "data\goalscorer\la-liga-player-match-logs-2025-2026.csv"
    "bundesliga" = "data\goalscorer\bundesliga-player-match-logs-2025-2026.csv"
    "ligue-1" = "data\goalscorer\ligue-1-player-match-logs-2025-2026.csv"
}

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

    throw "Python executable not found for goalscorer shadow settlement."
}

$today = Get-Date
$startYear = if ($today.Month -ge 7) { $today.Year } else { $today.Year - 1 }
$seasonLabel = "{0}-{1}" -f $startYear, ($startYear + 1)
$pythonExe = Resolve-PythonExe

Log "============================================"
Log "  Goalscorer shadow settlement started at $timestamp"
Log "============================================"
Log "Python executable: $pythonExe"
Log "Current season refresh: $seasonLabel"
Log "Leagues:               $($leagues -join ', ')"

Log "---- Fetching recent FotMob match detail ----"
& $pythonExe scripts\fotmob-fetch-match-detail.py --league $leagues --days-back 3 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "ERROR: FotMob match detail fetch failed (exit $LASTEXITCODE)"
    exit 1
}

& $pythonExe scripts\understat-scrape-serie-a.py --league $leagues --season $seasonLabel --resume 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "ERROR: Understat refresh failed (exit $LASTEXITCODE)"
    exit 1
}

foreach ($league in $leagues) {
    Log "---- Settle league: $league ----"
    & $pythonExe scripts\goalscorer-settle.py `
        --league $league `
        --signals $shadowOutputs[$league] `
        --summary $shadowSummaries[$league] 2>&1 | ForEach-Object { Log $_ }
    if ($LASTEXITCODE -ne 0) {
        Log "ERROR: FotMob shadow settlement failed for $league (exit $LASTEXITCODE)"
        exit 1
    }

    $requiredLog = $requiredPlayerLogs[$league]
    if (-not [string]::IsNullOrWhiteSpace($requiredLog) -and -not (Test-Path $requiredLog)) {
        Log "SKIP: current player log missing for $league ($requiredLog) - penalty review/evidence only"
        continue
    }

    $contextArgs = @(
        $penaltyContextCurrent[$league],
        $penaltyContextHistory[$league]
    )
    & $pythonExe scripts\goalscorer-penalty-review.py `
        --context $contextArgs `
        --data $dataGlobs[$league] `
        --days-back 21 `
        --output $penaltyReviewOutputs[$league] `
        --json-output $penaltyReviewJsonOutputs[$league] 2>&1 | ForEach-Object { Log $_ }
    if ($LASTEXITCODE -ne 0) {
        Log "ERROR: penalty-duty review failed for $league (exit $LASTEXITCODE)"
        exit 1
    }

    & $pythonExe scripts\build-penalty-baseline-evidence.py --league $league 2>&1 | ForEach-Object { Log $_ }
    if ($LASTEXITCODE -ne 0) {
        Log "ERROR: penalty baseline evidence build failed for $league (exit $LASTEXITCODE)"
        exit 1
    }
}

Log "---- Uploading hosted live snapshot ----"
& $pythonExe scripts\goalscorer-live-snapshot.py --supabase 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "ERROR: goalscorer live snapshot upload failed after settlement (exit $LASTEXITCODE)"
    exit 1
}

Log "============================================"
Log "  Goalscorer shadow settlement finished at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Log "============================================"
