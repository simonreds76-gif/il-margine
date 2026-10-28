$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root
. (Join-Path $root "scripts\use-local-python.ps1") -RepoRoot $root

& python scripts\poll-automation-commands.py
$commandExit = $LASTEXITCODE
# Existing two-minute task; the collector itself permits at most one attempt
# per 30 minutes. It only uploads private quotes, never sends betting alerts.
$paddyScript = Join-Path $root "scripts\paddy_source_runtime\paddy_local_bridge.py"
if (-not (Test-Path $paddyScript)) { $paddyScript = Join-Path $root "scripts\paddy_local_bridge.py" }
& python $paddyScript --root $root
exit $commandExit
