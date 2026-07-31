# One-time task registration for fully automatic pipeline.
# Daily fair-odds refresh: 10:05 and 22:30.
# Tennis Pinnacle history capture: every 30 minutes from 08:00 to 23:30.
# Use hidden PowerShell windows so scheduled jobs do not interrupt desktop work.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

$dailyScript = Join-Path $root "scripts\oncourt-daily.ps1"
$amRefreshScript = Join-Path $root "scripts\oncourt-am-refresh.ps1"
$weeklyScript = Join-Path $root "scripts\oncourt-weekly.ps1"
$closeCaptureScript = Join-Path $root "scripts\pinnacle-close-capture.ps1"
$healthScript = Join-Path $root "scripts\tennis-health-check.ps1"
$digestFallbackScript = Join-Path $root "scripts\tennis-digest-fallback.ps1"
$psExe = "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe"

if (!(Test-Path $dailyScript)) { throw "Missing $dailyScript" }
if (!(Test-Path $amRefreshScript)) { throw "Missing $amRefreshScript" }
if (!(Test-Path $weeklyScript)) { throw "Missing $weeklyScript" }
if (!(Test-Path $closeCaptureScript)) { throw "Missing $closeCaptureScript" }
if (!(Test-Path $healthScript)) { throw "Missing $healthScript" }
if (!(Test-Path $digestFallbackScript)) { throw "Missing $digestFallbackScript" }

$dailyCmd = "$psExe -ExecutionPolicy Bypass -NoProfile -WindowStyle Hidden -File `"$dailyScript`""
$amRefreshCmd = "$psExe -ExecutionPolicy Bypass -NoProfile -WindowStyle Hidden -File `"$amRefreshScript`""
$weeklyCmd = "$psExe -ExecutionPolicy Bypass -NoProfile -WindowStyle Hidden -File `"$weeklyScript`""
$closeCaptureCmd = "$psExe -ExecutionPolicy Bypass -NoProfile -WindowStyle Hidden -File `"$closeCaptureScript`""
$healthCmd = "$psExe -ExecutionPolicy Bypass -NoProfile -WindowStyle Hidden -File `"$healthScript`""
$digestFallbackCmd = "$psExe -ExecutionPolicy Bypass -NoProfile -WindowStyle Hidden -File `"$digestFallbackScript`""

