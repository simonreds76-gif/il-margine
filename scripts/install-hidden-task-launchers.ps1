# Run once, or after registering Il Margine tasks. Changes actions only.
[CmdletBinding(SupportsShouldProcess = $true)]
param([string[]]$TaskName = @())

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$launcherDir = Join-Path $repoRoot 'data\task-launchers'
$backupDir = Join-Path $repoRoot ('data\task-backups\windowless-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
$wscript = Join-Path $env:WINDIR 'System32\wscript.exe'
if (-not (Test-Path -LiteralPath $wscript)) { throw 'Windows Script Host is unavailable; no tasks changed.' }

function ConvertTo-VbsLiteral([string]$Value) {
    return '"' + $Value.Replace('"', '""') + '"'
}

function New-WrapperText([string]$Command, [string]$WorkingDirectory) {
    $lines = @('Option Explicit', 'Dim shell, result', 'Set shell = CreateObject("WScript.Shell")')
    if ($WorkingDirectory) { $lines += 'shell.CurrentDirectory = ' + (ConvertTo-VbsLiteral $WorkingDirectory) }
    # Wait for the real job and propagate its exit status to Task Scheduler.
    $lines += 'result = shell.Run(' + (ConvertTo-VbsLiteral $Command) + ', 0, True)'
    $lines += 'WScript.Quit result'
    return ($lines -join "`r`n") + "`r`n"
}

$tasks = @(Get-ScheduledTask | Where-Object {
    $_.TaskPath -eq '\' -and $_.TaskName -match '^Il\s?Margine(?:-| -)' -and
    ($TaskName.Count -eq 0 -or $_.TaskName -in $TaskName)
})
$changed = 0
$blocked = @()
foreach ($task in $tasks) {
    # SYSTEM jobs already run off the interactive desktop; do not alter accounts.
    if ($task.Principal.LogonType.ToString() -ne 'Interactive') { continue }
    if (@($task.Actions).Count -ne 1) { throw "Expected one action for $($task.TaskName); unchanged." }
    $oldAction = $task.Actions[0]
    if ($oldAction.Execute -ieq $wscript -and $oldAction.Arguments -like "*$launcherDir*") {
        Write-Output "Already windowless: $($task.TaskName)"
        continue
    }
    if ([IO.Path]::GetFileName($oldAction.Execute) -notmatch '^(powershell|pwsh|cmd|python|node)(\.exe)?$') {
        Write-Output "Unrecognized launcher, unchanged: $($task.TaskName)"
        continue
    }
    if (-not $PSCmdlet.ShouldProcess($task.TaskName, 'Replace console action with waiting, hidden Windows Script Host launcher')) { continue }
    New-Item -ItemType Directory -Force -Path $launcherDir, $backupDir | Out-Null
    $safeName = $task.TaskName -replace '[^a-zA-Z0-9_-]', '_'
    $backupPath = Join-Path $backupDir ($safeName + '.xml')
    $xmlBefore = Export-ScheduledTask -TaskName $task.TaskName -TaskPath $task.TaskPath
    [IO.File]::WriteAllText($backupPath, $xmlBefore, [Text.Encoding]::Unicode)
    $originalCommand = '"' + $oldAction.Execute.Trim('"') + '"'
    if ($oldAction.Arguments) { $originalCommand += ' ' + $oldAction.Arguments }
    $wrapperPath = Join-Path $launcherDir ($safeName + '.vbs')
    [IO.File]::WriteAllText($wrapperPath, (New-WrapperText $originalCommand $oldAction.WorkingDirectory), [Text.Encoding]::Unicode)
    $newActionParams = @{ Execute = $wscript; Argument = '//B //NoLogo "' + $wrapperPath + '"' }
    if ($oldAction.WorkingDirectory) { $newActionParams.WorkingDirectory = $oldAction.WorkingDirectory }
    $newAction = New-ScheduledTaskAction @newActionParams
    try {
        Set-ScheduledTask -TaskName $task.TaskName -TaskPath $task.TaskPath -Action $newAction -ErrorAction Stop | Out-Null
    } catch {
        if ($task.State.ToString() -eq 'Disabled') {
            Write-Warning "Protected disabled task left unchanged: $($task.TaskName). It cannot open a window while disabled."
            continue
        }
        $blocked += $task.TaskName
        Write-Warning "Unable to update $($task.TaskName): $($_.Exception.Message)"
        continue
    }
    $saved = Get-ScheduledTask -TaskName $task.TaskName -TaskPath $task.TaskPath
    if ($saved.Actions[0].Execute -ine $wscript -or $saved.Actions[0].Arguments -ne $newActionParams.Argument) {
        throw "Launcher verification failed for $($task.TaskName); inspect backup $backupPath"
    }
    [xml]$before = $xmlBefore
    [xml]$after = Export-ScheduledTask -TaskName $task.TaskName -TaskPath $task.TaskPath
    foreach ($node in @('Triggers', 'Principals', 'Settings')) {
        if ($before.Task.$node.OuterXml -ne $after.Task.$node.OuterXml) {
            Set-ScheduledTask -TaskName $task.TaskName -TaskPath $task.TaskPath -Action $oldAction | Out-Null
            throw "Unexpected $node change for $($task.TaskName); original action restored. Backup: $backupPath"
        }
    }
    $changed++
    Write-Output "Windowless: $($task.TaskName); original action saved in $backupPath"
}
Write-Output "Updated $changed task action(s). Schedules, enabled states, accounts and retry settings preserved."
if ($blocked.Count) { throw ('Enabled tasks still need repair: ' + ($blocked -join ', ')) }
