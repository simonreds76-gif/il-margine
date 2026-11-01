$ErrorActionPreference='Stop'
$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$testOutput = Join-Path $repo 'outputs/health-tests'
New-Item -ItemType Directory -Force $testOutput | Out-Null
$root = Join-Path $testOutput ('r' + [guid]::NewGuid().ToString('N').Substring(0,6))
New-Item -ItemType Directory -Force (Join-Path $root 'scripts'),(Join-Path $root 'data/backtest'),(Join-Path $root 'tmp') | Out-Null
Copy-Item -LiteralPath (Join-Path $repo 'scripts/tennis_runtime_health.py') -Destination (Join-Path $root 'scripts/tennis_runtime_health.py') -Force
$env:TEMP=Join-Path $root 'tmp';$env:TMP=$env:TEMP
$env:TENNIS_RUNTIME_RUN_ID=[guid]::NewGuid().ToString()
function Import-Function($file,$name) {
    $parseTokens=$null;$parseErrors=$null
    $ast=[Management.Automation.Language.Parser]::ParseFile($file,[ref]$parseTokens,[ref]$parseErrors)
    if($parseErrors.Count){throw ($parseErrors|Out-String)}
    $node=$ast.Find({param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq $name},$true)
    if(-not $node){throw "Function missing: $name"}
    return $node.Extent.Text
}
. ([scriptblock]::Create((Import-Function (Join-Path $repo 'scripts/oncourt-daily.ps1') 'Invoke-LoggedProcess')))
. ([scriptblock]::Create((Import-Function (Join-Path $repo 'scripts/tennis-health-check.ps1') 'Read-JsonFile')))
. ([scriptblock]::Create((Import-Function (Join-Path $repo 'scripts/tennis-health-check.ps1') 'Invoke-RuntimeWatchdog')))
function Log($message){Write-Host $message}
$script:fakeMessages=0
function Post-Alert($message){$script:fakeMessages++;return $true}
$NoNotify=$false
Set-Location $root
'import time; time.sleep(5)' | Set-Content -LiteralPath scripts/child.py
$code=Invoke-LoggedProcess -FilePath python -ArgumentList @('scripts/child.py') -Label 'Injected Windows timeout' -TimeoutSeconds 1
if($code -ne 124){throw "Wrong timeout exit: $code"}
$health=& python scripts/tennis_runtime_health.py check --json | ConvertFrom-Json
if($health.issues[0].issue -ne 'TIMED_OUT'){throw 'Timeout not visible'}
$null=Invoke-RuntimeWatchdog
$null=Invoke-RuntimeWatchdog
if($script:fakeMessages -ne 1){throw 'Duplicate failure notice'}
'pass' | Set-Content -LiteralPath scripts/child.py
$code=Invoke-LoggedProcess -FilePath python -ArgumentList @('scripts/child.py') -Label 'Injected Windows timeout' -TimeoutSeconds 5
if($code -ne 0){throw 'Recovery failed'}
$null=Invoke-RuntimeWatchdog
if($script:fakeMessages -ne 1){throw 'Routine success notice emitted'}
'raise SystemExit(3)' | Set-Content -LiteralPath scripts/child.py
$code=Invoke-LoggedProcess -FilePath python -ArgumentList @('scripts/child.py') -Label 'Injected Windows timeout' -TimeoutSeconds 5
if($code -ne 3){throw 'Failure code lost'}
$null=Invoke-RuntimeWatchdog
if($script:fakeMessages -ne 2){throw 'New failure after recovery was not notified'}
$NoNotify=$true
$null=Invoke-RuntimeWatchdog
if($script:fakeMessages -ne 2){throw 'NoNotify was ignored'}
@{passed=$true;real_telegram_messages=0;mock_notifications=$script:fakeMessages;tests=@('Windows timeout','receipt persistence','deduplication','recovery rearm','nonzero exit','NoNotify')} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $testOutput 'windows-runtime-verification.json')
Write-Host 'Windows wrapper and watchdog integration PASS. No network messages.'