function Test-ScheduledTaskExists([string]$taskName) {
    & cmd.exe /c "schtasks /Query /TN `"$taskName`" >nul 2>&1"
    return ($LASTEXITCODE -eq 0)
}

function Remove-ScheduledTaskIfExists([string]$taskName) {
    if (Test-ScheduledTaskExists $taskName) {
        schtasks /Delete /TN $taskName /F | Out-Host
    }
}

function Set-ScheduledTaskBatteryFriendly([string]$taskName) {
    $xml = schtasks /Query /TN $taskName /XML
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($xml)) {
        throw "Unable to read scheduled task XML for $taskName"
    }

    $patchedXml = $xml `
        -replace '<DisallowStartIfOnBatteries>true</DisallowStartIfOnBatteries>', '<DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>' `
        -replace '<StopIfGoingOnBatteries>true</StopIfGoingOnBatteries>', '<StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>'

    # A sleeping/offline laptop must catch up the daily refresh when it next
    # becomes available instead of silently leaving yesterday's board live.
    if ($patchedXml -match '<StartWhenAvailable>.*?</StartWhenAvailable>') {
        $patchedXml = [regex]::Replace($patchedXml, '<StartWhenAvailable>.*?</StartWhenAvailable>', '<StartWhenAvailable>true</StartWhenAvailable>')
    } else {
        $patchedXml = $patchedXml -replace '</Settings>', "    <StartWhenAvailable>true</StartWhenAvailable>`r`n  </Settings>"
    }

    $tmpPath = Join-Path ([System.IO.Path]::GetTempPath()) "$taskName.xml"
    try {
        Set-Content -Path $tmpPath -Value $patchedXml -Encoding Unicode
        schtasks /Create /TN $taskName /XML $tmpPath /F | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Unable to update scheduled task settings for $taskName (exit $LASTEXITCODE)" }
    } finally {
        Remove-Item -LiteralPath $tmpPath -Force -ErrorAction SilentlyContinue
    }
}

function Set-ScheduledTaskBridgeHardening(
    [string]$taskName,
    [string]$executionTimeLimit = "PT10M",
    [string]$restartInterval = "PT5M",
    [int]$restartCount = 2,
    [switch]$HighestRunLevel
) {
    $xml = schtasks /Query /TN $taskName /XML
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($xml)) {
        throw "Unable to read scheduled task XML for $taskName"
    }

    $patchedXml = $xml
    if ($HighestRunLevel) {
        if ($patchedXml -match '<RunLevel>.*?</RunLevel>') {
            $patchedXml = [regex]::Replace($patchedXml, '<RunLevel>.*?</RunLevel>', '<RunLevel>HighestAvailable</RunLevel>')
        } elseif ($patchedXml -match '</LogonType>') {
            $patchedXml = $patchedXml -replace '</LogonType>', "</LogonType>`r`n      <RunLevel>HighestAvailable</RunLevel>"
        } else {
            throw "Scheduled task XML for $taskName is missing <LogonType>"
        }
    }

    if ($patchedXml -match '<WakeToRun>.*?</WakeToRun>') {
        $patchedXml = [regex]::Replace($patchedXml, '<WakeToRun>.*?</WakeToRun>', '<WakeToRun>true</WakeToRun>')
    } else {
        $patchedXml = $patchedXml -replace '</Settings>', "    <WakeToRun>true</WakeToRun>`r`n  </Settings>"
    }

    if ($patchedXml -match '<StartWhenAvailable>.*?</StartWhenAvailable>') {
        $patchedXml = [regex]::Replace($patchedXml, '<StartWhenAvailable>.*?</StartWhenAvailable>', '<StartWhenAvailable>true</StartWhenAvailable>')
    } else {
        $patchedXml = $patchedXml -replace '</Settings>', "    <StartWhenAvailable>true</StartWhenAvailable>`r`n  </Settings>"
    }

    if ($patchedXml -match '<ExecutionTimeLimit>.*?</ExecutionTimeLimit>') {
        $patchedXml = [regex]::Replace($patchedXml, '<ExecutionTimeLimit>.*?</ExecutionTimeLimit>', "<ExecutionTimeLimit>$executionTimeLimit</ExecutionTimeLimit>")
    } else {
        $patchedXml = $patchedXml -replace '</Settings>', "    <ExecutionTimeLimit>$executionTimeLimit</ExecutionTimeLimit>`r`n  </Settings>"
    }

    $restartBlock = @"
    <RestartOnFailure>
      <Interval>$restartInterval</Interval>
      <Count>$restartCount</Count>
    </RestartOnFailure>
"@
    if ($patchedXml -match '<RestartOnFailure>.*?</RestartOnFailure>') {
        $patchedXml = [regex]::Replace($patchedXml, '<RestartOnFailure>.*?</RestartOnFailure>', $restartBlock, [System.Text.RegularExpressions.RegexOptions]::Singleline)
    } else {
        $patchedXml = $patchedXml -replace '</Settings>', "$restartBlock`r`n  </Settings>"
    }

    $tmpPath = Join-Path ([System.IO.Path]::GetTempPath()) "$taskName.bridge.xml"
    try {
        Set-Content -Path $tmpPath -Value $patchedXml -Encoding Unicode
        schtasks /Create /TN $taskName /XML $tmpPath /F | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Unable to harden scheduled task $taskName (exit $LASTEXITCODE)" }
    } finally {
        Remove-Item -LiteralPath $tmpPath -Force -ErrorAction SilentlyContinue
    }
}

Remove-ScheduledTaskIfExists "OnCourt Daily Sync"
Remove-ScheduledTaskIfExists "OnCourt Weekly"
Remove-ScheduledTaskIfExists "IlMargine-PinnacleCloseCapture"
Remove-ScheduledTaskIfExists "IlMargine-Tennis-Health"

schtasks /Create /TN "IlMargine-Daily" /SC DAILY /ST 22:30 /TR "$dailyCmd" /F | Out-Host
schtasks /Create /TN "IlMargine-Daily-AM" /SC DAILY /ST 10:05 /TR "$amRefreshCmd" /F | Out-Host
schtasks /Create /TN "IlMargine-Weekly" /SC WEEKLY /D SUN /ST 03:00 /TR "$weeklyCmd" /F | Out-Host
schtasks /Create /TN "IlMargine-Tennis-Close-Capture" /SC DAILY /ST 08:00 /RI 30 /DU 16:00 /TR "$closeCaptureCmd" /F | Out-Host
schtasks /Create /TN "IlMargine-Tennis-Health-AM" /SC DAILY /ST 11:15 /TR "$healthCmd" /F | Out-Host
schtasks /Create /TN "IlMargine-Tennis-Health-PM" /SC DAILY /ST 23:15 /TR "$healthCmd" /F | Out-Host
schtasks /Create /TN "IlMargine-Tennis-Digest-AM" /SC DAILY /ST 10:50 /TR "$digestFallbackCmd" /F | Out-Host

Set-ScheduledTaskBatteryFriendly "IlMargine-Daily"
Set-ScheduledTaskBatteryFriendly "IlMargine-Daily-AM"
Set-ScheduledTaskBatteryFriendly "IlMargine-Weekly"
Set-ScheduledTaskBatteryFriendly "IlMargine-Tennis-Close-Capture"
Set-ScheduledTaskBatteryFriendly "IlMargine-Tennis-Health-AM"
Set-ScheduledTaskBatteryFriendly "IlMargine-Tennis-Health-PM"
Set-ScheduledTaskBatteryFriendly "IlMargine-Tennis-Digest-AM"
Set-ScheduledTaskBridgeHardening "IlMargine-Weekly" -executionTimeLimit "PT6H" -restartInterval "PT15M" -restartCount 1
Set-ScheduledTaskBridgeHardening "IlMargine-Tennis-Close-Capture"
Set-ScheduledTaskBridgeHardening "IlMargine-Tennis-Health-AM" -executionTimeLimit "PT5M" -restartCount 1
Set-ScheduledTaskBridgeHardening "IlMargine-Tennis-Health-PM" -executionTimeLimit "PT5M" -restartCount 1
Set-ScheduledTaskBridgeHardening "IlMargine-Tennis-Digest-AM" -executionTimeLimit "PT5M" -restartCount 1

if (Test-ScheduledTaskExists "IlMargine-Tennis-Shadow-Settle") {
    schtasks /Delete /TN "IlMargine-Tennis-Shadow-Settle" /F | Out-Host
}

Write-Host ""
Write-Host "Tasks created/updated:"
schtasks /Query /TN "IlMargine-Daily" | Out-Host
schtasks /Query /TN "IlMargine-Daily-AM" | Out-Host
schtasks /Query /TN "IlMargine-Weekly" | Out-Host
schtasks /Query /TN "IlMargine-Tennis-Close-Capture" | Out-Host
schtasks /Query /TN "IlMargine-Tennis-Health-AM" | Out-Host
schtasks /Query /TN "IlMargine-Tennis-Health-PM" | Out-Host
schtasks /Query /TN "IlMargine-Tennis-Digest-AM" | Out-Host
Write-Host ""
Write-Host "Optional immediate test:"
Write-Host "  schtasks /Run /TN IlMargine-Daily"
Write-Host "  schtasks /Run /TN IlMargine-Tennis-Close-Capture"
