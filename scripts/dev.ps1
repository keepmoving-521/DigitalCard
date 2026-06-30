$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$env:UV_CACHE_DIR = Join-Path $root ".cache\uv"

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example. Replace SECRET_KEY before production use." -ForegroundColor Yellow
}

if (-not (Test-Path ".venv")) {
    uv sync
}

if (-not (Test-Path "node_modules")) {
    npm install
}

uv run alembic -c backend/alembic.ini upgrade head
npm run dev
