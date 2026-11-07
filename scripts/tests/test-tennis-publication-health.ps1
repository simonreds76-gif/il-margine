$ErrorActionPreference='Stop'
$repo=Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$root=Join-Path $repo ('outputs/test-publication-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force (Join-Path $root 'data') | Out-Null
function Import-Function($file,$name) {
 $tokens=$null;$errors=$null
 $ast=[Management.Automation.Language.Parser]::ParseFile($file,[ref]$tokens,[ref]$errors)
 if($errors.Count){throw ($errors|Out-String)}
 $node=$ast.Find({param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq $name},$true)
 if(-not $node){throw "Missing $name"};return $node.Extent.Text
}
$health=Join-Path $repo 'scripts/tennis-health-check.ps1'
foreach($name in @('Get-TaskRecoveryLogInfo','Get-LatestTaskRecoveryTime')) {
 . ([scriptblock]::Create((Import-Function $health $name)))
}
$log=Join-Path $root 'data/oncourt-am-refresh.log'
'AM Tennis Refresh finished at 2026-11-07 10:31:25' | Set-Content $log
if(Get-LatestTaskRecoveryTime 'IlMargine-Daily-AM'){throw 'A finished failure was falsely recovered'}
'AM Tennis Refresh verified OK at 2026-11-07 12:31:25' | Add-Content $log
if(-not (Get-LatestTaskRecoveryTime 'IlMargine-Daily-AM')){throw 'Verified success was not accepted'}
$log=Join-Path $root 'data/oncourt-daily.log'
'Daily Pipeline finished at 2026-11-07 10:31:25' | Set-Content $log
if(Get-LatestTaskRecoveryTime 'IlMargine-Daily'){throw 'Nightly failure was falsely recovered'}
'Daily Pipeline verified OK at 2026-11-07 12:31:25' | Add-Content $log
if(-not (Get-LatestTaskRecoveryTime 'IlMargine-Daily')){throw 'Nightly verified success was not accepted'}
foreach($file in @('oncourt-am-refresh.ps1','oncourt-daily.ps1','tennis-health-check.ps1')){
 $tokens=$null;$errors=$null
 $null=[Management.Automation.Language.Parser]::ParseFile((Join-Path $repo ('scripts/'+$file)),[ref]$tokens,[ref]$errors)
 if($errors.Count){throw ($errors|Out-String)}
}
Write-Host 'PASS: four recovery cases and three PowerShell syntax checks; no messages sent.'
