# One-time task registration for fully automatic pipeline.
# Daily fair-odds refresh: 11:00 and 23:55.
# Tennis Pinnacle history capture: every 30 minutes from 08:00 to 23:30.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

$dailyScript = Join-Path $root "scripts\oncourt-daily.ps1"
$amRefreshScript = Join-Path $root "scripts\oncourt-am-refresh.ps1"
$weeklyScript = Join-Path $root "scripts\oncourt-weekly.ps1"
$closeCaptureScript = Join-Path $root "scripts\pinnacle-close-capture.ps1"
$psExe = "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe"

if (!(Test-Path $dailyScript)) { throw "Missing $dailyScript" }
if (!(Test-Path $amRefreshScript)) { throw "Missing $amRefreshScript" }
if (!(Test-Path $weeklyScript)) { throw "Missing $weeklyScript" }
if (!(Test-Path $closeCaptureScript)) { throw "Missing $closeCaptureScript" }

$dailyCmd = "$psExe -ExecutionPolicy Bypass -NoProfile -File `"$dailyScript`""
$amRefreshCmd = "$psExe -ExecutionPolicy Bypass -NoProfile -File `"$amRefreshScript`""
$weeklyCmd = "$psExe -ExecutionPolicy Bypass -NoProfile -File `"$weeklyScript`""
$closeCaptureCmd = "$psExe -ExecutionPolicy Bypass -NoProfile -File `"$closeCaptureScript`""

function Test-ScheduledTaskExists([string]$taskName) {
    & cmd.exe /c "schtasks /Query /TN `"$taskName`" >nul 2>&1"
    return ($LASTEXITCODE -eq 0)
}

function Remove-ScheduledTaskIfExists([string]$taskName) {
    if (Test-ScheduledTaskExists $taskName) {
        schtasks /Delete /TN $taskName /F | Out-Host
    }
}

Remove-ScheduledTaskIfExists "OnCourt Daily Sync"
Remove-ScheduledTaskIfExists "OnCourt Weekly"
Remove-ScheduledTaskIfExists "IlMargine-PinnacleCloseCapture"

schtasks /Create /TN "IlMargine-Daily" /SC DAILY /ST 23:55 /TR "$dailyCmd" /F | Out-Host
schtasks /Create /TN "IlMargine-Daily-AM" /SC DAILY /ST 11:00 /TR "$amRefreshCmd" /F | Out-Host
schtasks /Create /TN "IlMargine-Weekly" /SC WEEKLY /D SUN /ST 03:00 /TR "$weeklyCmd" /F | Out-Host
schtasks /Create /TN "IlMargine-Tennis-Close-Capture" /SC DAILY /ST 08:00 /RI 30 /DU 16:00 /TR "$closeCaptureCmd" /F | Out-Host

if (Test-ScheduledTaskExists "IlMargine-Tennis-Shadow-Settle") {
    schtasks /Delete /TN "IlMargine-Tennis-Shadow-Settle" /F | Out-Host
}

Write-Host ""
Write-Host "Tasks created/updated:"
schtasks /Query /TN "IlMargine-Daily" | Out-Host
schtasks /Query /TN "IlMargine-Daily-AM" | Out-Host
schtasks /Query /TN "IlMargine-Weekly" | Out-Host
schtasks /Query /TN "IlMargine-Tennis-Close-Capture" | Out-Host
Write-Host ""
Write-Host "Optional immediate test:"
Write-Host "  schtasks /Run /TN IlMargine-Daily"
Write-Host "  schtasks /Run /TN IlMargine-Tennis-Close-Capture"
