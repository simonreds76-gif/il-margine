# One-time task registration for the goalscorer live pipeline.
# Creates:
#   - a daily live polling task with 60-minute repetition from 12:00 to 23:00
#   - a daily shadow settlement task at 10:00

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$liveScript = Join-Path $root "scripts\goalscorer-live.ps1"
$settleScript = Join-Path $root "scripts\goalscorer-shadow-settle.ps1"
$psExe = "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe"

$currentIdentity = [Security.Principal.WindowsIdentity]::GetCurrent()
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal($currentIdentity)
$isElevated = $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isElevated) {
    throw "Run this script from an elevated PowerShell window (Run as Administrator)."
}

if (!(Test-Path $liveScript)) { throw "Missing $liveScript" }
if (!(Test-Path $settleScript)) { throw "Missing $settleScript" }

$liveCmd = "$psExe -ExecutionPolicy Bypass -NoProfile -File `"$liveScript`""
$settleCmd = "$psExe -ExecutionPolicy Bypass -NoProfile -File `"$settleScript`""

function Test-ScheduledTaskExists([string]$taskName) {
    & cmd.exe /c "schtasks /Query /TN `"$taskName`" >nul 2>&1"
    return ($LASTEXITCODE -eq 0)
}

if (Test-ScheduledTaskExists "IlMargine-Goalscorer-Health") {
    schtasks /Delete /TN "IlMargine-Goalscorer-Health" /F | Out-Host
}

schtasks /Create /TN "IlMargine-Goalscorer-Live" /SC DAILY /ST 12:00 /RI 60 /DU 11:00 /RL HIGHEST /TR "$liveCmd" /F | Out-Host
# Run the daily settlement as SYSTEM so it can execute unattended during the day.
schtasks /Create /TN "IlMargine-Goalscorer-Shadow-Settle" /SC DAILY /ST 10:00 /RL HIGHEST /RU SYSTEM /TR "$settleCmd" /F | Out-Host

Write-Host ""
Write-Host "Goalscorer tasks created/updated."
Get-ScheduledTask -TaskName "IlMargine-Goalscorer-Live","IlMargine-Goalscorer-Shadow-Settle" |
    Get-ScheduledTaskInfo |
    Select-Object TaskName, LastRunTime, NextRunTime, LastTaskResult |
    Format-Table -AutoSize | Out-Host

Write-Host ""
Write-Host "Goalscorer watchdog intentionally not re-enabled by default."
Write-Host ""
Write-Host "Optional immediate test:"
Write-Host "  schtasks /Run /TN IlMargine-Goalscorer-Live"
Write-Host "  schtasks /Run /TN IlMargine-Goalscorer-Shadow-Settle"
