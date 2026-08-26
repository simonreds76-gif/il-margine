param(
    [switch]$TeamShots,
    [switch]$Corners,
    [switch]$Goalscorer,
    [switch]$AssistValue,
    [switch]$TennisProps,
    [switch]$Settlement,
    [string]$RemoteRef = "origin/golden-with-speed-insights",
    [ValidateRange(1, 30)][int]$ManagedBackupRetention = 7,
    [switch]$NoFetch,
    [switch]$NoBackup
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$syncAll = -not ($TeamShots -or $Corners -or $Goalscorer -or $AssistValue -or $TennisProps -or $Settlement)
$includeTeamShots = $syncAll -or $TeamShots
$includeCorners = $syncAll -or $Corners
$includeGoalscorer = $syncAll -or $Goalscorer
# Assist Value is frozen. Preserve an explicit manual sync path, but do not
# refresh its large shadow artifacts during normal localhost startup.
$includeAssistValue = $AssistValue
$includeTennisProps = $syncAll -or $TennisProps
$includeSettlement = $syncAll -or $Settlement -or $TeamShots -or $Corners

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
    "data/football-form/team-shots-v3-ema20-published-picks.csv",
    "data/football-form/team-shots-v3-ema20-clv-monitor.csv",
    "data/football-form/team-shots-v3-ema20-clv-monitor.md",
    "data/football-form/team-shots-v3-ema20-settlement-audit.json",
    "data/football-form/team-shots-v4-shadow-signals.csv",
    "data/football-form/team-shots-v4-shadow-clv.csv",
    "data/football-form/team-shots-v4-shadow-clv.md",
    "data/football-form/team-shots-v4-settlement-audit.json",
    "data/football-form/team-shots-v4-shadow-config.json",
    "data/football-form/football-counts-vnext-candidates.csv",
    "data/football-form/football-counts-vnext-gate.json",
    "data/football-form/football-counts-vnext-gate.md",
    "data/football-form/football-count-market-coverage.json",
    "data/goalkeeper-saves/gk-saves-capture-status.json",
    "data/goalkeeper-saves/gk-saves-v1-candidates.csv",
    "data/goalkeeper-saves/gk-saves-v1-provisional.csv",
    "data/goalkeeper-saves/gk-saves-v1-settlement-status.json",
    "data/goalkeeper-saves/gk-saves-v1-shadow-report.json",
    "data/goalkeeper-saves/gk-saves-v1-shadow-signals.csv",
    "data/team-shots/shadow/team-shots-shadow-signals.csv",
    "data/team-shots/shadow/team-shots-shadow-performance.txt",
    "data/shortlist/team-props-status.json"
)

$cornersFiles = @(
    "data/corners-ou/corners-live-snapshot.json",
    "data/corners-ou/corners-monitor-summary.json",
    "data/corners-ou/corners-ou-calibration.txt",
    "data/corners-ou/corners-ou-backtest-report.txt",
    "data/corners-ou/corners-ou-backtest-results.csv",
    "data/corners-ou/corners-ou-predictions.csv",
    "data/corners-ou/pinnacle-corners-odds.csv",
    "data/football-form/corners-v0-published-picks.csv",
    "data/football-form/corners-v0-clv-monitor.csv",
    "data/football-form/corners-v0-clv-monitor.md",
    "data/football-form/corners-v0-settlement-audit.json",
    "data/football-form/corners-v3-shadow-signals.csv",
    "data/football-form/corners-v3-shadow-clv.csv",
    "data/football-form/corners-v3-shadow-clv.md",
    "data/football-form/corners-v3-settlement-audit.json",
    "data/football-form/corners-v3-shadow-config.json",
    "data/football-form/football-counts-vnext-candidates.csv",
    "data/football-form/football-counts-vnext-gate.json",
    "data/football-form/football-counts-vnext-gate.md",
    "data/shortlist/shortlist-latest.txt",
    "data/shortlist/value-bets-latest.csv",
    "data/shortlist/signals-latest.csv",
    "data/shortlist/settled-pnl.csv",
    "data/shortlist/corners-live-pnl.txt",
    "data/shortlist/team-props-status.json"
)

