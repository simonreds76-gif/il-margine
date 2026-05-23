param(
  [Parameter(Mandatory = $true)]
  [string]$DeploymentUrl,

  [string]$Domain = "ilmargine.bet",
  [string]$Scope = "simones-projects-fb02b6e0"
)

$ErrorActionPreference = "Stop"

$vercel = Get-Command vercel -ErrorAction SilentlyContinue
if (-not $vercel) {
  throw "Vercel CLI is not installed. Install once with: npm.cmd install -g vercel@54.4.1"
}

Write-Host "Trying Vercel promote for $DeploymentUrl..."
& vercel promote $DeploymentUrl --yes --scope $Scope
if ($LASTEXITCODE -eq 0) {
  Write-Host "Vercel promote succeeded."
  exit 0
}

$promoteExit = $LASTEXITCODE
Write-Warning "vercel promote failed with exit code $promoteExit. Falling back to alias set for $Domain."
Write-Warning "This is expected if the local Vercel account can manage domains but is not GitHub-connected for Git deployment promotion."

& vercel alias set $DeploymentUrl $Domain --scope $Scope
if ($LASTEXITCODE -ne 0) {
  exit $LASTEXITCODE
}

Write-Host "Production domain $Domain now points to $DeploymentUrl."
exit 0
