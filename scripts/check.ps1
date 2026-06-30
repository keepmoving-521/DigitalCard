$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

uv run ruff check backend
uv run ruff format --check backend
uv run pytest
npm run typecheck
npm test
npm run build

Write-Host "All checks passed." -ForegroundColor Green

