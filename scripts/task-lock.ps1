$ErrorActionPreference = "Stop"

function Enter-TaskLock {
    param(
        [Parameter(Mandatory = $true)]
        [string]$LockName,
        [Parameter(Mandatory = $true)]
        [string]$RootPath
    )

    $locksDir = Join-Path $RootPath "data\locks"
    New-Item -ItemType Directory -Force -Path $locksDir | Out-Null

    $lockPath = Join-Path $locksDir ($LockName + ".lock")

    try {
        $stream = [System.IO.File]::Open(
            $lockPath,
            [System.IO.FileMode]::OpenOrCreate,
            [System.IO.FileAccess]::ReadWrite,
            [System.IO.FileShare]::None
        )
    } catch {
        return $null
    }

    $payload = @(
        "pid=$PID"
        "started_at=$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
        "host=$env:COMPUTERNAME"
        "script=$($MyInvocation.ScriptName)"
    ) -join [Environment]::NewLine

    $bytes = [System.Text.Encoding]::UTF8.GetBytes($payload)
    $stream.SetLength(0)
    $stream.Write($bytes, 0, $bytes.Length)
    $stream.Flush()

    return @{
        Stream = $stream
        Path = $lockPath
    }
}

function Exit-TaskLock {
    param($LockHandle)

    if ($null -eq $LockHandle) {
        return
    }

    if ($LockHandle.Stream) {
        $LockHandle.Stream.Dispose()
    }

    if ($LockHandle.Path) {
        Remove-Item -LiteralPath $LockHandle.Path -Force -ErrorAction SilentlyContinue
    }
}
