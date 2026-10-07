param([string]$DailyPath = (Join-Path $PSScriptRoot "..\oncourt-daily.ps1"))
$ErrorActionPreference = "Stop"
$tokens = $null; $parseErrors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path $DailyPath), [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count) { throw "Nightly script does not parse: $parseErrors" }
$functionAst = $ast.Find({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq "Invoke-NightlyV4Alerts" }, $true)
if ($null -eq $functionAst) { throw "Nightly v4 alert hook missing" }
# Evaluate only this function. Do not run extraction, odds collection or Telegram.
. ([scriptblock]::Create($functionAst.Extent.Text))
function Log($Message) {}
function Set-RunStatusFailure($Type, $Message) { $script:failure = $Type }
function Invoke-LoggedProcess($FilePath, $ArgumentList, $Label, $TimeoutSeconds) {
    $script:calls += 1
    if ($FilePath -ne "python" -or ($ArgumentList -join " ") -ne "scripts\tennis-daily-signal-digest.py --paper-signals-only" -or $TimeoutSeconds -ne 90) { throw "Unexpected command or unbounded alert step" }
    return $script:mockExit
}
foreach ($case in @(@{ Props = 0; Alert = 0; Calls = 1; Failure = "" }, @{ Props = 1; Alert = 0; Calls = 0; Failure = "" }, @{ Props = 0; Alert = 1; Calls = 1; Failure = "TennisV4AlertFailed" })) {
    $script:calls = 0; $script:failure = ""; $script:mockExit = $case.Alert
    Invoke-NightlyV4Alerts -PropsRefreshExit $case.Props
    if ($script:calls -ne $case.Calls -or $script:failure -ne $case.Failure) { throw "Nightly v4 case failed: $($case | ConvertTo-Json -Compress)" }
}
$commands = $ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.CommandAst] -and $node.GetCommandName() -eq "Invoke-NightlyV4Alerts" }, $true)
if ($commands.Count -ne 1) { throw "Expected exactly one nightly v4 hook" }
$text = Get-Content -LiteralPath $DailyPath -Raw
if ($commands[0].Extent.StartOffset -lt $text.IndexOf('$tennisPropsExit = Invoke-LoggedProcessWithRetry')) { throw "Alert runs before forecasts" }
Write-Output "PASS: nightly hook parses; success/failure routing, 90-second bound and producer ordering verified. No external actions executed."
