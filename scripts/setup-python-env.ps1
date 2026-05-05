param(
    [string]$VenvPath = ".venv",
    [switch]$Force
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

function Resolve-Python {
    $candidates = @(
        @("py", @("-3.11")),
        @("py", @("-3.12")),
        @("py", @("-3.14")),
        @("python", @())
    )

    foreach ($candidate in $candidates) {
        $exe = $candidate[0]
        $args = $candidate[1]
        $probe = $null
        try {
            $probe = & $exe @args -c "import platform, sys; print(sys.executable); print(platform.architecture()[0]); print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
        } catch {
            continue
        }
        if ($LASTEXITCODE -ne 0 -or -not $probe -or $probe.Count -lt 3) {
            continue
        }
        if ($probe[1] -ne "64bit") {
            Write-Host "Skipping $exe $($args -join ' '): $($probe[1]) Python is not suitable for numeric wheels."
            continue
        }
        return [pscustomobject]@{
            Command = $exe
            Args = $args
            Path = $probe[0]
            Version = $probe[2]
        }
    }

    throw "No suitable 64-bit Python found. Install Python 3.11, 3.12, or 3.14 x64, then rerun this script."
}

$python = Resolve-Python
Write-Host "Using Python $($python.Version): $($python.Path)"

$venvFullPath = Join-Path $repoRoot $VenvPath
if ((Test-Path -LiteralPath $venvFullPath) -and $Force) {
    Write-Host "Removing existing venv: $venvFullPath"
    Remove-Item -LiteralPath $venvFullPath -Recurse -Force
}

if (-not (Test-Path -LiteralPath $venvFullPath)) {
    Write-Host "Creating venv: $venvFullPath"
    & $python.Command @($python.Args + @("-m", "venv", $venvFullPath))
}

$venvPython = Join-Path $venvFullPath "Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPython)) {
    throw "Venv Python not found: $venvPython"
}

& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r (Join-Path $repoRoot "scripts\requirements.txt")
& $venvPython -m pip check

Write-Host ""
Write-Host "Python environment ready."
Write-Host "Activate with:"
Write-Host "  .\.venv\Scripts\Activate.ps1"
Write-Host "Or run scripts directly with:"
Write-Host "  .\.venv\Scripts\python.exe scripts\<script-name>.py"
