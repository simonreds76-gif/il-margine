param([string]$RootPath = (Split-Path -Parent $PSScriptRoot))
$ErrorActionPreference = 'Stop'
$RootPath = (Resolve-Path -LiteralPath $RootPath).Path
$existing = Get-ScheduledTask -TaskName 'IlMargine-Daily-AM'
$launcherDir = Join-Path $RootPath 'data/task-launchers'
New-Item -ItemType Directory -Force -Path $launcherDir | Out-Null
$launcher = Join-Path $launcherDir 'IlMargine-OnDemand.vbs'
$scriptPath = Join-Path $RootPath 'scripts/oncourt-am-refresh.ps1'
$command = 'powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File "' + $scriptPath + '" -OnDemand'
$escapedCommand = $command.Replace('"','""')
$escapedRoot = $RootPath.Replace('"','""')
$content = @"
Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = "$escapedRoot"
result = shell.Run("$escapedCommand", 0, True)
WScript.Quit result
"@
[System.IO.File]::WriteAllText($launcher, $content, (New-Object System.Text.UTF8Encoding($false)))
$action = New-ScheduledTaskAction -Execute (Join-Path $env:WINDIR 'System32/wscript.exe') -Argument ('//B //NoLogo "' + $launcher + '"') -WorkingDirectory $RootPath
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 2) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
# Deliberately no trigger: only the existing Admin queue may start this task.
Register-ScheduledTask -TaskName 'IlMargine-OnDemand' -Action $action -Settings $settings -Principal $existing.Principal -Description 'Priority manual OnCourt, prices and selection refresh; no historical reporting and no recurring trigger.' -Force | Out-Null
$task = Get-ScheduledTask -TaskName 'IlMargine-OnDemand'
if ($task.Triggers) { throw 'Unexpected trigger on manual-only task' }
Write-Output 'IlMargine-OnDemand installed; zero scheduled triggers.'

