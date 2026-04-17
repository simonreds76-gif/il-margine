# One-time task registration for fully automatic pipeline.
# Daily fair-odds refresh: 10:05 and 23:55.
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

function Set-ScheduledTaskBridgeHardening(
    [string]$taskName,
    [string]$executionTimeLimit = "PT10M",
    [string]$restartInterval = "PT5M",
    [int]$restartCount = 2
) {
    $xmlText = schtasks /Query /TN $taskName /XML
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($xmlText)) {
        throw "Unable to read scheduled task XML for $taskName"
    }

    [xml]$taskXml = $xmlText
    $nsUri = "http://schemas.microsoft.com/windows/2004/02/mit/task"
    $ns = New-Object System.Xml.XmlNamespaceManager($taskXml.NameTable)
    $ns.AddNamespace("t", $nsUri)

    function Set-OrCreateChildText(
        [System.Xml.XmlNode]$parent,
        [string]$name,
        [string]$value
    ) {
        $node = $parent.SelectSingleNode("t:$name", $ns)
        if ($null -eq $node) {
            $node = $taskXml.CreateElement($name, $nsUri)
            [void]$parent.AppendChild($node)
        }
        $node.InnerText = $value
        return $node
    }

    $settings = $taskXml.SelectSingleNode("/t:Task/t:Settings", $ns)
    if ($null -eq $settings) {
        throw "Scheduled task XML for $taskName is missing <Settings>"
    }

    $principal = $taskXml.SelectSingleNode("/t:Task/t:Principals/t:Principal", $ns)
    if ($null -eq $principal) {
        throw "Scheduled task XML for $taskName is missing <Principal>"
    }

    Set-OrCreateChildText $settings "WakeToRun" "true" | Out-Null
    Set-OrCreateChildText $settings "StartWhenAvailable" "true" | Out-Null
    Set-OrCreateChildText $settings "ExecutionTimeLimit" $executionTimeLimit | Out-Null
    Set-OrCreateChildText $principal "RunLevel" "HighestAvailable" | Out-Null

    $restartOnFailure = $settings.SelectSingleNode("t:RestartOnFailure", $ns)
    if ($null -eq $restartOnFailure) {
        $restartOnFailure = $taskXml.CreateElement("RestartOnFailure", $nsUri)
        [void]$settings.AppendChild($restartOnFailure)
    }
    Set-OrCreateChildText $restartOnFailure "Interval" $restartInterval | Out-Null
    Set-OrCreateChildText $restartOnFailure "Count" $restartCount.ToString() | Out-Null

    $tmpPath = Join-Path ([System.IO.Path]::GetTempPath()) "$taskName.bridge.xml"
    $settingsWriter = New-Object System.Xml.XmlWriterSettings
    $settingsWriter.Encoding = [System.Text.UnicodeEncoding]::new($false, $false)
    $settingsWriter.Indent = $true
    $xmlWriter = [System.Xml.XmlWriter]::Create($tmpPath, $settingsWriter)
    $taskXml.Save($xmlWriter)
    $xmlWriter.Dispose()

    schtasks /Create /TN $taskName /XML $tmpPath /F | Out-Null
    Remove-Item -LiteralPath $tmpPath -Force -ErrorAction SilentlyContinue
}

Remove-ScheduledTaskIfExists "OnCourt Daily Sync"
Remove-ScheduledTaskIfExists "OnCourt Weekly"
Remove-ScheduledTaskIfExists "IlMargine-PinnacleCloseCapture"

schtasks /Create /TN "IlMargine-Daily" /SC DAILY /ST 23:55 /TR "$dailyCmd" /F | Out-Host
schtasks /Create /TN "IlMargine-Daily-AM" /SC DAILY /ST 10:05 /TR "$amRefreshCmd" /F | Out-Host
schtasks /Create /TN "IlMargine-Weekly" /SC WEEKLY /D SUN /ST 03:00 /TR "$weeklyCmd" /F | Out-Host
schtasks /Create /TN "IlMargine-Tennis-Close-Capture" /SC DAILY /ST 08:00 /RI 30 /DU 16:00 /TR "$closeCaptureCmd" /F | Out-Host

Set-ScheduledTaskBatteryFriendly "IlMargine-Daily"
Set-ScheduledTaskBatteryFriendly "IlMargine-Daily-AM"
Set-ScheduledTaskBatteryFriendly "IlMargine-Weekly"
Set-ScheduledTaskBatteryFriendly "IlMargine-Tennis-Close-Capture"
Set-ScheduledTaskBridgeHardening "IlMargine-Tennis-Close-Capture"

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
