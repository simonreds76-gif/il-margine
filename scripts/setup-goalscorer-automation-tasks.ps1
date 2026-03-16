# One-time task registration for the goalscorer live pipeline.
# Poll every 30 minutes during the match window:
#   - odds refresh
#   - confirmed lineup fetch
#   - live comparison refresh

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

$liveScript = Join-Path $root "scripts\goalscorer-live.ps1"
$settleScript = Join-Path $root "scripts\goalscorer-shadow-settle.ps1"
$psExe = "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe"

if (!(Test-Path $liveScript)) { throw "Missing $liveScript" }
if (!(Test-Path $settleScript)) { throw "Missing $settleScript" }

$liveCmd = "$psExe -ExecutionPolicy Bypass -NoProfile -File `"$liveScript`""
$settleCmd = "$psExe -ExecutionPolicy Bypass -NoProfile -File `"$settleScript`""

schtasks /Create /TN "IlMargine-Goalscorer-Live" /SC MINUTE /MO 30 /ST 12:00 /ET 23:30 /TR "$liveCmd" /F | Out-Host
schtasks /Create /TN "IlMargine-Goalscorer-Shadow-Settle" /SC DAILY /ST 02:15 /TR "$settleCmd" /F | Out-Host

Write-Host ""
Write-Host "Tasks created/updated:"
schtasks /Query /TN "IlMargine-Goalscorer-Live" | Out-Host
schtasks /Query /TN "IlMargine-Goalscorer-Shadow-Settle" | Out-Host
Write-Host ""
Write-Host "Optional immediate test:"
Write-Host "  schtasks /Run /TN IlMargine-Goalscorer-Live"
Write-Host "  schtasks /Run /TN IlMargine-Goalscorer-Shadow-Settle"
