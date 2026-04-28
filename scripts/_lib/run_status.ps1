function Get-RunStatusRepoRoot {
    return Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
}

function Import-RunStatusEnv {
    if ($script:RunStatusEnvLoaded) {
        return
    }

    $root = Get-RunStatusRepoRoot
    foreach ($name in @(".env.local", "env.local")) {
        $path = Join-Path $root $name
        if (-not (Test-Path $path)) {
            continue
        }

        foreach ($rawLine in Get-Content $path -Encoding UTF8) {
            $line = "$rawLine".Trim()
            if ([string]::IsNullOrWhiteSpace($line) -or $line.StartsWith("#") -or -not $line.Contains("=")) {
                continue
            }

            $parts = $line.Split("=", 2)
            $key = $parts[0].Trim()
            $value = $parts[1].Trim().Trim('"').Trim("'")
            if (-not [string]::IsNullOrWhiteSpace($key) -and -not (Test-Path "Env:$key")) {
                Set-Item -Path "Env:$key" -Value $value
            }
        }
    }

    $script:RunStatusEnvLoaded = $true
}

function Resolve-RunStatusPython {
    if (-not [string]::IsNullOrWhiteSpace($env:RUN_STATUS_PY) -and (Test-Path $env:RUN_STATUS_PY)) {
        return $env:RUN_STATUS_PY
    }

    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source) {
        return $cmd.Source
    }

    foreach ($candidate in @(
        "C:\Python314\python.exe",
        "C:\Python313\python.exe",
        "C:\Python312\python.exe",
        "C:\Python311\python.exe",
        "C:\Python312-32\python.exe"
    )) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    return $null
}

function Invoke-RunStatusCli {
    param(
        [Parameter(Mandatory = $true)][string[]]$ArgumentList
    )

    try {
        Import-RunStatusEnv
        $pythonExe = Resolve-RunStatusPython
        if ([string]::IsNullOrWhiteSpace($pythonExe)) {
            return
        }

        $cliPath = Join-Path $PSScriptRoot "run_status_cli.py"
        if (-not (Test-Path $cliPath)) {
            return
        }

        & $pythonExe $cliPath @ArgumentList 2>&1 | Out-Null
    } catch {
        # Observability must never break the caller.
    }
}

function Start-RunStatus {
    param(
        [Parameter(Mandatory = $true)][string]$Pipeline,
        [string]$Trigger = "schedule"
    )

    $runId = [guid]::NewGuid().ToString()
    Invoke-RunStatusCli -ArgumentList @(
        "start",
        "--run-id", $runId,
        "--pipeline", $Pipeline,
        "--trigger-kind", $Trigger
    )

    return [pscustomobject]@{
        RunId = $runId
        Pipeline = $Pipeline
    }
}

function Complete-RunStatus {
    param(
        [Parameter(Mandatory = $false)]$Run,
        [Parameter(Mandatory = $true)][ValidateSet("ok", "failed", "timeout", "aborted")][string]$Status,
        [Nullable[int]]$RowsOut = $null,
        $ErrorRecord = $null,
        [string]$ErrorType = $null,
        [string]$ErrorMessage = $null
    )

    if ($null -eq $Run) {
        return
    }

    $args = @(
        "complete",
        "--run-id", "$($Run.RunId)",
        "--status", $Status
    )

    if ($RowsOut.HasValue) {
        $args += @("--rows-out", "$($RowsOut.Value)")
    }

    if ($null -ne $ErrorRecord) {
        $args += @("--error-type", $ErrorRecord.Exception.GetType().Name)
        $args += @("--error-message", $ErrorRecord.ToString())
    } else {
        if (-not [string]::IsNullOrWhiteSpace($ErrorType)) {
            $args += @("--error-type", $ErrorType)
        }
        if (-not [string]::IsNullOrWhiteSpace($ErrorMessage)) {
            $args += @("--error-message", $ErrorMessage)
        }
    }

    Invoke-RunStatusCli -ArgumentList $args
}
