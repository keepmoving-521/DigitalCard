$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$env:UV_CACHE_DIR = Join-Path $root ".cache\uv"

function Invoke-Checked {
    param([scriptblock]$Command)
    & $Command
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

Invoke-Checked { uv run ruff check backend }
Invoke-Checked { uv run ruff format --check backend }
Invoke-Checked { uv run pytest }
Invoke-Checked { npm run typecheck }
Invoke-Checked { npm test }
Invoke-Checked { npm run build }

Write-Host "All checks passed." -ForegroundColor Green
