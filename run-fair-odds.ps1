param(
    [switch]$Light,
    [switch]$WithSignals
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

function Log($msg) {
    Write-Host "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $msg"
}

if ($Light) {
    $argsList = @("scripts/run-daily-odds.py", "--skip-strict-report")
    $modeLabel = "light refresh (skip strict report)"
    Log "Starting fair-odds refresh: $modeLabel"
    Log "Command: python $($argsList -join ' ')"
    & python @argsList
    $exitCode = $LASTEXITCODE
} else {
    $scriptPath = Join-Path $root "scripts\oncourt-am-refresh.ps1"
    $modeLabel = "AM-style refresh (includes fair odds, Clay, Spread, settlement/performance)"
    Log "Starting fair-odds refresh: $modeLabel"
    Log "Command: powershell -ExecutionPolicy Bypass -NoProfile -File `"$scriptPath`""
    & powershell -ExecutionPolicy Bypass -NoProfile -File $scriptPath
    $exitCode = $LASTEXITCODE
}

if ($exitCode -ne 0) {
    Log "Fair-odds refresh failed (exit $exitCode)"
    exit $exitCode
}

Log "Fair-odds refresh finished successfully"
