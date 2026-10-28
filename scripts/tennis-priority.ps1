# Shared-file safety with manual refresh priority between background operations.
. (Join-Path $PSScriptRoot 'task-lock.ps1')

function Get-TennisPriorityRequest {
    param([string]$RootPath)
    $path = Join-Path $RootPath 'data\locks\tennis-on-demand-request.json'
    try {
        $request = Get-Content -LiteralPath $path -Raw -ErrorAction Stop | ConvertFrom-Json
        if ($request.request_id -and [datetime]::Parse($request.expires_at).ToUniversalTime() -gt [datetime]::UtcNow) { return $request }
    } catch {}
    return $null
}

function Enter-TennisPriorityLock {
    param([string]$RootPath, [switch]$Priority, [int]$WaitSeconds = 3600, [int]$PollSeconds = 2)
    $deadline = [datetime]::UtcNow.AddSeconds($WaitSeconds)
    do {
        if ($Priority -or $null -eq (Get-TennisPriorityRequest $RootPath)) {
            $handle = Enter-TaskLock -LockName 'tennis-automation' -RootPath $RootPath
            if ($null -ne $handle) {
                # Recheck after acquiring, to close the race with a new request.
                if ($Priority -or $null -eq (Get-TennisPriorityRequest $RootPath)) { return $handle }
                Exit-TaskLock $handle
            }
        }
        if ([datetime]::UtcNow -ge $deadline) { break }
        Start-Sleep -Milliseconds ([Math]::Max(50, $PollSeconds * 1000))
    } while ($true)
    throw 'Timed out waiting for exclusive tennis input/ledger access.'
}

function Invoke-TennisHistoryPython {
    # Every historical writer finishes before releasing the same lock that
    # pricing uses. Manual work may run between steps, never over a live writer.
    $arguments = $args
    $historyLock = Enter-TennisPriorityLock -RootPath $root
    $code = 1
    try { & python @arguments; $code = $LASTEXITCODE }
    finally { Exit-TaskLock $historyLock }
    $global:LASTEXITCODE = $code
}

function Write-TennisManualProgress {
    param([string]$RootPath, $Request, [string]$Phase, [string]$Message, [hashtable]$Details = @{})
    if ($null -eq $Request) { return }
    $path = Join-Path $RootPath 'data\backtest\tennis-on-demand-status.json'
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $path) | Out-Null
    $value = @{}
    try {
        $previous = Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
        if ($previous.request_id -eq $Request.request_id) {
            foreach ($property in $previous.PSObject.Properties) { $value[$property.Name] = $property.Value }
        }
    } catch {}
    $current = @{ request_id = $Request.request_id; requested_at = $Request.requested_at;
        state = 'started'; phase = $Phase; progress_message = $Message;
        updated_at = [datetime]::UtcNow.ToString('o') }
    foreach ($key in $current.Keys) { $value[$key] = $current[$key] }
    foreach ($key in $Details.Keys) { $value[$key] = $Details[$key] }
    $temporary = "$path.$PID.tmp"
    [System.IO.File]::WriteAllText($temporary, ($value | ConvertTo-Json -Depth 6), (New-Object System.Text.UTF8Encoding($false)))
    Move-Item -LiteralPath $temporary -Destination $path -Force
}
