# Il Margine - Pinnacle Close Capture
# Intended for a frequent scheduled task (e.g. every 15 minutes).
# Appends one full Pinnacle scrape run to bookmaker_odds_history.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root
. (Join-Path $root "scripts\task-lock.ps1")

$dataDir = Join-Path $root "data"
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null

$logFile = Join-Path $dataDir "pinnacle-close-capture.log"

function Log($msg) {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $msg"
    Write-Host $line
    Add-Content -Path $logFile -Value $line
}

$lockHandle = Enter-TaskLock -LockName "tennis-automation" -RootPath $root
if ($null -eq $lockHandle) {
    Log "Another tennis automation run is already active; skipping close capture."
    exit 0
}

try {
    Log "=== Pinnacle close capture start ==="
    & python scripts\pinnacle-capture-history.py --capture-mode close 2>&1 | ForEach-Object { Log $_ }
    if ($LASTEXITCODE -ne 0) {
        Log "ERROR: pinnacle close capture failed (exit $LASTEXITCODE)"
        exit 1
    }
    Log "=== Pinnacle close capture done ==="
}
finally {
    Exit-TaskLock $lockHandle
}
