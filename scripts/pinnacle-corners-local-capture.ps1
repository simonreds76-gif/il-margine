# Il Margine - local Pinnacle corners capture
# Arcadia serves residential Windows clients but blocks GitHub-hosted runners.
# This task writes only the append-only corners price file, then safely pushes it
# to Golden so the hosted vNext scorer can consume it on its next hourly pass.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

. (Join-Path $root "scripts\use-local-python.ps1") -RepoRoot $root
. (Join-Path $root "scripts\task-lock.ps1")

$dataDir = Join-Path $root "data"
$logFile = Join-Path $dataDir "pinnacle-corners-local-capture.log"
$branch = "golden-with-speed-insights"
$captureFile = "data/corners-ou/pinnacle-corners-odds.csv"

function Log([string]$Message) {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $Message"
    Write-Host $line
    Add-Content -Path $logFile -Value $line
}

function Invoke-NativeLogged([string]$FilePath, [string[]]$Arguments) {
    # Windows PowerShell can promote a native process's harmless stderr output
    # (for example Git's "From https://...") into a terminating ErrorRecord
    # when ErrorActionPreference is Stop. Capture it under Continue and decide
    # success solely from the native exit code.
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & $FilePath @Arguments 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousPreference
    }
    foreach ($entry in @($output)) {
        Log ([string]$entry)
    }
    return $exitCode
}

$lockHandle = Enter-TaskLock -LockName "football-corners-capture" -RootPath $root
if ($null -eq $lockHandle) {
    Log "Another local corners capture is active; skipping."
    exit 0
}

try {
    $dirty = @(git status --porcelain --untracked-files=no)
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to inspect the capture worktree."
    }
    if ($dirty.Count -gt 0) {
        throw "Capture worktree is dirty; refusing to mix automated data with code edits."
    }

    Log "Fetching latest $branch before capture."
    $exitCode = Invoke-NativeLogged "git" @("fetch", "origin", $branch)
    if ($exitCode -ne 0) {
        throw "git fetch failed with exit $exitCode"
    }
    $exitCode = Invoke-NativeLogged "git" @("merge", "--ff-only", "origin/$branch")
    if ($exitCode -ne 0) {
        throw "Capture branch cannot fast-forward to origin/$branch."
    }

    Log "Capturing Pinnacle Big-5 corners prices."
    $exitCode = Invoke-NativeLogged "python" @("scripts\pinnacle-scrape-corners.py", "--bucket-hours", "2")
    if ($exitCode -ne 0) {
        throw "Pinnacle corners capture failed with exit $exitCode"
    }

    git add -- $captureFile
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to stage $captureFile"
    }
    git diff --cached --quiet
    if ($LASTEXITCODE -eq 0) {
        Log "No new corners rows; nothing to push."
        exit 0
    }

    $exitCode = Invoke-NativeLogged "git" @("commit", "-m", "chore: capture local pinnacle corners odds")
    if ($exitCode -ne 0) {
        throw "Unable to commit local corners capture."
    }
    $bash = "C:\Program Files\Git\bin\bash.exe"
    $exitCode = Invoke-NativeLogged $bash @("scripts/ci-safe-push.sh", $branch)
    if ($exitCode -ne 0) {
        throw "Safe push failed with exit $exitCode"
    }
    Log "Local corners capture pushed successfully."
}
catch {
    Log "ERROR: $($_.Exception.Message)"
    throw
}
finally {
    Exit-TaskLock $lockHandle
}
