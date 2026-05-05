param(
    [string]$RepoRoot
)

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = Split-Path -Parent $PSScriptRoot
}

$venvScripts = Join-Path $RepoRoot ".venv\Scripts"
$venvPython = Join-Path $venvScripts "python.exe"

if (Test-Path -LiteralPath $venvPython) {
    $pathParts = [System.Collections.Generic.List[string]]::new()
    $env:Path -split ";" | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | ForEach-Object {
        if ($_.TrimEnd("\") -ne $venvScripts.TrimEnd("\")) {
            [void]$pathParts.Add($_)
        }
    }
    $env:Path = "$venvScripts;$($pathParts -join ';')"
    $env:ILMARGINE_PYTHON = $venvPython
}
