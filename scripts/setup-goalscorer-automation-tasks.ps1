# One-time task registration for the goalscorer live pipeline.
# Creates:
#   - a daily live polling task with 30-minute repetition from 12:00 to 23:30
#   - a daytime watchdog task that checks freshness every 15 minutes
#   - a daily shadow settlement task at 02:15

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$liveScript = Join-Path $root "scripts\goalscorer-live.ps1"
$healthScript = Join-Path $root "scripts\goalscorer-health-check.ps1"
$settleScript = Join-Path $root "scripts\goalscorer-shadow-settle.ps1"
$psExe = "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe"

$currentIdentity = [Security.Principal.WindowsIdentity]::GetCurrent()
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal($currentIdentity)
$isElevated = $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isElevated) {
    throw "Run this script from an elevated PowerShell window (Run as Administrator)."
}

if (!(Test-Path $liveScript)) { throw "Missing $liveScript" }
if (!(Test-Path $healthScript)) { throw "Missing $healthScript" }
if (!(Test-Path $settleScript)) { throw "Missing $settleScript" }

$liveCmd = "$psExe -ExecutionPolicy Bypass -NoProfile -File `"$liveScript`""
$healthCmd = "$psExe -ExecutionPolicy Bypass -NoProfile -File `"$healthScript`""
$settleCmd = "$psExe -ExecutionPolicy Bypass -NoProfile -File `"$settleScript`""

schtasks /Create /TN "IlMargine-Goalscorer-Live" /SC DAILY /ST 12:00 /RI 30 /DU 11:30 /RL HIGHEST /TR "$liveCmd" /F | Out-Host
schtasks /Create /TN "IlMargine-Goalscorer-Health" /SC DAILY /ST 12:15 /RI 15 /DU 11:45 /RL HIGHEST /TR "$healthCmd" /F | Out-Host
schtasks /Create /TN "IlMargine-Goalscorer-Shadow-Settle" /SC DAILY /ST 02:15 /RL HIGHEST /TR "$settleCmd" /F | Out-Host

Write-Host ""
Write-Host "Goalscorer tasks created/updated."
Get-ScheduledTask -TaskName "IlMargine-Goalscorer-Live","IlMargine-Goalscorer-Health","IlMargine-Goalscorer-Shadow-Settle" |
    Get-ScheduledTaskInfo |
    Select-Object TaskName, LastRunTime, NextRunTime, LastTaskResult |
    Format-Table -AutoSize | Out-Host

Write-Host ""
Write-Host "Optional immediate test:"
Write-Host "  schtasks /Run /TN IlMargine-Goalscorer-Live"
Write-Host "  schtasks /Run /TN IlMargine-Goalscorer-Health"
Write-Host "  schtasks /Run /TN IlMargine-Goalscorer-Shadow-Settle"