$settlementFiles = @(
    "data/results-snapshot/latest.json",
    # Current 2026/27 football-count lanes. These are deliberately included in
    # normal localhost startup without pulling the much larger model archives.
    "data/football-form/team-shots-v4-shadow-signals.csv",
    "data/football-form/team-shots-v4-shadow-clv.csv",
    "data/football-form/team-shots-v4-shadow-clv.md",
    "data/football-form/team-shots-v4-settlement-audit.json",
    "data/football-form/team-shots-v4-shadow-config.json",
    "data/football-form/corners-v3-shadow-signals.csv",
    "data/football-form/corners-v3-shadow-clv.csv",
    "data/football-form/corners-v3-shadow-clv.md",
    "data/football-form/corners-v3-settlement-audit.json",
    "data/football-form/corners-v3-shadow-config.json",
    "data/football-form/football-counts-vnext-candidates.csv",
    "data/football-form/football-counts-vnext-gate.json",
    "data/football-form/football-counts-vnext-gate.md",
    "data/football-form/team-shots-v3-ema20-clv-monitor.csv",
    "data/football-form/team-shots-v3-ema20-clv-monitor.md",
    "data/football-form/team-shots-v3-ema20-settlement-audit.json",
    "data/football-form/corners-v0-clv-monitor.csv",
    "data/football-form/corners-v0-clv-monitor.md",
    "data/football-form/corners-v0-settlement-audit.json",
    "data/goalkeeper-saves/gk-saves-capture-status.json",
    "data/goalkeeper-saves/gk-saves-v1-candidates.csv",
    "data/goalkeeper-saves/gk-saves-v1-provisional.csv",
    "data/goalkeeper-saves/gk-saves-v1-settlement-status.json",
    "data/goalkeeper-saves/gk-saves-v1-shadow-report.json",
    "data/goalkeeper-saves/gk-saves-v1-shadow-signals.csv",
    "data/team-shots/team-shots-live-snapshot.json",
    "data/corners-ou/corners-live-snapshot.json",
    "data/corners-ou/corners-monitor-summary.json"
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
    "data/goalscorer/confirmed-lineups.json",
    "data/goalscorer/fair-odds-lab-serie-a-signals.csv",
    "data/goalscorer/fair-odds-lab-epl-signals.csv",
    "data/goalscorer/fair-odds-lab-la-liga-signals.csv",
    "data/goalscorer/fair-odds-lab-bundesliga-signals.csv",
    "data/goalscorer/fair-odds-lab-ligue-1-signals.csv",
    "data/goalscorer/fair-odds-lab-serie-a-quarantine.csv",
    "data/goalscorer/fair-odds-lab-epl-quarantine.csv",
    "data/goalscorer/fair-odds-lab-la-liga-quarantine.csv",
    "data/goalscorer/fair-odds-lab-bundesliga-quarantine.csv",
    "data/goalscorer/fair-odds-lab-ligue-1-quarantine.csv",
    "public/fair-odds-lab/signals.json",
    "public/fair-odds-lab/highlights.json"
)

$assistValueFiles = @(
    "data/assist-value/assist-value-shadow-signals.csv",
    "data/assist-value/assist-value-shadow-board.csv",
    "data/assist-value/assist-value-shadow-report.txt",
    "data/assist-value/assist-value-model-report.txt",
    "data/assist-value/assist-value-shadow-performance.txt",
    "data/assist-value/assist-market-audit-serie-a.csv",
    "data/assist-value/assist-market-audit-epl.csv",
    "data/assist-value/assist-market-audit-la-liga.csv",
    "data/assist-value/assist-market-audit-bundesliga.csv",
    "data/assist-value/assist-market-audit-ligue-1.csv"
)

$utcNow = (Get-Date).ToUniversalTime()
$todayUtc = $utcNow.ToString("yyyy-MM-dd")
$monthUtc = $utcNow.ToString("yyyy-MM")
$tennisPropsFiles = @(
    "data/tennis-props/inbox/bet365-lines-history-$monthUtc.csv"
)
0..3 | ForEach-Object {
    $captureDate = $utcNow.AddDays(-$_).ToString("yyyy-MM-dd")
    $tennisPropsFiles += "data/tennis-props/inbox/bet365-lines-$captureDate.csv"
    $tennisPropsFiles += "data/tennis-props/inbox/bet365-tennis-market-audit-$captureDate.csv"
}

$files = New-Object System.Collections.Generic.List[string]
if ($includeTeamShots) { $teamShotsFiles | ForEach-Object { [void]$files.Add($_) } }
if ($includeCorners) { $cornersFiles | ForEach-Object { [void]$files.Add($_) } }
if ($includeSettlement) { $settlementFiles | ForEach-Object { [void]$files.Add($_) } }
if ($includeGoalscorer) { $goalscorerFiles | ForEach-Object { [void]$files.Add($_) } }
if ($includeAssistValue) { $assistValueFiles | ForEach-Object { [void]$files.Add($_) } }
if ($includeTennisProps) { $tennisPropsFiles | ForEach-Object { [void]$files.Add($_) } }

$files = $files | Select-Object -Unique

