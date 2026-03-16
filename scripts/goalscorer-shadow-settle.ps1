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
    @("serie-a", "epl", "la-liga", "bundesliga")
} else {
    $env:GOALSCORER_LEAGUES.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ }
}

$dataGlobs = @{
    "serie-a" = "data\goalscorer\serie-a-player-match-logs-*.csv"
    "epl" = "data\goalscorer\epl-player-match-logs-*.csv"
    "la-liga" = "data\goalscorer\la-liga-player-match-logs-*.csv"
    "bundesliga" = "data\goalscorer\bundesliga-player-match-logs-*.csv"
}

$shadowOutputs = @{
    "serie-a" = "data\goalscorer\goalscorer-shadow-signals.csv"
    "epl" = "data\goalscorer\epl-shadow-signals.csv"
    "la-liga" = "data\goalscorer\la-liga-shadow-signals.csv"
    "bundesliga" = "data\goalscorer\bundesliga-shadow-signals.csv"
}

$shadowSummaries = @{
    "serie-a" = "data\goalscorer\goalscorer-shadow-performance.txt"
    "epl" = "data\goalscorer\epl-shadow-performance.txt"
    "la-liga" = "data\goalscorer\la-liga-shadow-performance.txt"
    "bundesliga" = "data\goalscorer\bundesliga-shadow-performance.txt"
}

function Log($msg) {
    $line = "$(Get-Date -Format 'HH:mm:ss') $msg"
    Write-Host $line
    Add-Content -Path $logFile -Value $line
}

$today = Get-Date
$startYear = if ($today.Month -ge 7) { $today.Year } else { $today.Year - 1 }
$seasonLabel = "{0}-{1}" -f $startYear, ($startYear + 1)

Log "============================================"
Log "  Goalscorer shadow settlement started at $timestamp"
Log "============================================"
Log "Current season refresh: $seasonLabel"
Log "Leagues:               $($leagues -join ', ')"

& python scripts\understat-scrape-serie-a.py --league $leagues --season $seasonLabel --resume 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "ERROR: Understat refresh failed (exit $LASTEXITCODE)"
    exit 1
}

foreach ($league in $leagues) {
    Log "---- Settle league: $league ----"
    & python scripts\goalscorer-shadow-tracker.py `
        --settle-only `
        --output $shadowOutputs[$league] `
        --summary $shadowSummaries[$league] `
        --data $dataGlobs[$league] 2>&1 | ForEach-Object { Log $_ }
    if ($LASTEXITCODE -ne 0) {
        Log "ERROR: shadow settlement failed for $league (exit $LASTEXITCODE)"
        exit 1
    }
}

Log "============================================"
Log "  Goalscorer shadow settlement finished at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Log "============================================"
