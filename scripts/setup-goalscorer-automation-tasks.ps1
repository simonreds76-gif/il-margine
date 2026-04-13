# One-time task registration for the goalscorer automation pipeline.
# GitHub hosted workflows are now the primary live engine.
# This setup script keeps the local Windows task as an explicit fallback only.
# Creates:
#   - optional local live polling task (disabled by default unless requested)
#   - a daily shadow settlement task at 10:00

param(
    [switch]$EnableLocalLiveSchedule
)

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

function Set-ScheduledTaskBatteryFriendly([string]$taskName) {
    $xml = schtasks /Query /TN $taskName /XML
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($xml)) {
        throw "Unable to read scheduled task XML for $taskName"
    }

    $patchedXml = $xml `
        -replace '<DisallowStartIfOnBatteries>true</DisallowStartIfOnBatteries>', '<DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>' `
        -replace '<StopIfGoingOnBatteries>true</StopIfGoingOnBatteries>', '<StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>'

    $tmpPath = Join-Path ([System.IO.Path]::GetTempPath()) "$taskName.xml"
    Set-Content -Path $tmpPath -Value $patchedXml -Encoding Unicode
    schtasks /Create /TN $taskName /XML $tmpPath /F | Out-Null
    Remove-Item -LiteralPath $tmpPath -Force -ErrorAction SilentlyContinue
}

if (Test-ScheduledTaskExists "IlMargine-Goalscorer-Health") {
    schtasks /Delete /TN "IlMargine-Goalscorer-Health" /F | Out-Host
}

if ($EnableLocalLiveSchedule) {
    schtasks /Create /TN "IlMargine-Goalscorer-Live" /SC DAILY /ST 08:00 /RI 10 /DU 16:00 /RL HIGHEST /TR "$liveCmd" /F | Out-Host
    Set-ScheduledTaskBatteryFriendly "IlMargine-Goalscorer-Live"
} elseif (Test-ScheduledTaskExists "IlMargine-Goalscorer-Live") {
    schtasks /Change /TN "IlMargine-Goalscorer-Live" /DISABLE | Out-Host
}
# Run the daily settlement as SYSTEM so it can execute unattended during the day.
schtasks /Create /TN "IlMargine-Goalscorer-Shadow-Settle" /SC DAILY /ST 10:00 /RL HIGHEST /RU SYSTEM /TR "$settleCmd" /F | Out-Host

Set-ScheduledTaskBatteryFriendly "IlMargine-Goalscorer-Shadow-Settle"

Write-Host ""
Write-Host "Goalscorer tasks created/updated."
Get-ScheduledTask -TaskName "IlMargine-Goalscorer-Shadow-Settle" |
    Get-ScheduledTaskInfo |
    Select-Object TaskName, LastRunTime, NextRunTime, LastTaskResult |
    Format-Table -AutoSize | Out-Host

Write-Host ""
if ($EnableLocalLiveSchedule) {
    Get-ScheduledTask -TaskName "IlMargine-Goalscorer-Live" |
        Get-ScheduledTaskInfo |
        Select-Object TaskName, LastRunTime, NextRunTime, LastTaskResult |
        Format-Table -AutoSize | Out-Host
    Write-Host ""
    Write-Host "Local Windows live polling is ENABLED by request."
} else {
    Write-Host "GitHub hosted hot-live polling is the primary path."
    Write-Host "Local Windows live polling is disabled by default and kept as fallback/manual only."
    Write-Host "Use -EnableLocalLiveSchedule if you explicitly want the local scheduled poll back."
}
Write-Host ""
Write-Host "Optional immediate test:"
Write-Host "  powershell -ExecutionPolicy Bypass -NoProfile -File scripts\\goalscorer-live.ps1"
Write-Host "  schtasks /Run /TN IlMargine-Goalscorer-Shadow-Settle"