if (-not $NoFetch) {
    Write-Host "Fetching latest hosted data from origin/golden-with-speed-insights..."
    git fetch origin golden-with-speed-insights | Out-Null
}

$backupRoot = $null
if (-not $NoBackup) {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $backupRoot = Join-Path $repoRoot ".cleanup-backups/hosted-monitor-sync-$stamp"
    New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null
    Set-Content -LiteralPath (Join-Path $backupRoot ".managed-retention") -Value $stamp -Encoding Ascii
    Write-Host "Backing up existing local monitor artifacts to $backupRoot"
}

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$synced = 0
$skipped = 0
$backedUp = 0

# These CSVs are append-only evidence ledgers. A hosted snapshot can lag the
# laptop settlement run, so replacing a richer local ledger would erase rows
# from the localhost monitor. Merge hosted additions into local evidence and
# retain the more complete version of any existing pick.
$mergeEvidenceCsvFiles = @(
    "data/football-form/team-shots-v4-shadow-clv.csv",
    "data/football-form/corners-v3-shadow-clv.csv",
    "data/goalkeeper-saves/gk-saves-v1-shadow-signals.csv"
)

function Test-SettledEvidenceRow {
    param([Parameter(Mandatory = $true)]$Row)
    return ([string]$Row.result).Trim().ToLowerInvariant() -in @("won", "lost", "push", "void")
}

function Get-EvidenceRowScore {
    param([Parameter(Mandatory = $true)]$Row)
    $score = 0
    if (Test-SettledEvidenceRow -Row $Row) { $score += 1000 }
    foreach ($field in @("book_price_close", "pinnacle_price_close", "published_to_close_clv", "close_odds", "clv", "pnl_units", "actual_team_shots", "actual_total_corners", "actual_saves", "settled_at")) {
        if (-not [string]::IsNullOrWhiteSpace([string]$Row.$field)) { $score += 1 }
    }
    return $score
}

function Merge-EvidenceCsvContent {
    param(
        [Parameter(Mandatory = $true)][string]$TargetPath,
        [Parameter(Mandatory = $true)][string[]]$RemoteContent
    )

    if (-not (Test-Path -LiteralPath $TargetPath)) {
        return (($RemoteContent -join "`n") + "`n")
    }

    $localRows = @(Import-Csv -LiteralPath $TargetPath)
    $remoteRows = @($RemoteContent | ConvertFrom-Csv)
    if ($localRows.Count -eq 0) {
        return (($RemoteContent -join "`n") + "`n")
    }
    if ($remoteRows.Count -eq 0) {
        Write-Host "Preserved local evidence (hosted ledger empty): $TargetPath"
        return [System.IO.File]::ReadAllText($TargetPath)
    }

    $headers = New-Object System.Collections.Generic.List[string]
    foreach ($row in @($remoteRows[0], $localRows[0])) {
        foreach ($property in $row.PSObject.Properties.Name) {
            if (-not $headers.Contains($property)) { [void]$headers.Add($property) }
        }
    }

    $keyField = if ($headers.Contains("pick_id")) { "pick_id" } elseif ($headers.Contains("signal_id")) { "signal_id" } else { $null }
    if (-not $keyField) {
        throw "Evidence CSV has no pick_id or signal_id key: $TargetPath"
    }

    $merged = [ordered]@{}
    foreach ($row in $remoteRows) {
        $key = ([string]$row.$keyField).Trim()
        if ($key) { $merged[$key] = $row }
    }
    foreach ($row in $localRows) {
        $key = ([string]$row.$keyField).Trim()
        if (-not $key) { continue }
        if (-not $merged.Contains($key) -or (Get-EvidenceRowScore -Row $row) -gt (Get-EvidenceRowScore -Row $merged[$key])) {
            $merged[$key] = $row
        }
    }

    $normalized = foreach ($row in $merged.Values) {
        $ordered = [ordered]@{}
        foreach ($header in $headers) { $ordered[$header] = [string]$row.$header }
        [pscustomobject]$ordered
    }
    Write-Host "Merged evidence ledger: local=$($localRows.Count), hosted=$($remoteRows.Count), result=$($normalized.Count)"
    return (($normalized | ConvertTo-Csv -NoTypeInformation) -join "`n") + "`n"
}

function Write-TextFileWithRetry {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Content,
        [Parameter(Mandatory = $true)][System.Text.Encoding]$Encoding,
        [int]$Attempts = 8,
        [int]$DelayMs = 250
    )

    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        try {
            [System.IO.File]::WriteAllText($Path, $Content, $Encoding)
            return
        } catch [System.IO.IOException] {
            if ($attempt -ge $Attempts) {
                throw
            }
            $sleepMs = $DelayMs * $attempt
            Write-Host "Retry locked file write ($attempt/$Attempts): $Path"
            Start-Sleep -Milliseconds $sleepMs
        }
    }
}

