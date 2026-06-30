$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv is required. Install it from https://docs.astral.sh/uv/"
}
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    throw "Node.js 22 or newer is required."
}
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
}

uv sync
npm install
uv run alembic -c backend/alembic.ini upgrade head
Write-Host "DigitalCard setup complete. Run .\scripts\dev.ps1 to start all services." -ForegroundColor Green

