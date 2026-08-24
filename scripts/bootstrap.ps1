# Local research bootstrap. Not a production installer.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

uv sync
Set-Location frontend
npm ci
npm run build
Set-Location ..
uv run crowdent doctor --json
Write-Host "RESEARCH ONLY — NOT DEPLOYMENT CERTIFIED"
