# Il Margine - Goalscorer shadow settlement task
# Purpose: refresh current-season Understat logs, settle shadow picks, update summary.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root
. (Join-Path $root "scripts\use-local-python.ps1") -RepoRoot $root
. (Join-Path $root "scripts\task-lock.ps1")

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

$publicOutputs = @{
    "serie-a" = "data\goalscorer\goalscorer-public-signals.csv"
    "epl" = "data\goalscorer\epl-public-signals.csv"
    "la-liga" = "data\goalscorer\la-liga-public-signals.csv"
    "bundesliga" = "data\goalscorer\bundesliga-public-signals.csv"
    "ligue-1" = "data\goalscorer\ligue-1-public-signals.csv"
}

$publicSummaries = @{
    "serie-a" = "data\goalscorer\goalscorer-public-performance.txt"
    "epl" = "data\goalscorer\epl-public-performance.txt"
    "la-liga" = "data\goalscorer\la-liga-public-performance.txt"
    "bundesliga" = "data\goalscorer\bundesliga-public-performance.txt"
    "ligue-1" = "data\goalscorer\ligue-1-public-performance.txt"
}

$fairOddsLabOutputs = @{
    "serie-a" = "data\goalscorer\fair-odds-lab-serie-a-signals.csv"
    "epl" = "data\goalscorer\fair-odds-lab-epl-signals.csv"
    "la-liga" = "data\goalscorer\fair-odds-lab-la-liga-signals.csv"
    "bundesliga" = "data\goalscorer\fair-odds-lab-bundesliga-signals.csv"
    "ligue-1" = "data\goalscorer\fair-odds-lab-ligue-1-signals.csv"
}

$fairOddsLabSummaries = @{
    "serie-a" = "data\goalscorer\fair-odds-lab-serie-a-performance.txt"
    "epl" = "data\goalscorer\fair-odds-lab-epl-performance.txt"
    "la-liga" = "data\goalscorer\fair-odds-lab-la-liga-performance.txt"
    "bundesliga" = "data\goalscorer\fair-odds-lab-bundesliga-performance.txt"
    "ligue-1" = "data\goalscorer\fair-odds-lab-ligue-1-performance.txt"
}

$fairOddsLabQuarantineOutputs = @{
    "serie-a" = "data\goalscorer\fair-odds-lab-serie-a-quarantine.csv"
    "epl" = "data\goalscorer\fair-odds-lab-epl-quarantine.csv"
    "la-liga" = "data\goalscorer\fair-odds-lab-la-liga-quarantine.csv"
    "bundesliga" = "data\goalscorer\fair-odds-lab-bundesliga-quarantine.csv"
    "ligue-1" = "data\goalscorer\fair-odds-lab-ligue-1-quarantine.csv"
}

