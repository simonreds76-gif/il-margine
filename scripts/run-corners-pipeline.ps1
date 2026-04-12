<#
.SYNOPSIS
    Automated team props pipeline: corners + team total shots in one run.

.DESCRIPTION
    Run this script manually or via Task Scheduler. It will:
    1. Run corners model + fetch corner O/U odds + generate value shortlist
    2. Run team shots model + scrape team total shots (Odds-API.io / BetsAPI)
    3. Archive odds + compare model vs book + shadow track + settle
    4. Log everything with timestamps and emit a pipeline status JSON

    The Odds API (the-odds-api.com) does not offer team total shots; those
    lines come from Odds-API.io or BetsAPI when keys are set in .env.local.

.EXAMPLE
    .\scripts\run-corners-pipeline.ps1
    .\scripts\run-corners-pipeline.ps1 -DaysAhead 3 -LeaguesOnly "epl,serie-a"
#>

param(
    [string]$LeaguesOnly = "",
    [int]$DaysAhead = 7,
    [double]$MinEdge = 0.10,
    [string]$Regions = "eu",
    [double]$ShotsMinEdge = 0.05,
    [switch]$SkipTeamShots
)

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$runStartedAtUtc = (Get-Date).ToUniversalTime().ToString("o")
$logDir = Join-Path $root "data\shortlist"
if (!(Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
$logFile = Join-Path $logDir "pipeline-log.txt"
$statusFile = Join-Path $logDir "team-props-status.json"
$latestShortlistPath = Join-Path $logDir "shortlist-latest.txt"
$latestValueBetsPath = Join-Path $logDir "value-bets-latest.csv"
$latestSignalsPath = Join-Path $logDir "signals-latest.csv"
$warnings = New-Object System.Collections.Generic.List[string]
$criticalFailures = New-Object System.Collections.Generic.List[string]
$currentStep = ""
$lastSuccessfulFinishedAt = $null

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

function Log($msg) {
    $line = "[$(Get-Date -Format 'HH:mm:ss')] $msg"
    Write-Host $line
    $utf8NoBom = [System.Text.UTF8Encoding]::new($false)
    [System.IO.File]::AppendAllText($logFile, $line + [Environment]::NewLine, $utf8NoBom)
}

function Add-WarningMessage([string]$message) {
    $warnings.Add($message) | Out-Null
    Log "  [WARN] $message"
}

function Add-CriticalFailure([string]$message) {
    $criticalFailures.Add($message) | Out-Null
    Log "  [ERROR] $message"
}

function Get-LatestMatchingFile([string]$glob) {
    return Get-ChildItem $glob -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -notmatch "-latest\." } |
        Sort-Object Name |
        Select-Object -Last 1
}

function Sync-LatestArtifact([string]$glob, [string]$targetPath) {
    $latest = Get-LatestMatchingFile $glob
    if ($null -eq $latest) {
        return $null
    }
    try {
        $sourcePath = [System.IO.Path]::GetFullPath($latest.FullName)
        $destPath = [System.IO.Path]::GetFullPath($targetPath)
        if ($sourcePath -eq $destPath) {
            return $latest
        }
    } catch {
        # Fall through to the copy; path normalization failing is non-fatal here.
    }
    Copy-Item -Path $latest.FullName -Destination $targetPath -Force
    return $latest
}

function Build-ArtifactsState {
    $artifacts = [ordered]@{}

    foreach ($entry in @(
        @{ Name = "shortlist_latest"; Path = $latestShortlistPath },
        @{ Name = "value_bets_latest"; Path = $latestValueBetsPath },
        @{ Name = "signals_latest"; Path = $latestSignalsPath },
        @{ Name = "pipeline_log"; Path = $logFile },
        @{ Name = "team_shots_predictions"; Path = (Join-Path $root "data\team-shots\team-shots-predictions.csv") },
        @{ Name = "team_shots_comparison"; Path = (Join-Path $root "data\team-shots\team-shots-comparison.csv") },
        @{ Name = "team_shots_upcoming"; Path = (Join-Path $root "data\team-shots\team-shots-upcoming.csv") }
    )) {
        $exists = Test-Path $entry.Path
        $artifacts[$entry.Name] = [ordered]@{
            path = $entry.Path
            exists = $exists
            updated_at = if ($exists) { (Get-Item $entry.Path).LastWriteTimeUtc.ToString("o") } else { $null }
        }
    }

    return $artifacts
}

function Write-Status {
    param(
        [string]$State,
        [string]$Message,
        [int]$ExitCode = 0,
        [hashtable]$Artifacts = @{}
    )

    $nowUtc = (Get-Date).ToUniversalTime().ToString("o")
    $payload = [ordered]@{
        pipeline = "team-props"
        state = $State
        updated_at = $nowUtc
        last_started_at = $runStartedAtUtc
        last_finished_at = if ($State -eq "running") { $null } else { $nowUtc }
        last_successful_finished_at = $lastSuccessfulFinishedAt
        current_step = $currentStep
        message = $Message
        warnings = @($warnings)
        critical_failures = @($criticalFailures)
        last_exit_code = $ExitCode
        inputs = [ordered]@{
            leagues_only = $LeaguesOnly
            days_ahead = $DaysAhead
            min_edge = $MinEdge
            shots_min_edge = $ShotsMinEdge
            regions = $Regions
        }
        artifacts = $Artifacts
    }

    ($payload | ConvertTo-Json -Depth 6) | Set-Content -Path $statusFile -Encoding UTF8
}

$previousStatus = Read-JsonFile $statusFile
if ($previousStatus -and $previousStatus.last_successful_finished_at) {
    $lastSuccessfulFinishedAt = [string]$previousStatus.last_successful_finished_at
}

Write-Status -State "running" -Message "Team props pipeline started"

Log "=========================================="
Log "  TEAM PROPS PIPELINE -- $timestamp"
Log "  (Corners + Team Total Shots)"
Log "=========================================="

try {
    # ============================================================
    # PART 1: CORNERS
    # ============================================================
    Log ""
    Log "--- CORNERS ---"

    $cornersDir = Join-Path $root "data\corners-ou"
    $cornersHistoryDir = Join-Path $cornersDir "historical"
    New-Item -ItemType Directory -Force -Path $cornersDir | Out-Null
    New-Item -ItemType Directory -Force -Path $cornersHistoryDir | Out-Null

    $cornersLeagues = if ($LeaguesOnly) {
        $LeaguesOnly.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ }
    } else {
        @("epl", "serie-a", "la-liga", "bundesliga", "ligue-1")
    }
    $nowLocal = Get-Date
    $currentSeason = if ($nowLocal.Month -ge 8) { $nowLocal.Year } else { $nowLocal.Year - 1 }
    $hadCornersHistory = Test-Path (Join-Path $cornersHistoryDir "all-historical-matches.csv")
    $historyFiles = @(Get-ChildItem $cornersHistoryDir -Filter "*.csv" -ErrorAction SilentlyContinue | Where-Object { $_.Name -ne "all-historical-matches.csv" })
    $historySeasons = if ($hadCornersHistory -and $historyFiles.Count -gt 0) {
        @($currentSeason)
    } else {
        2014..$currentSeason
    }

    $currentStep = "corners-history"
    Write-Status -State "running" -Message "Refreshing corners historical data" -Artifacts (Build-ArtifactsState)
    if ($historySeasons.Count -gt 1) {
        Log "Step 1a: Bootstrapping isolated corners historical base ($($historySeasons[0])-$($historySeasons[-1]))..."
    } else {
        Log "Step 1a: Refreshing corners current-season history..."
    }
    $fdArgs = @("scripts/footballdata-download-historical.py", "--leagues") + $cornersLeagues + @("--seasons") + ($historySeasons | ForEach-Object { "$_" }) + @("--out-dir", $cornersHistoryDir, "--overwrite")
    $fdResult = & python @fdArgs 2>&1
    if ($LASTEXITCODE -ne 0) {
        if (-not $hadCornersHistory) {
            Add-CriticalFailure "Corners historical refresh returned exit code $LASTEXITCODE with no isolated history base available."
        } else {
            Add-WarningMessage "Corners historical refresh returned exit code $LASTEXITCODE; using existing isolated history base."
        }
        $fdResult | ForEach-Object { Log "  $_" }
    } else {
        Log "  Corners historical refresh complete"
    }

    $currentStep = "corners-model"
    Write-Status -State "running" -Message "Running corners model" -Artifacts (Build-ArtifactsState)
    Log "Step 1b: Running corners model..."
    $modelResult = & python scripts/corners-ou-model.py 2>&1
    if ($LASTEXITCODE -ne 0) {
        Add-CriticalFailure "Corners model returned exit code $LASTEXITCODE"
        $modelResult | ForEach-Object { Log "  $_" }
    } else {
        $predLine = ($modelResult | Select-String "predictions generated" | Select-Object -Last 1)
        if ($predLine) { Log "  $predLine" }
    }

    $currentStep = "corners-calibration"
    Write-Status -State "running" -Message "Fitting corners calibration" -Artifacts (Build-ArtifactsState)
    Log "Step 1c: Fitting Platt calibration..."
    $calibResult = & python scripts/corners-fit-calibration.py 2>&1
    if ($LASTEXITCODE -ne 0) {
        Add-WarningMessage "Corners calibration fit failed (exit $LASTEXITCODE); shortlist will use raw probabilities."
    } else {
        $calibLine = ($calibResult | Select-String "Params written" | Select-Object -Last 1)
        if ($calibLine) { Log "  $calibLine" }
    }

    $currentStep = "corners-shortlist"
    Write-Status -State "running" -Message "Generating corners shortlist" -Artifacts (Build-ArtifactsState)
    Log "Step 1d: Fetching corner odds and generating shortlist..."
    $shortlistArgs = @("scripts/matchday-shortlist.py", "--all-leagues", "--min-edge", $MinEdge, "--days-ahead", $DaysAhead, "--regions", $Regions)
    if ($LeaguesOnly) {
        $shortlistArgs = @("scripts/matchday-shortlist.py", "--league", $LeaguesOnly.Split(",")[0], "--min-edge", $MinEdge, "--days-ahead", $DaysAhead, "--regions", $Regions)
    }
    $shortlistResult = & python @shortlistArgs 2>&1
    $betsLine = ($shortlistResult | Select-String "Total bets:" | Select-Object -Last 1)
    $creditsLine = ($shortlistResult | Select-String "credits remaining" | Select-Object -Last 1)
    if ($betsLine) { Log "  $betsLine" }
    if ($creditsLine) { Log "  $creditsLine" }
    if ($LASTEXITCODE -ne 0) {
        Add-CriticalFailure "Corners shortlist returned exit code $LASTEXITCODE"
        $shortlistResult | ForEach-Object { Log "  $_" }
    }

    $currentStep = "corners-settle"
    Write-Status -State "running" -Message "Settling corners shortlist" -Artifacts (Build-ArtifactsState)
    Log "Step 1e: Settling previous corner bets..."
    $settleResult = & python scripts/shortlist-settle.py 2>&1
    $settleExitCode = $LASTEXITCODE
    $settleLine = ($settleResult | Select-String "Settled:" | Select-Object -Last 1)
    if ($settleLine) {
        Log "  $settleLine"
    } else {
        Log "  No previous corner bets to settle"
    }
    $noCornersToSettle = ($settleResult | Select-String "No previous corner bets to settle" | Select-Object -First 1)
    if ($settleExitCode -ne 0 -and -not $noCornersToSettle) {
        Add-WarningMessage "Corners settlement returned exit code $settleExitCode."
    }

    if (-not $SkipTeamShots) {
        # ============================================================
        # PART 2: TEAM TOTAL SHOTS
        # ============================================================
        Log ""
        Log "--- TEAM TOTAL SHOTS ---"

        $dataDir = Join-Path $root "data\team-shots"
        New-Item -ItemType Directory -Force -Path $dataDir | Out-Null
        New-Item -ItemType Directory -Force -Path (Join-Path $dataDir "shadow") | Out-Null
        New-Item -ItemType Directory -Force -Path (Join-Path $dataDir "inbox") | Out-Null

        $teamShotsLeagues = if ($LeaguesOnly) {
            $LeaguesOnly.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ }
        } else {
            @("epl", "serie-a", "la-liga", "bundesliga", "ligue-1")
        }
        $nowLocal = Get-Date
        $currentSeason = if ($nowLocal.Month -ge 8) { $nowLocal.Year } else { $nowLocal.Year - 1 }
        $leagueArgs = @()
        foreach ($leagueKey in $teamShotsLeagues) {
            $leagueArgs += @("--leagues", $leagueKey)
        }

        $currentStep = "team-shots-history"
        Write-Status -State "running" -Message "Refreshing team shots historical data" -Artifacts (Build-ArtifactsState)
        Log "Step 2a: Refreshing current season shot history..."
        try {
            $fdArgs = @("scripts/footballdata-download-historical.py") + $leagueArgs + @("--seasons", $currentSeason, "--overwrite")
            $fdResult = & python @fdArgs 2>&1
            if ($LASTEXITCODE -ne 0) {
                Add-WarningMessage "Football-Data refresh returned exit code $LASTEXITCODE."
                $fdResult | ForEach-Object { Log "  $_" }
            } else {
                Log "  Football-Data refresh complete"
            }

            $fbrefArgs = @("scripts/fbref-download-shooting.py") + $leagueArgs + @("--seasons", $currentSeason)
            $fbrefResult = & python @fbrefArgs 2>&1
            if ($LASTEXITCODE -ne 0) {
                Add-WarningMessage "FBRef/Understat refresh returned exit code $LASTEXITCODE."
                $fbrefResult | ForEach-Object { Log "  $_" }
            } else {
                Log "  FBRef/Understat refresh complete"
            }
        } catch {
            Add-WarningMessage "Team shots historical refresh threw an exception: $_"
        }

        $currentStep = "team-shots-model"
        Write-Status -State "running" -Message "Running team shots model" -Artifacts (Build-ArtifactsState)
        Log "Step 2b: Running team shots model..."
        try {
            $shotsModelResult = & python scripts/team-shots-model.py 2>&1
            if ($LASTEXITCODE -ne 0) {
                Add-CriticalFailure "Team shots model returned exit code $LASTEXITCODE"
                $shotsModelResult | ForEach-Object { Log "  $_" }
            } else {
                $shotsLine = ($shotsModelResult | Select-String "predictions generated" | Select-Object -Last 1)
                if ($shotsLine) { Log "  $shotsLine" } else { Log "  Model complete" }
            }
        } catch {
            Add-CriticalFailure "Team shots model threw an exception: $_"
        }

        $currentStep = "team-shots-calibration"
        Write-Status -State "running" -Message "Fitting team shots calibration" -Artifacts (Build-ArtifactsState)
        Log "Step 2c: Fitting team shots calibration..."
        try {
            $calibResult = & python scripts/team-shots-fit-calibration.py 2>&1
            if ($LASTEXITCODE -ne 0) {
                Add-WarningMessage "Team shots calibration returned exit code $LASTEXITCODE."
                $calibResult | ForEach-Object { Log "  $_" }
            } else {
                $calibLine = ($calibResult | Select-String "Params written" | Select-Object -Last 1)
                if ($calibLine) { Log "  $calibLine" } else { Log "  Calibration complete" }
            }
        } catch {
            Add-WarningMessage "Team shots calibration threw an exception: $_"
        }

        $currentStep = "team-shots-upcoming"
        Write-Status -State "running" -Message "Writing upcoming team shots fixtures" -Artifacts (Build-ArtifactsState)
        Log "Step 2d: Writing upcoming fixture Lambda (The Odds API + model)..."
        try {
            $upcomingResult = & python scripts/team_shots_upcoming.py --days-ahead $DaysAhead 2>&1
            if ($LASTEXITCODE -ne 0) {
                Add-WarningMessage "Team shots upcoming returned exit code $LASTEXITCODE."
                $upcomingResult | ForEach-Object { Log "  $_" }
            } else {
                $upcomingLine = ($upcomingResult | Select-String "Wrote \d+ upcoming rows" | Select-Object -Last 1)
                if ($upcomingLine) { Log "  $upcomingLine" } else { $upcomingResult | ForEach-Object { Log "  $_" } }
            }
        } catch {
            Add-WarningMessage "Team shots upcoming threw an exception: $_"
        }

        $currentStep = "team-shots-scrape"
        Write-Status -State "running" -Message "Scraping team shots odds" -Artifacts (Build-ArtifactsState)
        Log "Step 2e: Scraping team total shots odds (Odds-API.io / BetsAPI)..."
        $shotsArgs = @("scripts/team-shots-scrape-odds.py", "--all-leagues", "--days-ahead", $DaysAhead)
        try {
            $scrapeResult = & python @shotsArgs 2>&1
            if ($LASTEXITCODE -ne 0) {
                Add-WarningMessage "Team shots scrape returned exit code $LASTEXITCODE."
                $scrapeResult | ForEach-Object { Log "  $_" }
            } else {
                $totalLine = ($scrapeResult | Select-String "Total team shots rows written:" | Select-Object -Last 1)
                if ($totalLine) { Log "  $totalLine" }
            }
        } catch {
            Add-WarningMessage "Team shots scrape threw an exception: $_"
        }

        $currentStep = "team-shots-archive"
        Write-Status -State "running" -Message "Archiving team shots odds" -Artifacts (Build-ArtifactsState)
        Log "Step 2f: Archiving odds..."
        try {
            & python scripts/team-shots-odds-archive.py 2>&1 | ForEach-Object { Log "  $_" }
            if ($LASTEXITCODE -ne 0) {
                Add-WarningMessage "Team shots odds archive returned exit code $LASTEXITCODE."
            }
        } catch {
            Add-WarningMessage "Odds archive failed: $_"
        }

        $currentStep = "team-shots-compare"
        Write-Status -State "running" -Message "Comparing team shots model vs bookmaker" -Artifacts (Build-ArtifactsState)
        Log "Step 2g: Comparing model vs bookmaker..."
        try {
            & python scripts/team-shots-compare.py --min-edge $ShotsMinEdge 2>&1 | ForEach-Object { Log "  $_" }
            if ($LASTEXITCODE -ne 0) {
                Add-WarningMessage "Team shots comparison returned exit code $LASTEXITCODE."
            }
        } catch {
            Add-WarningMessage "Comparison failed: $_"
        }

        $currentStep = "team-shots-shadow"
        Write-Status -State "running" -Message "Tracking team shots shadow signals" -Artifacts (Build-ArtifactsState)
        Log "Step 2h: Tracking shadow signals..."
        try {
            & python scripts/team-shots-shadow-tracker.py --min-edge $ShotsMinEdge 2>&1 | ForEach-Object { Log "  $_" }
            if ($LASTEXITCODE -ne 0) {
                Add-WarningMessage "Team shots shadow tracking returned exit code $LASTEXITCODE."
            }
        } catch {
            Add-WarningMessage "Shadow tracking failed: $_"
        }

        $currentStep = "team-shots-settle"
        Write-Status -State "running" -Message "Settling pending team shots signals" -Artifacts (Build-ArtifactsState)
        Log "Step 2i: Settling pending shot signals..."
        try {
            & python scripts/team-shots-settle.py 2>&1 | ForEach-Object { Log "  $_" }
            if ($LASTEXITCODE -ne 0) {
                Add-WarningMessage "Team shots settlement returned exit code $LASTEXITCODE."
            }
        } catch {
            Add-WarningMessage "Shot settlement failed: $_"
        }
    } else {
        Log ""
        Log "--- TEAM TOTAL SHOTS ---"
        Log "Skipped (SkipTeamShots switch enabled)"
    }

    $currentStep = "artifacts"
    Sync-LatestArtifact -glob (Join-Path $logDir "shortlist-*.txt") -targetPath $latestShortlistPath | Out-Null
    Sync-LatestArtifact -glob (Join-Path $logDir "value-bets-*.csv") -targetPath $latestValueBetsPath | Out-Null
    Sync-LatestArtifact -glob (Join-Path $logDir "signals-*.csv") -targetPath $latestSignalsPath | Out-Null

    $artifacts = Build-ArtifactsState

    Log ""
    Log "Pipeline complete. Check:"
    Log "  Corners shortlist: http://localhost:3000/model-monitor/corners"
    Log "  Team shots:        http://localhost:3000/model-monitor/team-shots"
    Log "  Files:             data/shortlist/ + data/team-shots/"
    Log "=========================================="

    $currentStep = ""
    if ($criticalFailures.Count -eq 0) {
        $lastSuccessfulFinishedAt = (Get-Date).ToUniversalTime().ToString("o")
    }

    if ($criticalFailures.Count -gt 0) {
        Write-Status -State "failed" -Message "Team props pipeline finished with critical failures." -ExitCode 1 -Artifacts $artifacts
        exit 1
    }

    $finalState = if ($warnings.Count -gt 0) { "warning" } else { "idle" }
    $finalMessage = if ($warnings.Count -gt 0) {
        "Team props pipeline finished with warnings."
    } else {
        "Team props pipeline finished successfully."
    }
    Write-Status -State $finalState -Message $finalMessage -Artifacts $artifacts

    $latestShortlist = Get-LatestMatchingFile (Join-Path $logDir "shortlist-*.txt")
    if ($latestShortlist) {
        Write-Host ""
        Get-Content $latestShortlist.FullName
    }

    exit 0
} catch {
    Add-CriticalFailure "Fatal team props pipeline exception: $($_.Exception.Message)"
    Write-Status -State "failed" -Message $_.Exception.Message -ExitCode 1 -Artifacts (Build-ArtifactsState)
    exit 1
}
