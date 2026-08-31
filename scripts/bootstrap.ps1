$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
uv sync --group dev
Set-Location frontend
npm ci
npm run build
Set-Location ..
uv run stilldot doctor
Write-Host "RESEARCH DEMO — NOT DEPLOYMENT-READY"