$fairOddsLabQuarantineSummaries = @{
    "serie-a" = "data\goalscorer\fair-odds-lab-serie-a-quarantine-performance.txt"
    "epl" = "data\goalscorer\fair-odds-lab-epl-quarantine-performance.txt"
    "la-liga" = "data\goalscorer\fair-odds-lab-la-liga-quarantine-performance.txt"
    "bundesliga" = "data\goalscorer\fair-odds-lab-bundesliga-quarantine-performance.txt"
    "ligue-1" = "data\goalscorer\fair-odds-lab-ligue-1-quarantine-performance.txt"
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

$understatMaxAgeHours = if ([string]::IsNullOrWhiteSpace($env:GOALSCORER_UNDERSTAT_MAX_AGE_HOURS)) {
    18
} else {
    [double]$env:GOALSCORER_UNDERSTAT_MAX_AGE_HOURS
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

function Get-UnderstatRefreshLeagues {
    param(
        [string[]]$LeagueNames,
        [hashtable]$RequiredLogs,
        [double]$MaxAgeHours
    )

    $refreshLeagues = New-Object System.Collections.Generic.List[string]
    $now = Get-Date
    foreach ($league in $LeagueNames) {
        $requiredLog = $RequiredLogs[$league]
        if ([string]::IsNullOrWhiteSpace($requiredLog)) {
            $refreshLeagues.Add($league) | Out-Null
            continue
        }

        if (-not (Test-Path $requiredLog)) {
            Log "Understat refresh required: missing current player log for $league ($requiredLog)"
            $refreshLeagues.Add($league) | Out-Null
            continue
        }

        $ageHours = ($now - (Get-Item $requiredLog).LastWriteTime).TotalHours
        if ($ageHours -ge $MaxAgeHours) {
            Log ("Understat refresh required: {0} player log is {1:N1}h old (threshold {2:N1}h)" -f $league, $ageHours, $MaxAgeHours)
            $refreshLeagues.Add($league) | Out-Null
        }
    }

    return @($refreshLeagues)
}

$today = Get-Date
$startYear = if ($today.Month -ge 7) { $today.Year } else { $today.Year - 1 }
$seasonLabel = "{0}-{1}" -f $startYear, ($startYear + 1)
$pythonExe = Resolve-PythonExe

$lockHandle = Enter-TaskLock -LockName "goalscorer-automation" -RootPath $root
if ($null -eq $lockHandle) {
    Log "Another goalscorer automation run is already active; skipping settlement."
    exit 0
}

try {
    Log "============================================"
    Log "  Goalscorer shadow settlement started at $timestamp"
    Log "============================================"
    Log "Python executable: $pythonExe"
    Log "Current season refresh: $seasonLabel"
    Log "Leagues:               $($leagues -join ', ')"

    Log "---- Fetching recent FotMob match detail ----"
    & $pythonExe scripts\fotmob-fetch-match-detail.py --league $leagues --days-back 3 2>&1 | ForEach-Object { Log $_ }
    if ($LASTEXITCODE -ne 0) {
        Log "WARNING: FotMob match detail fetch failed (exit $LASTEXITCODE) - continuing with existing local detail."
    }

    $understatRefreshLeagues = Get-UnderstatRefreshLeagues -LeagueNames $leagues -RequiredLogs $requiredPlayerLogs -MaxAgeHours $understatMaxAgeHours
    if ($understatRefreshLeagues.Count -gt 0) {
        Log ("Refreshing Understat only for stale leagues: {0}" -f ($understatRefreshLeagues -join ", "))
        & $pythonExe scripts\understat-scrape-serie-a.py --league $understatRefreshLeagues --season $seasonLabel --resume 2>&1 | ForEach-Object { Log $_ }
        if ($LASTEXITCODE -ne 0) {
            Log "WARNING: Understat refresh failed (exit $LASTEXITCODE) - continuing with existing player logs."
        }
    } else {
        Log ("Skip Understat refresh: current-season player logs are fresh (< {0:N1}h)." -f $understatMaxAgeHours)
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

        & $pythonExe scripts\goalscorer-settle.py `
            --league $league `
            --signals $publicOutputs[$league] `
            --summary $publicSummaries[$league] 2>&1 | ForEach-Object { Log $_ }
        if ($LASTEXITCODE -ne 0) {
            Log "ERROR: FotMob public settlement failed for $league (exit $LASTEXITCODE)"
            exit 1
        }

        Log "---- Settle league: $league (Fair Odds Lab exposure) ----"
        & $pythonExe scripts\goalscorer-settle.py `
            --league $league `
            --signals $fairOddsLabOutputs[$league] `
            --summary $fairOddsLabSummaries[$league] 2>&1 | ForEach-Object { Log $_ }
        if ($LASTEXITCODE -ne 0) {
            Log "ERROR: Fair Odds Lab exposure settlement failed for $league (exit $LASTEXITCODE)"
            exit 1
        }

        $quarantineSignals = $fairOddsLabQuarantineOutputs[$league]
        if (Test-Path $quarantineSignals) {
            Log "---- Settle league: $league (Fair Odds Lab extreme-gap quarantine) ----"
            & $pythonExe scripts\goalscorer-settle.py `
                --league $league `
                --signals $quarantineSignals `
                --summary $fairOddsLabQuarantineSummaries[$league] 2>&1 | ForEach-Object { Log $_ }
            if ($LASTEXITCODE -ne 0) {
                Log "ERROR: Fair Odds Lab quarantine settlement failed for $league (exit $LASTEXITCODE)"
                exit 1
            }
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
            --allow-empty-context `
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
        Log "WARNING: goalscorer live snapshot upload failed after settlement (exit $LASTEXITCODE) - local settlement outputs were still written."
    }

    Log "============================================"
    Log "  Goalscorer shadow settlement finished at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    Log "============================================"
}
finally {
    Exit-TaskLock $lockHandle
}
