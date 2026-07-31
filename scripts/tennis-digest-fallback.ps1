# Idempotent AM fallback for the private tennis Telegram digest.
# The ready-state guard prevents stale signal files from being reported as today's card.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root
. (Join-Path $root "scripts\use-local-python.ps1") -RepoRoot $root

& python scripts\tennis-daily-signal-digest.py --require-ready
exit $LASTEXITCODE
