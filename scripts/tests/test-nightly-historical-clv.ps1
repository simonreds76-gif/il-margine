param(
    [string]$NightlyPath = (Join-Path $PSScriptRoot "..\oncourt-settle-nightly.ps1"),
    [string]$WeeklyPath = (Join-Path $PSScriptRoot "..\oncourt-weekly.ps1")
)
$ErrorActionPreference = "Stop"
function Parse-Script($Path) {
    $tokens = $null; $parseErrors = $null
    $ast = [System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path $Path), [ref]$tokens, [ref]$parseErrors)
    if ($parseErrors.Count) { throw "Script does not parse: $Path : $parseErrors" }
    return $ast
}
$nightly = Parse-Script $NightlyPath
$weekly = Parse-Script $WeeklyPath
$gate = @($nightly.FindAll({ param($node)
    $node -is [System.Management.Automation.Language.IfStatementAst] -and
    $node.Clauses[0].Item1.Extent.Text -eq '$IncludeHistoricalClv'
}, $true))
if ($gate.Count -ne 1) { throw "Expected one explicit historical CLV gate" }
$params = @($nightly.ParamBlock.Parameters | Where-Object { $_.Name.VariablePath.UserPath -eq "IncludeHistoricalClv" })
if ($params.Count -ne 1 -or $params[0].DefaultValue) { throw "Historical audits must be opt-in" }
$auditCalls = @($nightly.FindAll({ param($node)
    $node -is [System.Management.Automation.Language.CommandAst] -and
    $node.GetCommandName() -eq "Invoke-HistoryStep" -and
    $node.CommandElements[1].Extent.Text -eq 'scripts\audit-strict-clv.py'
}, $true))
if ($auditCalls.Count -ne 2) { throw "Expected exactly two historical audits" }
foreach ($call in $auditCalls) {
    if ($call.Extent.StartOffset -lt $gate[0].Extent.StartOffset -or $call.Extent.EndOffset -gt $gate[0].Extent.EndOffset) {
        throw "Historical audit escaped weekly-only gate"
    }
}
# Evaluate only the real gate with a fake Python step: no data writes, prices or alerts.
function Log($Message) { $script:messages += [string]$Message }
function Invoke-HistoryStep {
    $script:commands += ,@($args)
    $global:LASTEXITCODE = $script:mockExit
}
$gateBlock = [scriptblock]::Create($gate[0].Extent.Text)
foreach ($case in @(
    @{ Enabled=$false; Exit=0; Calls=0; Warnings=0 },
    @{ Enabled=$true; Exit=0; Calls=2; Warnings=0 },
    @{ Enabled=$true; Exit=1; Calls=2; Warnings=2 }
)) {
    $IncludeHistoricalClv = $case.Enabled
    $script:commands = @(); $script:messages = @(); $script:mockExit = $case.Exit
    . $gateBlock
    if ($script:commands.Count -ne $case.Calls) { throw "Wrong number of audits: $($case | ConvertTo-Json -Compress)" }
    if (@($script:messages | Where-Object { $_ -like 'WARNING:*' }).Count -ne $case.Warnings) { throw "Audit errors no longer reported independently" }
    if (-not $case.Enabled -and @($script:messages | Where-Object { $_ -like '*saved reports retained*' }).Count -ne 1) { throw "Nightly deferral must be explicit" }
    foreach ($i in 0..($case.Calls - 1)) {
        if ($case.Calls -eq 0) { break }
        $side = @('match', 'spread')[$i]; $suffix = @('ml', 'spread')[$i]
        $expected = @('scripts\audit-strict-clv.py', '--signals', 'data\backtest\tennis-model-market-gap-archive.csv', '--bet-type', $side,
            '--detail-csv', "data\backtest\tennis-model-market-gap-clv-$suffix.csv",
            '--summary-txt', "data\backtest\tennis-model-market-gap-clv-$suffix.txt",
            '--unmatched-csv', "data\backtest\tennis-model-market-gap-clv-$suffix-unmatched.csv")
        if (($script:commands[$i] -join '|') -ne ($expected -join '|')) { throw "Historical audit arguments changed" }
    }
}
# Settlement/report calls must still execute unconditionally before/after the gate.
$settlement = @($nightly.FindAll({ param($node)
    $node -is [System.Management.Automation.Language.CommandAst] -and $node.GetCommandName() -eq 'Invoke-HistoryStep' -and
    $node.Extent.Text -like '*settle-strict-signals.py --csv data\backtest\tennis-model-market-gap-archive.csv*'
}, $true))
$report = @($nightly.FindAll({ param($node)
    $node -is [System.Management.Automation.Language.CommandAst] -and $node.GetCommandName() -eq 'Invoke-HistoryStep' -and
    $node.CommandElements[1].Extent.Text -eq 'scripts\tennis-model-market-gap-report.py'
}, $true))
if ($settlement.Count -ne 1 -or $settlement[0].Extent.EndOffset -ge $gate[0].Extent.StartOffset) { throw "Nightly settlement delayed behind historical scans" }
if ($report.Count -ne 1 -or $report[0].Extent.StartOffset -le $gate[0].Extent.EndOffset) { throw "Nightly report removed or gated" }
$weeklyCalls = @($weekly.FindAll({ param($node)
    $node -is [System.Management.Automation.Language.CommandAst] -and
    $node.Extent.Text -like '*-File scripts\oncourt-settle-nightly.ps1*'
}, $true))
if ($weeklyCalls.Count -ne 1 -or $weeklyCalls[0].Extent.Text -notlike '*-CooperativeLock -IncludeHistoricalClv*') { throw "Existing weekly run must retain both audits and yield to Admin" }
Write-Output 'PASS: nightly skips both historical audits; weekly runs unchanged commands; audit failures remain visible; daily settlement/report and cooperative locking retained.'
