param(
    [Parameter(Mandatory=$true)][string]$ConfigPath,
    [string]$Python = 'C:\Python314\python.exe'
)
$ErrorActionPreference = 'Stop'
$config = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
$state = [IO.Path]::GetFullPath($config.stateDirectory)
$script = Join-Path $PSScriptRoot 'football_atlas_update.py'
if (!(Test-Path -LiteralPath $Python) -or !(Test-Path -LiteralPath $script)) { throw 'Runtime missing' }
$configFull = (Resolve-Path -LiteralPath $ConfigPath).Path
$user = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
function Quote-PS([string]$s) { return "'" + $s.Replace("'", "''") + "'" }
foreach ($kind in @('capture','publish')) {
    $name = if ($kind -eq 'capture') { 'IlMargine-Football-Atlas-Capture' } else { 'IlMargine-Football-Atlas-Weekly' }
    $ps = Join-Path $state "$kind-task.ps1"
    $vbs = Join-Path $state "$kind-task.vbs"
    $log = Join-Path $state "$kind-task.log"
    $body = @"
`$ErrorActionPreference = 'Continue'
`$env:PYTHONDONTWRITEBYTECODE = '1'
`$env:PYTHONUTF8 = '1'
`$log = $(Quote-PS $log)
if ((Test-Path -LiteralPath `$log) -and (Get-Item -LiteralPath `$log).Length -gt 5MB) {
    Copy-Item -LiteralPath `$log -Destination (`$log + '.previous') -Force
    Clear-Content -LiteralPath `$log
}
& $(Quote-PS $Python) $(Quote-PS $script) $kind --config $(Quote-PS $configFull) *>> `$log
exit `$LASTEXITCODE
"@
    [IO.File]::WriteAllText($ps, $body, [Text.UTF8Encoding]::new($false))
    $command = 'powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' + $ps + '"'
    $vb = "Option Explicit`r`nDim s, rc`r`nSet s = CreateObject(""WScript.Shell"")`r`nrc = s.Run(""" + $command.Replace('"','""') + """, 0, True)`r`nWScript.Quit rc`r`n"
    [IO.File]::WriteAllText($vbs, $vb, [Text.UTF8Encoding]::new($false))
    $action = New-ScheduledTaskAction -Execute "$env:WINDIR\System32\wscript.exe" -Argument "//B //NoLogo `"$vbs`""
    if ($kind -eq 'capture') {
        $trigger = New-ScheduledTaskTrigger -Daily -At '00:00'
        $repeat = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 10) -RepetitionDuration (New-TimeSpan -Days 1)
        $trigger.Repetition = $repeat.Repetition
        $limit = New-TimeSpan -Minutes 8
    } else {
        $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Tuesday -At '09:15'
        $limit = New-TimeSpan -Minutes 50
    }
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -ExecutionTimeLimit $limit
    Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description 'Local Football Atlas: validated Pinnacle 1X2 collection and weekly publication, hidden windows.' -Force | Out-Null
    Write-Output "Registered $name"
}
