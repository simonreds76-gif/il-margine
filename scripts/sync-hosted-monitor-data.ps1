param(
    [switch]$TeamShots,
    [switch]$Corners,
    [switch]$Goalscorer
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$syncAll = -not ($TeamShots -or $Corners -or $Goalscorer)
$includeTeamShots = $syncAll -or $TeamShots
$includeCorners = $syncAll -or $Corners
$includeGoalscorer = $syncAll -or $Goalscorer

$teamShotsFiles = @(
    "data/team-shots/team-shots-live-snapshot.json",
    "data/team-shots/team-shots-calibration.txt",
    "data/team-shots/team-shots-calibration-params.json",
    "data/team-shots/team-shots-calibration-diagnostics.txt",
    "data/team-shots/team-shots-backtest-results.csv",
    "data/team-shots/team-shots-backtest-report.txt",
    "data/team-shots/team-shots-predictions.csv",
    "data/team-shots/team-shots-comparison.csv",
    "data/team-shots/team-shots-comparison.txt",
    "data/team-shots/team-shots-odds-history.csv",
    "data/team-shots/team-shots-upcoming.csv",
    "data/team-shots/team-shots-scanner.csv",
    "data/team-shots/shadow/team-shots-shadow-signals.csv",
    "data/team-shots/shadow/team-shots-shadow-performance.txt",
    "data/shortlist/team-props-status.json"
)

$cornersFiles = @(
    "data/corners-ou/corners-live-snapshot.json",
    "data/corners-ou/corners-ou-calibration.txt",
    "data/corners-ou/corners-ou-backtest-report.txt",
    "data/corners-ou/corners-ou-backtest-results.csv",
    "data/corners-ou/corners-ou-predictions.csv",
    "data/corners-ou/pinnacle-corners-odds.csv",
    "data/shortlist/shortlist-latest.txt",
    "data/shortlist/value-bets-latest.csv",
    "data/shortlist/signals-latest.csv",
    "data/shortlist/settled-pnl.csv",
    "data/shortlist/corners-live-pnl.txt",
    "data/shortlist/team-props-status.json"
)

$goalscorerFiles = @(
    "data/goalscorer/goalscorer-live-snapshot.json",
    "data/goalscorer/all-leagues-live-board.json",
    "data/goalscorer/live-board.json",
    "data/goalscorer/goalscorer-live-comparison.csv",
    "data/goalscorer/goalscorer-live-comparison.txt",
    "data/goalscorer/goalscorer-public-signals.csv",
    "data/goalscorer/goalscorer-shadow-signals.csv",
    "data/goalscorer/goalscorer-live-status.json",
    "data/goalscorer/goalscorer-live-schedule-state.json",
    "data/goalscorer/goalscorer-health-status.json",
    "data/goalscorer/goalscorer-live.log",
    "data/goalscorer/confirmed-lineups.json"
)

$files = New-Object System.Collections.Generic.List[string]
if ($includeTeamShots) { $teamShotsFiles | ForEach-Object { [void]$files.Add($_) } }
if ($includeCorners) { $cornersFiles | ForEach-Object { [void]$files.Add($_) } }
if ($includeGoalscorer) { $goalscorerFiles | ForEach-Object { [void]$files.Add($_) } }

$files = $files | Select-Object -Unique

Write-Host "Fetching latest hosted data from origin/golden-with-speed-insights..."
git fetch origin golden-with-speed-insights | Out-Null

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$synced = 0
$skipped = 0

foreach ($relativePath in $files) {
    $blobSpec = "origin/golden-with-speed-insights:$relativePath"
    $content = git show $blobSpec 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Skip missing: $relativePath"
        $skipped += 1
        continue
    }

    $targetPath = Join-Path $repoRoot ($relativePath -replace "/", "\")
    $targetDir = Split-Path -Parent $targetPath
    if ($targetDir) {
        New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
    }

    [System.IO.File]::WriteAllText($targetPath, ($content -join "`n"), $utf8NoBom)
    Write-Host "Synced: $relativePath"
    $synced += 1
}

Write-Host ""
Write-Host "Done. Synced $synced file(s); skipped $skipped missing file(s)."