foreach ($relativePath in $files) {
    $blobSpec = "${RemoteRef}:$relativePath"
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $content = & git show $blobSpec 2>$null
    $gitShowExitCode = $LASTEXITCODE
    $ErrorActionPreference = $previousErrorActionPreference
    if ($gitShowExitCode -ne 0) {
        Write-Host "Skip missing: $relativePath"
        $skipped += 1
        continue
    }

    $targetPath = Join-Path $repoRoot ($relativePath -replace "/", "\")
    $contentToWrite = (($content -join "`n") + "`n")
    if ($relativePath -in $mergeEvidenceCsvFiles) {
        $contentToWrite = Merge-EvidenceCsvContent -TargetPath $targetPath -RemoteContent $content
    }
    if ((Test-Path -LiteralPath $targetPath) -and $backupRoot) {
        $backupPath = Join-Path $backupRoot ($relativePath -replace "/", "\")
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $backupPath) | Out-Null
        Copy-Item -LiteralPath $targetPath -Destination $backupPath -Force
        $backedUp += 1
    }

    $targetDir = Split-Path -Parent $targetPath
    if ($targetDir) {
        New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
    }

    Write-TextFileWithRetry -Path $targetPath -Content $contentToWrite -Encoding $utf8NoBom
    Write-Host "Synced: $relativePath"
    $synced += 1
}

if ($backupRoot) {
    $cleanupRoot = Join-Path $repoRoot ".cleanup-backups"
    $managedBackups = @(
        Get-ChildItem -LiteralPath $cleanupRoot -Directory -Filter "hosted-monitor-sync-*" -ErrorAction SilentlyContinue |
            Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName ".managed-retention") } |
            Sort-Object LastWriteTime -Descending
    )
    $expiredBackups = @($managedBackups | Select-Object -Skip $ManagedBackupRetention)
    foreach ($expired in $expiredBackups) {
        if (-not $expired.FullName.StartsWith(($cleanupRoot + [System.IO.Path]::DirectorySeparatorChar), [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to prune backup outside cleanup root: $($expired.FullName)"
        }
        Remove-Item -LiteralPath $expired.FullName -Recurse -Force
    }
    if ($expiredBackups.Count -gt 0) {
        Write-Host "Pruned $($expiredBackups.Count) managed backup(s); retained newest $ManagedBackupRetention."
    }
}

Write-Host ""
Write-Host "Done. Synced $synced file(s); skipped $skipped missing file(s); backed up $backedUp file(s)."

function Show-MonitorCsvStatus($Label, $Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return }
    try {
        $rows = Import-Csv -LiteralPath $Path
        $groups = $rows | Group-Object result | Sort-Object Name
        $summary = ($groups | ForEach-Object { "$($_.Name)=$($_.Count)" }) -join ", "
        $pending = @($rows | Where-Object { $_.result -eq "pending" })
        Write-Host "$Label status: $summary; pending=$($pending.Count)"
        foreach ($row in ($pending | Select-Object -First 5)) {
            Write-Host "  pending $($row.match_date): $($row.match) / $($row.selection)"
        }
    } catch {
        Write-Warning "Could not summarize ${Label}: $($_.Exception.Message)"
    }
}

Show-MonitorCsvStatus "Team shots v3 EMA20" (Join-Path $repoRoot "data/football-form/team-shots-v3-ema20-clv-monitor.csv")
Show-MonitorCsvStatus "Corners v0" (Join-Path $repoRoot "data/football-form/corners-v0-clv-monitor.csv")

function Show-AssistValueStatus($Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return }
    try {
        $rows = Import-Csv -LiteralPath $Path
        $signals = @($rows | Where-Object { $_.signal_status -eq "shadow_signal" })
        $settled = @($signals | Where-Object { $_.settled -in @("1", "true", "yes") })
        $pending = [Math]::Max(0, $signals.Count - $settled.Count)
        Write-Host "Assist Value shadow status: signals=$($signals.Count), settled=$($settled.Count), pending=$pending"
        foreach ($row in ($signals | Select-Object -First 5)) {
            Write-Host "  signal $($row.match_date): $($row.home_team) vs $($row.away_team) / $($row.player_name) @ $($row.market_odds)"
        }
    } catch {
        Write-Warning "Could not summarize Assist Value: $($_.Exception.Message)"
    }
}

if ($includeAssistValue) {
    Show-AssistValueStatus (Join-Path $repoRoot "data/assist-value/assist-value-shadow-signals.csv")
}
