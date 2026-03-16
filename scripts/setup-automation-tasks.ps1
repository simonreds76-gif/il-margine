# One-time task registration for fully automatic pipeline.
# Daily: 11:00 and 23:55 (Roger tips/stats/fixtures up to date morning and night).

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

$dailyScript = Join-Path $root "scripts\oncourt-daily.ps1"
$weeklyScript = Join-Path $root "scripts\oncourt-weekly.ps1"
$psExe = "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe"

if (!(Test-Path $dailyScript)) { throw "Missing $dailyScript" }
if (!(Test-Path $weeklyScript)) { throw "Missing $weeklyScript" }

$dailyCmd = "$psExe -ExecutionPolicy Bypass -NoProfile -File `"$dailyScript`""
$weeklyCmd = "$psExe -ExecutionPolicy Bypass -NoProfile -File `"$weeklyScript`""

schtasks /Create /TN "IlMargine-Daily" /SC DAILY /ST 23:55 /TR "$dailyCmd" /F | Out-Host
schtasks /Create /TN "IlMargine-Daily-AM" /SC DAILY /ST 11:00 /TR "$dailyCmd" /F | Out-Host
schtasks /Create /TN "IlMargine-Weekly" /SC WEEKLY /D SUN /ST 22:00 /TR "$weeklyCmd" /F | Out-Host

if ((schtasks /Query /TN "IlMargine-Tennis-Shadow-Settle" 2>$null) -and $LASTEXITCODE -eq 0) {
    schtasks /Delete /TN "IlMargine-Tennis-Shadow-Settle" /F | Out-Host
}

Write-Host ""
Write-Host "Tasks created/updated:"
schtasks /Query /TN "IlMargine-Daily" | Out-Host
schtasks /Query /TN "IlMargine-Daily-AM" | Out-Host
schtasks /Query /TN "IlMargine-Weekly" | Out-Host
Write-Host ""
Write-Host "Optional immediate test:"
Write-Host "  schtasks /Run /TN IlMargine-Daily"
