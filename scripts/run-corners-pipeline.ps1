<#
.SYNOPSIS
    Automated team props pipeline: corners + team total shots in one run.

.DESCRIPTION
    Run this script manually or via Task Scheduler. It will:
    1. Run corners model + fetch corner O/U odds + generate value shortlist
    2. Run team shots model + scrape team total shots (Odds-API.io / BetsAPI)
    3. Archive odds + compare model vs book + shadow track + settle
    4. Log everything with timestamps

    The Odds API (the-odds-api.com) does not offer team total shots; those
    lines come from Odds-API.io or BetsAPI when keys are set in .env.local.

.EXAMPLE
    .\scripts\run-corners-pipeline.ps1
    .\scripts\run-corners-pipeline.ps1 -DaysAhead 3 -LeaguesOnly "epl,serie-a"
#>

param(
    [string]$LeaguesOnly = "",
    [int]$DaysAhead = 7,
    [double]$MinEdge = 0.12,
    [string]$Regions = "eu",
    [double]$ShotsMinEdge = 0.05
)

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$logDir = Join-Path $root "data\shortlist"
if (!(Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
$logFile = Join-Path $logDir "pipeline-log.txt"

function Log($msg) {
    $line = "[$(Get-Date -Format 'HH:mm:ss')] $msg"
    Write-Host $line
    Add-Content -Path $logFile -Value $line
}

Log "=========================================="
Log "  TEAM PROPS PIPELINE -- $timestamp"
Log "  (Corners + Team Total Shots)"
Log "=========================================="

# ============================================================
# PART 1: CORNERS
# ============================================================
Log ""
Log "--- CORNERS ---"

Log "Step 1a: Running corners model..."
$modelResult = & python scripts/corners-ou-model.py 2>&1
if ($LASTEXITCODE -ne 0) {
    Log "  WARNING: Model script returned exit code $LASTEXITCODE"
    Log "  $modelResult"
} else {
    $predLine = ($modelResult | Select-String "predictions generated" | Select-Object -Last 1)
    if ($predLine) { Log "  $predLine" }
}

Log "Step 1a2: Fitting Platt calibration..."
$calibResult = & python scripts/corners-fit-calibration.py 2>&1
if ($LASTEXITCODE -ne 0) {
    Log "  [WARN] Calibration fit failed (exit $LASTEXITCODE) — shortlist will use raw probabilities"
} else {
    $calibLine = ($calibResult | Select-String "Params written" | Select-Object -Last 1)
    if ($calibLine) { Log "  $calibLine" }
}

Log "Step 1b: Fetching corner odds and generating shortlist..."
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
    Log "  WARNING: Shortlist returned exit code $LASTEXITCODE"
}

Log "Step 1c: Settling previous corner bets..."
$settleResult = & python scripts/shortlist-settle.py 2>&1
$settleLine = ($settleResult | Select-String "Settled:" | Select-Object -Last 1)
if ($settleLine) { Log "  $settleLine" } else { Log "  No previous corner bets to settle" }

# ============================================================
# PART 2: TEAM TOTAL SHOTS
# ============================================================
Log ""
Log "--- TEAM TOTAL SHOTS ---"

$dataDir = Join-Path $root "data\team-shots"
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $dataDir "shadow") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $dataDir "inbox") | Out-Null

Log "Step 2a: Running team shots model..."
try {
    $shotsModelResult = & python scripts/team-shots-model.py 2>&1
    $shotsLine = ($shotsModelResult | Select-String "predictions generated" | Select-Object -Last 1)
    if ($shotsLine) { Log "  $shotsLine" } else { Log "  Model complete" }
} catch {
    Log "  [WARN] Team shots model failed: $_"
}

Log "Step 2a2: Writing upcoming fixture λ (The Odds API + model)..."
try {
    $upcomingResult = & python scripts/team_shots_upcoming.py --days-ahead $DaysAhead 2>&1
    $upcomingLine = ($upcomingResult | Select-String "Wrote \d+ upcoming rows" | Select-Object -Last 1)
    if ($upcomingLine) { Log "  $upcomingLine" } else { $upcomingResult | ForEach-Object { Log "  $_" } }
} catch {
    Log "  [WARN] Team shots upcoming failed: $_"
}

Log "Step 2b: Scraping team total shots odds (Odds-API.io / BetsAPI)..."
$shotsArgs = @("scripts/team-shots-scrape-odds.py", "--all-leagues", "--days-ahead", $DaysAhead)
try {
    $scrapeResult = & python @shotsArgs 2>&1
    $totalLine = ($scrapeResult | Select-String "Total team shots rows written:" | Select-Object -Last 1)
    if ($totalLine) { Log "  $totalLine" }
} catch {
    Log "  [WARN] Team shots scrape failed: $_"
}

Log "Step 2c: Archiving odds..."
try {
    & python scripts/team-shots-odds-archive.py 2>&1 | ForEach-Object { Log "  $_" }
} catch {
    Log "  [WARN] Odds archive failed: $_"
}

Log "Step 2d: Comparing model vs bookmaker..."
try {
    & python scripts/team-shots-compare.py --min-edge $ShotsMinEdge 2>&1 | ForEach-Object { Log "  $_" }
} catch {
    Log "  [WARN] Comparison failed: $_"
}

Log "Step 2e: Tracking shadow signals..."
try {
    & python scripts/team-shots-shadow-tracker.py --min-edge $ShotsMinEdge 2>&1 | ForEach-Object { Log "  $_" }
} catch {
    Log "  [WARN] Shadow tracking failed: $_"
}

Log "Step 2f: Settling pending shot signals..."
try {
    & python scripts/team-shots-settle.py 2>&1 | ForEach-Object { Log "  $_" }
} catch {
    Log "  [WARN] Shot settlement failed: $_"
}

# ============================================================
# SUMMARY
# ============================================================
Log ""
Log "Pipeline complete. Check:"
Log "  Corners shortlist: http://localhost:3000/model-monitor/corners"
Log "  Team shots:        http://localhost:3000/model-monitor/team-shots"
Log "  Files:             data/shortlist/ + data/team-shots/"
Log "=========================================="

$latestShortlist = Get-ChildItem "$logDir\shortlist-*.txt" -ErrorAction SilentlyContinue | Sort-Object Name | Select-Object -Last 1
if ($latestShortlist) {
    Write-Host ""
    Get-Content $latestShortlist.FullName
}
