param(
    [switch]$WithSignals
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

function Log($msg) {
    Write-Host "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $msg"
}

$argsList = @("scripts/run-daily-odds.py")
if (-not $WithSignals) {
    $argsList += "--skip-strict-report"
}

$modeLabel = if ($WithSignals) { "full refresh (includes signal reports)" } else { "light refresh (skip strict report)" }
Log "Starting fair-odds refresh: $modeLabel"
Log "Command: python $($argsList -join ' ')"

& python @argsList
$exitCode = $LASTEXITCODE

if ($exitCode -ne 0) {
    Log "Fair-odds refresh failed (exit $exitCode)"
    exit $exitCode
}

Log "Fair-odds refresh finished successfully"
